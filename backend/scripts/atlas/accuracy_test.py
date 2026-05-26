"""Deep accuracy tests for Atlas: precision recall, noise resistance,
quantitative preservation, adversarial isolation, long-context multi-turn,
and cross-bucket reasoning.

Usage:
  cd backend && uv run python -m scripts.atlas.accuracy_test
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
from app.atlas.memory.operations import recall_memory, write_memory
from app.atlas.tools import dispatch

logger = logging.getLogger(__name__)

REPORT_DIR = Path(__file__).resolve().parents[2] / "data"


# ---------------------------------------------------------------------------
# Result type + registry
# ---------------------------------------------------------------------------

@dataclass
class AccuracyResult:
    name: str
    category: str
    description: str
    passed: bool
    detail: str
    fix_suggestion: str | None = None


SCENARIOS: list[tuple[str, str, str, Callable]] = []


def scenario(name: str, category: str, description: str):
    def decorator(func: Callable):
        SCENARIOS.append((name, category, description, func))
        return func
    return decorator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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
            logger.warning("cleanup failed: %s", exc)
    for cid in catalog_ids or []:
        try:
            es.delete(index=INDEX_CATALOG, id=cid, refresh=True)
        except Exception:  # noqa: BLE001
            pass


def drive_turn(
    es: Elasticsearch,
    *,
    user_id: str,
    session_id: str,
    history: list[dict[str, Any]],
    user_message: str,
) -> dict[str, Any]:
    events = list(run_turn(
        es, user_id=user_id, session_id=session_id,
        history=list(history), user_message=user_message,
    ))
    return {
        "user_message": user_message,
        "text": "".join(e.get("text", "") for e in events if e.get("event") == "text_chunk"),
        "tool_calls": [(e.get("name"), e.get("arguments") or {}) for e in events if e.get("event") == "tool_call"],
        "tool_results": [(e.get("name"), e.get("result")) for e in events if e.get("event") == "tool_result"],
        "memory_writes": [e for e in events if e.get("event") == "memory_write"],
        "consolidation_facts": [e for e in events if e.get("event") == "consolidation_fact"],
        "events": events,
    }


# ---------------------------------------------------------------------------
# P. Precision recall
# ---------------------------------------------------------------------------

@scenario("P1", "P. Precision recall",
          "Three-level supersession chain: current Hub wins, prior versions hidden")
def s_p1(es: Elasticsearch, user_a: str, user_b: str) -> tuple[bool, str, str | None]:
    v1 = write_memory(es, user_id=user_a, memory_type="semantic",
                     text="User owns a Lumio Hub v1.",
                     fact_type="identity", refresh=True)
    v2 = write_memory(es, user_id=user_a, memory_type="semantic",
                     text="User owns a Lumio Hub v2.",
                     fact_type="identity",
                     supersedes_id=v1["id"], contradiction="natural", refresh=True)
    v3 = write_memory(es, user_id=user_a, memory_type="semantic",
                     text="User owns a Lumio Hub v3.",
                     fact_type="identity",
                     supersedes_id=v2["id"], contradiction="natural", refresh=True)
    hits = recall_memory(es, query="what hub do I have", user_id=user_a, k=10)
    ids = [h["id"] for h in hits]
    if v3["id"] in ids and v1["id"] not in ids and v2["id"] not in ids:
        rank = ids.index(v3["id"]) + 1
        return True, f"current Hub v3 surfaced at rank {rank}; v1 and v2 hidden", None
    return False, f"v1 in hits: {v1['id'] in ids}, v2 in hits: {v2['id'] in ids}, v3 in hits: {v3['id'] in ids}", \
        "Check the must_not exists field=superseded_by filter at operations.py:307."


@scenario("P2", "P. Precision recall",
          "Distinct facts across topics: location-query picks location fact")
def s_p2(es: Elasticsearch, user_a: str, user_b: str) -> tuple[bool, str, str | None]:
    facts = {
        "location": "User lives in Edinburgh in a Georgian townhouse.",
        "hub": "User owns a Lumio Hub v3 with firmware 4.2.",
        "allergy": "User is allergic to nickel and avoids metal jewelry.",
        "work": "User works remotely as a software architect.",
        "pet": "User has a Labrador retriever named Bramble.",
    }
    ids = {}
    for tag, text in facts.items():
        w = write_memory(es, user_id=user_a, memory_type="semantic",
                        text=text, fact_type="identity", refresh=True)
        ids[tag] = w["id"]
    hits = recall_memory(es, query="where does the user live", user_id=user_a, k=5)
    hit_ids = [h["id"] for h in hits]
    if hit_ids and hit_ids[0] == ids["location"]:
        return True, f"location fact ranks #1 of {len(hits)} hits", None
    rank_location = (hit_ids.index(ids["location"]) + 1) if ids["location"] in hit_ids else None
    return False, f"location fact rank: {rank_location}; top hit: {hits[0]['source'].get('text','')[:80] if hits else 'none'}", \
        "Reranker should pick the location-relevant fact; investigate Jina v2 scoring on this query."


# ---------------------------------------------------------------------------
# N. Noise resistance
# ---------------------------------------------------------------------------

@scenario("N1", "N. Noise resistance",
          "Allergy needle survives 30 unrelated episodic noise events")
def s_n1(es: Elasticsearch, user_a: str, user_b: str) -> tuple[bool, str, str | None]:
    noise_texts = [
        "Just dialed in to the office.", "Looking at firmware notes.",
        "Reviewing my Zigbee mesh layout.", "Thanks, that helps.",
        "Yes, the LED is flashing red.", "Hub v3 is connected.",
        "What's the weather like today?", "Trying a factory reset.",
        "The kitchen bulb is offline.", "Updated to firmware 3.9.",
        "Bridge restarted overnight.", "Motion sensor seems flaky.",
        "Looking at the dashboard now.", "Bulbs in the bedroom are fine.",
        "Power outage yesterday.", "Garage door opener stopped working.",
        "App says no devices found.", "Cleared the cache.",
        "Sensor stayed yellow for a while.", "Trying a different SSID.",
        "Reboot didn't help.", "OS is on 17.4.", "Mesh is okay now.",
        "Smart bulb stayed white.", "Battery low alert.",
        "Garage works again.", "Bridge stayed online overnight.",
        "Doorbell triggered at 11pm.", "Lots of devices online.",
        "Cleared notifications.",
    ]
    for text in noise_texts:
        write_memory(es, user_id=user_a, memory_type="episodic", text=text,
                    session_id="noise", event_type="user_message",
                    role="user", refresh=False)  # batch; refresh once at end
    es.indices.refresh(index=INDEX_EPISODIC)
    needle = write_memory(es, user_id=user_a, memory_type="semantic",
                         text="User is allergic to nickel and avoids any nickel-coated metal hardware.",
                         fact_type="constraint", refresh=True)
    hits = recall_memory(es, query="does the user have any metal allergies", user_id=user_a, k=5)
    ids = [h["id"] for h in hits]
    if needle["id"] in ids:
        rank = ids.index(needle["id"]) + 1
        return True, f"allergy needle found at rank {rank} of 5 (corpus: 30 noise + 1 needle)", None
    return False, f"allergy needle NOT in top 5; top hit: {hits[0]['source'].get('text','')[:80] if hits else 'none'}", \
        "Hybrid + reranker should rescue this. Check if too much noise drowned the dense leg's score."


# ---------------------------------------------------------------------------
# Q. Quantitative preservation
# ---------------------------------------------------------------------------

@scenario("Q1", "Q. Quantitative preservation",
          "Exact quantity '12' preserved through write→recall")
def s_q1(es: Elasticsearch, user_a: str, user_b: str) -> tuple[bool, str, str | None]:
    text = "User owns exactly 12 Lumio Smart Bulbs."
    w = write_memory(es, user_id=user_a, memory_type="semantic", text=text,
                    fact_type="identity", refresh=True)
    hits = recall_memory(es, query="how many bulbs does the user own", user_id=user_a, k=5)
    matches = [h for h in hits if h["id"] == w["id"]]
    if matches and "12" in matches[0]["source"].get("text", ""):
        return True, f"quantity '12' preserved in recalled text: {matches[0]['source']['text'][:80]!r}", None
    return False, f"fact not found OR '12' missing; top hit: {hits[0]['source'].get('text','')[:80] if hits else 'none'}", \
        "Index mapping should not transform numeric tokens; this should never fail. Check episodic.json text field analyzer."


@scenario("Q2", "Q. Quantitative preservation",
          "Exact date '24 May 2026' preserved through write→recall")
def s_q2(es: Elasticsearch, user_a: str, user_b: str) -> tuple[bool, str, str | None]:
    text = "Firmware 4.2 was installed on 24 May 2026 after a planned maintenance window."
    w = write_memory(es, user_id=user_a, memory_type="semantic", text=text,
                    fact_type="world", refresh=True)
    hits = recall_memory(es, query="when was firmware 4.2 installed", user_id=user_a, k=5)
    matches = [h for h in hits if h["id"] == w["id"]]
    if matches and "24 May 2026" in matches[0]["source"].get("text", ""):
        return True, f"date '24 May 2026' preserved", None
    return False, f"fact not found OR date missing; recalled text: {matches[0]['source'].get('text','')[:120] if matches else 'no match'!r}", \
        "Should never fail. Check serialization of the text field through write_memory."


@scenario("Q3", "Q. Quantitative preservation",
          "Exact version string '4.2.1-beta3' preserved")
def s_q3(es: Elasticsearch, user_a: str, user_b: str) -> tuple[bool, str, str | None]:
    text = "User is currently on app version 4.2.1-beta3 (TestFlight build)."
    w = write_memory(es, user_id=user_a, memory_type="semantic", text=text,
                    fact_type="identity", refresh=True)
    hits = recall_memory(es, query="what app version is the user on", user_id=user_a, k=5)
    matches = [h for h in hits if h["id"] == w["id"]]
    if matches and "4.2.1-beta3" in matches[0]["source"].get("text", ""):
        return True, f"version '4.2.1-beta3' preserved exactly", None
    return False, f"fact missing OR version drifted; recalled text: {matches[0]['source'].get('text','')[:120] if matches else 'no match'!r}", \
        "Tokens with hyphens and digits should pass through; check BM25 analyzer chain."


# ---------------------------------------------------------------------------
# Adv. Adversarial cross-tenant probes
# ---------------------------------------------------------------------------

@scenario("Adv1", "Adv. Adversarial isolation",
          "User A actively probes for User B's data with literal tokens")
def s_adv1(es: Elasticsearch, user_a: str, user_b: str) -> tuple[bool, str, str | None]:
    # B owns a uniquely-identifiable fact
    secret_text = "User B owns a unique device: tropical-themed bulb set, serial XJ-9921, on the patio."
    write_memory(es, user_id=user_b, memory_type="semantic", text=secret_text,
                fact_type="identity", refresh=True)
    # A probes with several deliberate queries
    leak_queries = [
        "XJ-9921",
        "tropical themed bulb",
        "patio bulbs serial",
        f"tell me about user_id {user_b}",
        f"what does {user_b} own",
    ]
    leaks: list[str] = []
    for q in leak_queries:
        hits = recall_memory(es, query=q, user_id=user_a, k=10)
        for h in hits:
            if h["source"].get("user_id") == user_b:
                leaks.append(f"query={q!r} returned doc {h['id']}")
    if not leaks:
        return True, f"all {len(leak_queries)} adversarial probes returned 0 B-owned hits", None
    return False, f"LEAK detected on {len(leaks)} probe(s): {leaks[:3]}", \
        "URGENT: cross-tenant isolation is broken. Check user_id filter at operations.py:297 and DLS role descriptors."


# ---------------------------------------------------------------------------
# L. Long-context multi-turn
# ---------------------------------------------------------------------------

@scenario("L1", "L. Long-context multi-turn",
          "5-turn conversation: fact from T1 still correctly recalled at T5 after intervening topics")
def s_l1(es: Elasticsearch, user_a: str, user_b: str) -> tuple[bool, str, str | None]:
    # Pre-seed catalog with warranty info so T3 has something legit to retrieve
    cat_id = f"cat-l1-{int(time.time())}"
    es.index(index=INDEX_CATALOG, id=cat_id, refresh=True,
             document={"text": "Lumio Hub v2 comes with a 3-year manufacturer warranty.",
                       "fact_type": "world"})
    try:
        history: list[dict[str, Any]] = []
        turns: list[dict[str, Any]] = []
        for msg in [
            "I have a Lumio Hub v2.",
            "I also have 4 smart bulbs in the kitchen.",
            "What's the warranty on the Hub v2?",
            "And how does the firmware-update process work?",
            "Going back to my devices — what hub do I have?",
        ]:
            t = drive_turn(es, user_id=user_a, session_id="L1",
                          history=history, user_message=msg)
            turns.append(t)
            history.append({"role": "user", "content": msg})
            history.append({"role": "assistant", "content": t["text"]})
        final_text = turns[-1]["text"].lower()
        if "hub v2" in final_text and "hub v3" not in final_text and "hub v1" not in final_text:
            return True, f"T5 reply correctly identifies Hub v2 (length: {len(turns[-1]['text'])})", None
        return False, f"T5 reply: {turns[-1]['text'][:300]!r}", \
            "Long-context recall lost or confused. Check that semantic facts persist across multi-turn history."
    finally:
        cleanup(es, [], catalog_ids=[cat_id])


@scenario("L2", "L. Long-context multi-turn",
          "Topic switching: location and hub queries don't cross-contaminate")
def s_l2(es: Elasticsearch, user_a: str, user_b: str) -> tuple[bool, str, str | None]:
    history: list[dict[str, Any]] = []
    turns: list[dict[str, Any]] = []
    for msg in [
        "I live in Bristol.",
        "I have a Lumio Hub v3.",
        "Where do I live?",
        "What hub do I have?",
    ]:
        t = drive_turn(es, user_id=user_a, session_id="L2",
                      history=history, user_message=msg)
        turns.append(t)
        history.append({"role": "user", "content": msg})
        history.append({"role": "assistant", "content": t["text"]})
    t3_lower = turns[2]["text"].lower()
    t4_lower = turns[3]["text"].lower()
    t3_correct = "bristol" in t3_lower
    t4_correct = "hub v3" in t4_lower
    if t3_correct and t4_correct:
        return True, f"T3 (location) and T4 (hub) both correct, no cross-contamination", None
    return False, f"T3 has bristol: {t3_correct}; T4 has hub v3: {t4_correct}; T3 reply: {turns[2]['text'][:150]!r}; T4 reply: {turns[3]['text'][:150]!r}", \
        "Agent confused between topics — check that recall queries on T3/T4 are appropriately scoped."


# ---------------------------------------------------------------------------
# X. Cross-bucket reasoning
# ---------------------------------------------------------------------------

@scenario("X1", "X. Cross-bucket reasoning",
          "Agent combines semantic context + procedural playbook in one response")
def s_x1(es: Elasticsearch, user_a: str, user_b: str) -> tuple[bool, str, str | None]:
    write_memory(es, user_id=user_a, memory_type="semantic",
                text="User's living room has thick Victorian walls that strongly attenuate Zigbee signal.",
                fact_type="world", refresh=True)
    write_memory(es, user_id=user_a, memory_type="procedural",
                text="Zigbee disconnect after power outage: change channel to 25",
                name="zigbee_channel_25_fix",
                description="When devices keep disconnecting due to Zigbee interference, change channel to 25.",
                steps=[
                    {"order": 1, "instruction": "Open the Lumio app's network settings", "tool": "ask_user"},
                    {"order": 2, "instruction": "Change Zigbee channel to channel 25", "tool": "ask_user"},
                    {"order": 3, "instruction": "Wait 30 seconds for devices to reconnect", "tool": "ask_user"},
                ],
                refresh=True)
    t = drive_turn(es, user_id=user_a, session_id="X1", history=[],
                  user_message="My smart bulbs keep disconnecting in the living room. What should I do?")
    text_l = t["text"].lower()
    mentions_walls = ("victorian" in text_l or "thick wall" in text_l
                      or "attenuat" in text_l or "interference" in text_l)
    mentions_channel = ("channel 25" in text_l or "change the channel" in text_l
                        or "zigbee channel" in text_l)
    if mentions_walls and mentions_channel:
        return True, f"reply combines wall context AND channel-change procedure", None
    return False, f"walls mentioned: {mentions_walls}, channel mentioned: {mentions_channel}; reply: {t['text'][:300]!r}", \
        "Agent isn't combining buckets. Check that recall returns both semantic and procedural hits for this query."


# ---------------------------------------------------------------------------
# Runner + report
# ---------------------------------------------------------------------------

def run_all() -> tuple[list[AccuracyResult], list[str]]:
    es = get_es_client()
    ts = int(time.time())
    user_a = f"acc_a_{ts}"
    user_b = f"acc_b_{ts}"
    print(f"Running {len(SCENARIOS)} accuracy scenarios as {user_a}, {user_b}.\n")

    results: list[AccuracyResult] = []
    for name, category, description, func in SCENARIOS:
        print(f"  [{name}] {description}...", end=" ", flush=True)
        start = time.time()
        try:
            passed, detail, fix = func(es, user_a, user_b)
        except Exception as exc:  # noqa: BLE001
            passed = False
            detail = f"UNCAUGHT {type(exc).__name__}: {exc}\n{traceback.format_exc()}"
            fix = "Scenario raised. See traceback in report."
        elapsed = time.time() - start
        results.append(AccuracyResult(
            name=name, category=category, description=description,
            passed=passed, detail=detail, fix_suggestion=fix,
        ))
        print(f"{'PASS' if passed else 'FAIL'}  ({elapsed:.1f}s)")

    return results, [user_a, user_b]


def write_report(results: list[AccuracyResult]) -> Path:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = REPORT_DIR / f"accuracy_test_report-{ts}.md"

    passed = sum(1 for r in results if r.passed)
    failed = len(results) - passed
    by_cat: dict[str, list[AccuracyResult]] = {}
    for r in results:
        by_cat.setdefault(r.category, []).append(r)

    lines: list[str] = []
    lines.append(f"# Atlas Accuracy Test Report — {ts}\n")
    lines.append(f"**Total:** {len(results)}  |  **Passed:** {passed}  |  **Failed:** {failed}\n")

    lines.append("\n## Summary by category\n")
    for cat in sorted(by_cat):
        items = by_cat[cat]
        p = sum(1 for r in items if r.passed)
        fail_names = [r.name for r in items if not r.passed]
        line = f"- **{cat}**: {p}/{len(items)}"
        if fail_names:
            line += f" — failed: {', '.join(fail_names)}"
        lines.append(line)

    failures = [r for r in results if not r.passed]
    if failures:
        lines.append("\n## Failures with fix suggestions\n")
        for r in failures:
            lines.append(f"### {r.name} — {r.description}\n")
            lines.append(f"**Category:** {r.category}\n")
            lines.append(f"**Detail:**\n```\n{r.detail}\n```\n")
            if r.fix_suggestion:
                lines.append(f"**Fix plan:** {r.fix_suggestion}\n")
    else:
        lines.append("\n## Failures\n\n_None — all accuracy scenarios passed._\n")

    lines.append("\n## Per-scenario detail\n")
    for cat in sorted(by_cat):
        lines.append(f"\n### {cat}\n")
        for r in by_cat[cat]:
            mark = "✅" if r.passed else "❌"
            lines.append(f"- {mark} **{r.name}** — {r.description}")
            lines.append(f"  - {r.detail}")

    path.write_text("\n".join(lines) + "\n")
    return path


def main() -> int:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")
    results, user_ids = run_all()
    es = get_es_client()
    print("\nCleaning up...")
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
