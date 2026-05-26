"""Multi-turn agent stress test for Atlas.

Drives real `run_turn` generators with sequences of user messages, consumes
the SSE events, and asserts on observable behavior (tool calls, memory writes,
consolidation outputs, response text). Each scenario uses fresh test users
so no production data is touched.

Usage:
  cd backend && uv run python -m scripts.atlas.agent_stress_test
"""

from __future__ import annotations

import logging
import time
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from elasticsearch import Elasticsearch

from app.elasticsearch.client import get_es_client
from app.atlas.agent import run_turn
from app.atlas.memory.constants import (
    INDEX_CATALOG,
    INDEX_EPISODIC,
    INDEX_PROCEDURAL,
    INDEX_SEMANTIC,
)
from app.atlas.memory.operations import write_memory

logger = logging.getLogger(__name__)

REPORT_DIR = Path(__file__).resolve().parents[2] / "data"


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass
class MultiTurnResult:
    name: str
    description: str
    passed: bool
    detail: str
    turns: list[dict[str, Any]] = field(default_factory=list)
    fix_suggestion: str | None = None


SCENARIOS: list[tuple[str, str, Callable]] = []


def scenario(name: str, description: str):
    def decorator(func: Callable):
        SCENARIOS.append((name, description, func))
        return func
    return decorator


# ---------------------------------------------------------------------------
# Driver helpers
# ---------------------------------------------------------------------------

def drive_turn(
    es: Elasticsearch,
    *,
    user_id: str,
    session_id: str,
    history: list[dict[str, Any]],
    user_message: str,
) -> dict[str, Any]:
    """Run one turn end-to-end and aggregate the yielded SSE events."""
    events = list(run_turn(
        es,
        user_id=user_id,
        session_id=session_id,
        history=list(history),
        user_message=user_message,
    ))
    return {
        "user_message": user_message,
        "text": "".join(e.get("text", "") for e in events if e.get("event") == "text_chunk"),
        "tool_calls": [
            (e.get("name"), e.get("arguments") or {})
            for e in events if e.get("event") == "tool_call"
        ],
        "tool_results": [
            (e.get("name"), e.get("result"))
            for e in events if e.get("event") == "tool_result"
        ],
        "memory_writes": [e for e in events if e.get("event") == "memory_write"],
        "consolidation_facts": [e for e in events if e.get("event") == "consolidation_fact"],
        "consolidation_updates": [e for e in events if e.get("event") == "consolidation_update"],
        "events": events,
    }


