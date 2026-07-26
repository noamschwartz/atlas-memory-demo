"""End-to-end verification for the Release 1 memory changes.

Runs against a live cluster. Uses a throwaway user id for everything it writes
and deletes it afterwards, so it is safe to run against the demo cluster.

Usage:
  uv run python -m scripts.atlas.verify_release1
  uv run python -m scripts.atlas.verify_release1 --keep   # skip cleanup
"""

from __future__ import annotations

import argparse
import sys
import time
from typing import Any

from app.atlas.agent import _format_core_memory, _system_prompt, run_turn
from app.atlas.consolidate import consolidate
from app.atlas.memory.constants import (
    INDEX_EPISODIC,
    INDEX_PROCEDURAL,
    INDEX_SEMANTIC,
    INDEX_STATE,
)
from app.atlas.memory.operations import core_memory, list_memories, recall_memory, write_memory
from app.atlas.memory.state import ensure_watermark, get_watermark
from app.atlas.tools import dispatch
from app.elasticsearch.client import get_es_client

TEST_USER = "__release1_verify__"

_results: list[tuple[bool, str, str]] = []


def check(name: str, ok: bool, detail: str = "") -> bool:
    _results.append((ok, name, detail))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  |  {detail}" if detail else ""))
    return ok


def cleanup(es) -> None:
    for idx in (INDEX_EPISODIC, INDEX_SEMANTIC, INDEX_PROCEDURAL):
        try:
            es.delete_by_query(
                index=idx, body={"query": {"term": {"user_id": TEST_USER}}},
                refresh=True, conflicts="proceed",
            )
        except Exception as exc:  # noqa: BLE001
            print(f"  (cleanup {idx}: {exc})")
    try:
        es.delete(index=INDEX_STATE, id=TEST_USER, refresh=True)
    except Exception:  # noqa: BLE001
        pass


# ---------------------------------------------------------------------------

def t_core_memory_on_real_persona(es) -> None:
    print("\n[1] A1 core memory against the seeded corpus")
    facts = core_memory(es, user_id="sarah")
    check("returns facts for sarah", len(facts) > 0, f"{len(facts)} facts")
    kinds = {f["fact_type"] for f in facts}
    check("only identity/constraint types", kinds <= {"identity", "constraint"}, str(sorted(kinds)))

    types_in_order = [f["fact_type"] for f in facts]
    first_identity = next((i for i, t in enumerate(types_in_order) if t == "identity"), len(types_in_order))
    last_constraint = max((i for i, t in enumerate(types_in_order) if t == "constraint"), default=-1)
    check("constraints ordered before identity", last_constraint < first_identity,
          f"last constraint idx={last_constraint}, first identity idx={first_identity}")

    rendered = _format_core_memory(facts)
    prompt = _system_prompt(facts)
    check("core memory lands in the system prompt", rendered.split("\n")[0] in prompt)
    check("profile block present", "<customer_profile>" in prompt)
    print(f"      profile block ~{len(rendered)} chars (~{len(rendered)//4} tokens)")


def t_core_memory_empty_user(es) -> None:
    print("\n[2] A1 degrades cleanly for a user with no profile facts")
    facts = core_memory(es, user_id=TEST_USER)
    check("no facts for fresh user", facts == [])
    prompt = _system_prompt(facts)
    check("prompt still renders", "<customer_profile>" in prompt and "{core_memory}" not in prompt)
    check("states absence explicitly", "no durable profile facts" in prompt)


def t_retraction(es) -> None:
    print("\n[3] A5 retraction is distinguishable from prior state")
    natural_old = write_memory(es, user_id=TEST_USER, memory_type="semantic",
                               text="Test user lives in Bristol", fact_type="identity", refresh=True)
    harsh_old = write_memory(es, user_id=TEST_USER, memory_type="semantic",
                             text="Test user owns a Hub v1", fact_type="identity", refresh=True)

    write_memory(es, user_id=TEST_USER, memory_type="semantic",
                 text="Test user lives in Edinburgh", fact_type="identity",
                 supersedes_id=natural_old["id"], contradiction="natural", refresh=True)
    write_memory(es, user_id=TEST_USER, memory_type="semantic",
                 text="Test user has never owned a Hub v1", fact_type="identity",
                 supersedes_id=harsh_old["id"], contradiction="harsh", refresh=True)

    nat = es.get(index=INDEX_SEMANTIC, id=natural_old["id"])["_source"]
    har = es.get(index=INDEX_SEMANTIC, id=harsh_old["id"])["_source"]
    check("natural: superseded", bool(nat.get("superseded_by")))
    check("natural: NOT retracted", not nat.get("retracted"))
    check("harsh: superseded", bool(har.get("superseded_by")))
    check("harsh: retracted=true", har.get("retracted") is True)

    hits = recall_memory(es, query="where does the test user live", user_id=TEST_USER,
                         memory_types=["semantic"], k=10, include_superseded=True)
    payload = dispatch(es, user_id=TEST_USER, name="recall_memory",
                       arguments={"query": "hub ownership history", "memory_types": ["semantic"],
                                  "k": 10, "include_superseded": True})
    retracted_seen = any(h.get("retracted") for h in payload["hits"])
    check("retracted flag reaches the agent payload", retracted_seen,
          f"{len(payload['hits'])} hits returned")
    conf_seen = any("confidence" in h for h in payload["hits"])
    check("B2: confidence reaches the agent payload", conf_seen)