def cleanup(es: Elasticsearch, user_ids: list[str], catalog_ids: list[str] | None = None) -> None:
    if user_ids:
        try:
            es.delete_by_query(
                index=",".join([INDEX_EPISODIC, INDEX_SEMANTIC, INDEX_PROCEDURAL]),
                body={"query": {"terms": {"user_id": user_ids}}},
                refresh=True,
                conflicts="proceed",
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("cleanup (user docs) failed: %s", exc)
    for cid in catalog_ids or []:
        try:
            es.delete(index=INDEX_CATALOG, id=cid, refresh=True)
        except Exception:  # noqa: BLE001
            pass


# ---------------------------------------------------------------------------
# Scenarios
# ---------------------------------------------------------------------------

@scenario(
    "M1",
    "Cross-turn recall: pre-seeded semantic fact surfaces in agent response",
)
def s_m1(es: Elasticsearch, user_id: str) -> tuple[bool, str, list[dict], str | None]:
    write_memory(es, user_id=user_id, memory_type="semantic",
                 text="User owns a Lumio Hub v3.",
                 fact_type="identity", refresh=True)
    t = drive_turn(es, user_id=user_id, session_id="m1",
                   history=[], user_message="What hub model do I have?")
    has_v3 = "hub v3" in t["text"].lower()
    has_recall = any(name == "recall_memory" for name, _ in t["tool_calls"])
    if has_v3 and has_recall:
        return True, f"agent mentioned Hub v3 (recall calls: {sum(1 for n,_ in t['tool_calls'] if n=='recall_memory')})", [t], None
    detail = f"text mentions hub v3: {has_v3}; recall_memory called: {has_recall}; reply: {t['text'][:200]!r}"
    return False, detail, [t], "If text mentions hub but not v3, check the pre-recall result — semantic_text leg may not be matching. If no recall_memory call, the agent skipped tools; tighten the system prompt."


@scenario(
    "M2",
    "Cross-session persistence: fact survives an empty-history second turn",
)
def s_m2(es: Elasticsearch, user_id: str) -> tuple[bool, str, list[dict], str | None]:
    write_memory(es, user_id=user_id, memory_type="semantic",
                 text="User owns a Lumio Hub v2.",
                 fact_type="identity", refresh=True)
    # Turn 1 in session A — establishes some innocuous context
    t1 = drive_turn(es, user_id=user_id, session_id="m2_sessA",
                    history=[], user_message="Hi there.")
    # Turn 2 in session B — empty history, new session
    t2 = drive_turn(es, user_id=user_id, session_id="m2_sessB",
                    history=[], user_message="What hub do I own?")
    has_v2 = "hub v2" in t2["text"].lower()
    has_recall = any(name == "recall_memory" for name, _ in t2["tool_calls"])
    if has_v2 and has_recall:
        return True, f"second-session recall surfaced Hub v2 (recall calls: {sum(1 for n,_ in t2['tool_calls'] if n=='recall_memory')})", [t1, t2], None
    detail = f"turn2 text mentions hub v2: {has_v2}; recall called: {has_recall}; reply: {t2['text'][:200]!r}"
    return False, detail, [t1, t2], "If memory survives sessions but not surfaced, check pre-recall query + retriever filter; user_id filter must NOT be tied to session_id."


@scenario(
    "M3",
    "Contradiction across turns: turn 1 issues supersession, turn 2 surfaces new fact",
)
def s_m3(es: Elasticsearch, user_id: str) -> tuple[bool, str, list[dict], str | None]:
    write_memory(es, user_id=user_id, memory_type="semantic",
                 text="User lives in Bristol.",
                 fact_type="identity", confidence=0.9, refresh=True)
    t1 = drive_turn(es, user_id=user_id, session_id="m3",
                    history=[], user_message="Actually I moved to Edinburgh.")
    history = [
        {"role": "user", "content": "Actually I moved to Edinburgh."},
        {"role": "assistant", "content": t1["text"]},
    ]
    t2 = drive_turn(es, user_id=user_id, session_id="m3",
                    history=history, user_message="Where do I live?")
    # Did turn 1 issue a supersession?
    superseded_call = any(
        name == "write_memory" and isinstance(args, dict) and args.get("supersedes_id")
        for name, args in t1["tool_calls"]
    )
    has_edin = "edinburgh" in t2["text"].lower()
    # Lenient: Bristol may appear as historical context ("you used to live in Bristol")
    # as long as Edinburgh is the current state.
    if superseded_call and has_edin:
        return True, f"turn1 superseded ({sum(1 for n,a in t1['tool_calls'] if n=='write_memory' and isinstance(a,dict) and a.get('supersedes_id'))} call(s)); turn2 surfaces Edinburgh", [t1, t2], None
    detail = f"superseded call in turn1: {superseded_call}; edinburgh in turn2: {has_edin}; turn2 reply: {t2['text'][:200]!r}"
    return False, detail, [t1, t2], "If superseded_call=False, the agent didn't pick up the contradiction. Check SYSTEM_PROMPT contradiction-rule wording at agent.py:39-42."


@scenario(
    "M4",
    "Range-extender mention + full device list: fact captured (in-turn write OR consolidation) and surfaced",
)
def s_m4(es: Elasticsearch, user_id: str) -> tuple[bool, str, list[dict], str | None]:
    t = drive_turn(es, user_id=user_id, session_id="m4", history=[],
                   user_message="I just got a Lumio Range Extender I haven't set up. What's my full device list?")
    wrote_re = any(
        name == "write_memory" and isinstance(args, dict)
        and "range extender" in (args.get("text") or "").lower()
        for name, args in t["tool_calls"]
    )
    # Post-turn consolidation is an equally valid capture path —
    # the durable fact lands as a semantic memory either way.
    cons_re = any(
        "range extender" in (f.get("text", "") or "").lower()
        for f in t["consolidation_facts"]
    )
    captured = wrote_re or cons_re
    called_recall = any(name == "recall_memory" for name, _ in t["tool_calls"])
    mentions_re = "range extender" in t["text"].lower()
    if captured and called_recall and mentions_re:
        return True, f"captured (in-turn={wrote_re}, consolidation={cons_re}); recalled; surfaced in reply", [t], None
    detail = f"captured: {captured} (in-turn={wrote_re}, consolidation={cons_re}); recalled: {called_recall}; mentioned in reply: {mentions_re}; reply: {t['text'][:200]!r}"
    return False, detail, [t], "If captured=False, neither in-turn write_memory nor consolidation captured the new fact. If mentions_re=False, refresh=True may not be propagating (check tools.py:208 + operations.py:134)."


@scenario(
    "M5",
    "Wrong-info removal: fact gone from recall (via forget_memory OR supersession)",
)
def s_m5(es: Elasticsearch, user_id: str) -> tuple[bool, str, list[dict], str | None]:
    seed = write_memory(es, user_id=user_id, memory_type="semantic",
                       text="User owns a Lumio Hub v1.",
                       fact_type="identity", refresh=True)
    t = drive_turn(es, user_id=user_id, session_id="m5", history=[],
                   user_message="Forget that I have a Hub v1 — that was wrong information.")

    # Path A: forget_memory hard-deletes the doc.
    forget_calls = [args for name, args in t["tool_calls"] if name == "forget_memory"]
    if forget_calls:
        try:
            es.get(index=INDEX_SEMANTIC, id=seed["id"])
            return False, f"forget_memory called but seed doc still exists; calls: {forget_calls}", [t], \
                "forget_memory dispatch path may not be propagating refresh; check tools.py forget_memory branch."
        except Exception:  # noqa: BLE001 (NotFoundError)
            return True, f"agent called forget_memory ({len(forget_calls)}x); seed doc gone (hard delete)", [t], None

    # Path B: harsh-contradiction supersession on the same id soft-removes from recall.
    super_calls = [
        args for name, args in t["tool_calls"]
        if name == "write_memory" and isinstance(args, dict)
        and args.get("supersedes_id") == seed["id"]
    ]
    if super_calls:
        try:
            doc = es.get(index=INDEX_SEMANTIC, id=seed["id"])["_source"]
            if doc.get("superseded_by"):
                return True, f"agent superseded the seed (soft delete via supersedes_id); seed.superseded_by set", [t], None
            return False, f"supersession call made but seed.superseded_by not set", [t], \
                "Check write_memory's update at operations.py:128-142."
        except Exception:  # noqa: BLE001
            return False, "seed doc disappeared without forget_memory and without supersession marker", [t], \
                "Investigate: the seed doc shouldn't vanish without an explicit path."

    detail = f"agent did neither forget_memory nor supersession on seed; reply: {t['text'][:200]!r}; tool calls: {[n for n,_ in t['tool_calls']]}"
    return False, detail, [t], "Agent didn't act on the 'wrong information' / 'forget' intent. Check SYSTEM_PROMPT contradiction + forget rules at agent.py:39-44."


@scenario(
    "M6",
    "Procedural follow-through: pre-seeded playbook surfaces and shapes the response",
)
def s_m6(es: Elasticsearch, user_id: str) -> tuple[bool, str, list[dict], str | None]:
    write_memory(es, user_id=user_id, memory_type="procedural",
                 text="Hub disconnect after power cut: change Zigbee channel",
                 name="zigbee_channel_fix",
                 description="Resolves hub disconnects after a power outage by changing the Zigbee channel",
                 steps=[
                     {"order": 1, "instruction": "Open the Lumio app", "tool": "ask_user"},
                     {"order": 2, "instruction": "Change the Zigbee channel to channel 25", "tool": "ask_user"},
                     {"order": 3, "instruction": "Wait 30 seconds and verify all devices reconnect", "tool": "ask_user"},
                 ],
                 refresh=True)
    t = drive_turn(es, user_id=user_id, session_id="m6", history=[],
                   user_message="My hub disconnected after a power outage. What should I do?")
    text_l = t["text"].lower()
    mentions_zigbee_channel = "zigbee channel" in text_l or "channel 25" in text_l or "change the channel" in text_l
    if mentions_zigbee_channel:
        return True, "agent's reply references the seeded playbook's Zigbee-channel step", [t], None
    detail = f"reply doesn't mention zigbee channel; reply: {t['text'][:300]!r}; tool calls: {[n for n,_ in t['tool_calls']]}"
    return False, detail, [t], "Procedural recall may not be surfacing. Verify the procedural trigger_text gets BM25/semantic hits on 'power outage' / 'disconnect' phrasing."


@scenario(
    "M7",
    "Catalog federation: agent recalls with include_catalog=true on a product question",
)
def s_m7(es: Elasticsearch, user_id: str) -> tuple[bool, str, list[dict], str | None]:
    cat_id = f"stress-cat-{int(time.time())}"
    es.index(index=INDEX_CATALOG, id=cat_id,
             document={
                 "text": "Lumio Hub v3 comes with a 5-year manufacturer warranty covering hardware defects.",
                 "fact_type": "world",
             },
             refresh=True)
    try:
        t = drive_turn(es, user_id=user_id, session_id="m7", history=[],
                       user_message="What's the warranty on the Hub v3?")
        used_catalog = any(
            name == "recall_memory" and isinstance(args, dict)
            and args.get("include_catalog") is True
            for name, args in t["tool_calls"]
        )
        # Also check the pre-recall (the synthetic tool_call before LLM iterations)
        # — agent.py:108 sets include_catalog=True on the pre-recall.
        # That counts as catalog federation too.
        mentions_warranty = ("5-year" in t["text"].lower()
                             or "5 year" in t["text"].lower()
                             or "warranty" in t["text"].lower())
        if used_catalog and mentions_warranty:
            return True, "agent recalled with include_catalog and mentioned warranty", [t], None
        detail = f"used_catalog: {used_catalog}; mentions warranty content: {mentions_warranty}; reply: {t['text'][:200]!r}"
        return False, detail, [t], "Verify pre-recall at agent.py:108 sets include_catalog=True; check catalog index has the doc."
    finally:
        cleanup(es, [], catalog_ids=[cat_id])


@scenario(
    "M8",
    "Durable fact captured: by in-turn write_memory OR post-turn consolidation",
)
def s_m8(es: Elasticsearch, user_id: str) -> tuple[bool, str, list[dict], str | None]:
    t = drive_turn(es, user_id=user_id, session_id="m8", history=[],
                   user_message="I just upgraded my Lumio Hub to firmware 4.2 last week.")
    facts = t["consolidation_facts"]
    cons_mentions = [
        f for f in facts
        if "firmware" in (f.get("text", "") or "").lower()
        or "4.2" in (f.get("text", "") or "")
    ]
    # An in-turn write_memory by the agent is an equally valid capture path —
    # consolidation will correctly dedup against it (and write nothing new).
    in_turn_writes = [
        args for name, args in t["tool_calls"]
        if name == "write_memory"
        and isinstance(args, dict)
        and ("firmware" in (args.get("text") or "").lower()
             or "4.2" in (args.get("text") or ""))
    ]
    if cons_mentions or in_turn_writes:
        return True, f"fact captured: consolidation={len(cons_mentions)}, in-turn writes={len(in_turn_writes)}", [t], None
    detail = (
        f"no firmware/4.2 fact captured anywhere; "
        f"consolidation_facts={len(facts)}, "
        f"in-turn writes={[a.get('text','') for n,a in t['tool_calls'] if n=='write_memory']}"
    )
    return False, detail, [t], "Neither consolidation nor in-turn write_memory captured the durable claim. Investigate consolidation prompt or system_prompt's write-on-reveal rule."


@scenario(
    "M9",
    "Empty user message: agent loop completes without crashing",
)
def s_m9(es: Elasticsearch, user_id: str) -> tuple[bool, str, list[dict], str | None]:
    try:
        t = drive_turn(es, user_id=user_id, session_id="m9", history=[],
                       user_message="")
        return True, f"empty-message turn completed; reply length={len(t['text'])}; reply: {t['text'][:100]!r}", [t], None
    except Exception as exc:  # noqa: BLE001
        return False, f"raised {type(exc).__name__}: {exc}", [], \
            "Add an empty-message guard at the top of run_turn — or accept empty messages explicitly."


# ---------------------------------------------------------------------------
# Runner + report
# ---------------------------------------------------------------------------

def run_all() -> tuple[list[MultiTurnResult], list[str]]:
    es = get_es_client()
    ts = int(time.time())

    print(f"Running {len(SCENARIOS)} multi-turn agent scenarios.")
    print("(Each turn makes real LLM calls; expect 3-6 minutes total.)\n")

    results: list[MultiTurnResult] = []
    user_ids: list[str] = []

    for name, description, func in SCENARIOS:
        user_id = f"agent_stress_{ts}_{name.lower()}"
        user_ids.append(user_id)
        print(f"  [{name}] {description}...", end=" ", flush=True)
        start = time.time()
        try:
            passed, detail, turns, fix = func(es, user_id)
        except Exception as exc:  # noqa: BLE001
            passed = False
            detail = f"UNCAUGHT {type(exc).__name__}: {exc}\n{traceback.format_exc()}"
            turns = []
            fix = "Scenario raised an unexpected exception. See traceback in report."
        elapsed = time.time() - start
        results.append(MultiTurnResult(
            name=name, description=description, passed=passed,
            detail=detail, turns=turns, fix_suggestion=fix,
        ))
        print(f"{'PASS' if passed else 'FAIL'}  ({elapsed:.1f}s)")

    return results, user_ids


def write_report(results: list[MultiTurnResult]) -> Path:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = REPORT_DIR / f"agent_stress_test_report-{ts}.md"

    passed = sum(1 for r in results if r.passed)
    failed = len(results) - passed

    lines: list[str] = []
    lines.append(f"# Atlas Agent Stress Test Report — {ts}\n")
    lines.append(f"**Total:** {len(results)}  |  **Passed:** {passed}  |  **Failed:** {failed}\n")

    lines.append("\n## Summary\n")
    for r in results:
        mark = "✅" if r.passed else "❌"
        lines.append(f"- {mark} **{r.name}** — {r.description}")

    failures = [r for r in results if not r.passed]
    if failures:
        lines.append("\n## Failures with fix suggestions\n")
        for r in failures:
            lines.append(f"### {r.name} — {r.description}\n")
            lines.append(f"**Detail:**\n```\n{r.detail}\n```\n")
            if r.fix_suggestion:
                lines.append(f"**Fix plan:** {r.fix_suggestion}\n")

    lines.append("\n## Per-scenario detail\n")
    for r in results:
        mark = "✅" if r.passed else "❌"
        lines.append(f"\n### {mark} {r.name} — {r.description}\n")
        lines.append(f"**Result:** {r.detail}\n")
        if r.turns:
            for i, t in enumerate(r.turns, start=1):
                lines.append(f"**Turn {i}** — user: `{t.get('user_message','')[:120]}`")
                tool_names = [n for n, _ in t.get("tool_calls", [])]
                lines.append(f"- tool_calls: {tool_names}")
                lines.append(f"- memory_writes: {len(t.get('memory_writes', []))}")
                lines.append(f"- consolidation_facts: {len(t.get('consolidation_facts', []))}")
                reply = (t.get("text") or "").strip()
                lines.append(f"- reply ({len(reply)} chars): `{reply[:300]}{'...' if len(reply) > 300 else ''}`")

    path.write_text("\n".join(lines) + "\n")
    return path


def main() -> int:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")

    results, user_ids = run_all()

    # Cleanup all test users
    es = get_es_client()
    print("\nCleaning up test users...")
    cleanup(es, user_ids)

    path = write_report(results)
    passed = sum(1 for r in results if r.passed)
    failed = len(results) - passed
    print(f"\n=== Summary ===")
    print(f"Total: {len(results)}  Passed: {passed}  Failed: {failed}")
    print(f"Report: {path}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