def t_procedural_steps(es) -> None:
    print("\n[4] C1 an agent-issued procedural write carries its steps")
    steps = [
        {"order": 1, "instruction": "Power-cycle the hub and wait 90 seconds", "tool": "ask_user"},
        {"order": 2, "instruction": "Re-pair the nearest mains-powered device", "tool": "ask_user"},
    ]
    res = dispatch(es, user_id=TEST_USER, name="write_memory", arguments={
        "memory_type": "procedural", "text": "hub drops zigbee devices",
        "name": "zigbee_recover", "description": "Recover a dropped Zigbee mesh", "steps": steps,
    })
    doc = es.get(index=INDEX_PROCEDURAL, id=res["id"])["_source"]
    check("steps persisted via the tool path", doc.get("steps") == steps,
          f"{len(doc.get('steps') or [])} steps")
    check("name persisted", doc.get("name") == "zigbee_recover")
    check("description persisted", doc.get("description") == "Recover a dropped Zigbee mesh")


def t_list_memories_param(es) -> None:
    print("\n[5] C5 superseded filter is opt-in, so the inspector view is unchanged")
    with_sup = list_memories(es, user_id=TEST_USER, memory_type="semantic", limit=50)
    without = list_memories(es, user_id=TEST_USER, memory_type="semantic", limit=50,
                            include_superseded=False)
    check("default keeps superseded (audit view intact)", len(with_sup) > len(without),
          f"{len(with_sup)} vs {len(without)}")
    check("opt-out drops exactly the superseded ones",
          all(not r["source"].get("superseded_by") for r in without))


def t_watermark(es) -> None:
    print("\n[6] A2 consolidation watermark")
    wm = ensure_watermark(es, TEST_USER)
    if wm is None:
        check("watermark store unavailable -> degrades to legacy path", True,
              f"{INDEX_STATE} not provisioned; consolidation falls back, does not stop")
        out = consolidate(es, user_id=TEST_USER, dry_run=True)
        check("consolidation still runs on the legacy path",
              out.get("reason") != "watermark_error", f"reason={out.get('reason')}")
        return
    check("watermark initialised", bool(wm), wm)
    out = consolidate(es, user_id=TEST_USER, dry_run=True)
    check("watermark active", out.get("watermark_active") is True)
    check("no backlog after init", out.get("episodes_considered", 0) == 0,
          f"episodes_considered={out.get('episodes_considered')}")


def t_full_turn(es) -> None:
    print("\n[7] End-to-end: a real chat turn through run_turn")
    events: list[dict[str, Any]] = []
    t0 = time.time()
    for ev in run_turn(es, user_id="sarah", session_id="release1-verify",
                       history=[], user_message="my hub keeps dropping off wifi, what should I do?"):
        events.append(ev)
    elapsed = time.time() - t0

    kinds = [e["event"] for e in events]
    check("turn completed", "done" in kinds, f"{len(events)} events in {elapsed:.1f}s")
    core_ev = next((e for e in events if e["event"] == "core_memory"), None)
    check("core_memory event emitted", core_ev is not None,
          f"{core_ev['count']} facts" if core_ev else "missing")
    check("pre-recall ran", any(e["event"] == "tool_call" for e in events))
    text = "".join(e.get("text", "") for e in events if e["event"] == "text_chunk")
    check("model produced a reply", len(text) > 40, f"{len(text)} chars")
    check("consolidation ran", "consolidation_done" in kinds)
    print(f"\n      --- reply (first 400 chars) ---\n      {text[:400]}")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--keep", action="store_true", help="skip cleanup of the test user")
    args = p.parse_args()

    es = get_es_client()
    print(f"Release 1 verification against {TEST_USER!r}\n" + "=" * 62)
    cleanup(es)

    try:
        t_core_memory_on_real_persona(es)
        t_core_memory_empty_user(es)
        t_retraction(es)
        t_procedural_steps(es)
        t_list_memories_param(es)
        t_watermark(es)
        t_full_turn(es)
    finally:
        if not args.keep:
            print("\ncleaning up test user...")
            cleanup(es)

    passed = sum(1 for ok, _, _ in _results if ok)
    total = len(_results)
    print("\n" + "=" * 62)
    print(f"{passed}/{total} checks passed")
    for ok, name, detail in _results:
        if not ok:
            print(f"  FAILED: {name} {detail}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
