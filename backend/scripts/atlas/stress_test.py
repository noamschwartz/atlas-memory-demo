"""Stress test for Atlas memory: correctness + edge cases.

Exercises the memory layer's invariants — basic CRUD, contradiction handling,
multi-tenant isolation, same-turn write/recall, the new timestamp payload field,
consolidation, edge cases, and the recency signal. Produces a Markdown report
with per-scenario pass/fail and fix plans for any failures.

Usage:
  cd backend && uv run python -m scripts.atlas.stress_test
"""

from __future__ import annotations

import json
import logging
import time
import traceback
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

from elasticsearch import Elasticsearch, NotFoundError

from app.elasticsearch.client import get_es_client
from app.atlas.consolidate import consolidate
from app.atlas.memory.constants import (
    INDEX_CATALOG,
    INDEX_EPISODIC,
    INDEX_PROCEDURAL,
    INDEX_SEMANTIC,
    SUPERSEDE_CONFIDENCE_PENALTY,
)
from app.atlas.memory.operations import (
    forget_memory,
    list_memories,
    recall_memory,
    update_procedural,
    write_memory,
)
from app.atlas.tools import dispatch

logger = logging.getLogger(__name__)

REPORT_DIR = Path(__file__).resolve().parents[2] / "data"


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass
class ScenarioResult:
    name: str
    category: str
    description: str
    passed: bool
    detail: str
    fix_suggestion: str | None = None


SCENARIOS: list[tuple[str, str, str, Callable]] = []


def scenario(name: str, category: str, description: str):
    """Register a scenario function. The function receives (es, user_a, user_b)."""
    def decorator(func: Callable):
        SCENARIOS.append((name, category, description, func))
        return func
    return decorator


# ---------------------------------------------------------------------------
# Cleanup helpers
# ---------------------------------------------------------------------------

def cleanup(es: Elasticsearch, user_ids: list[str]) -> None:
    """Delete every doc belonging to the stress-test users across memory indices."""
    if not user_ids:
        return
    try:
        es.delete_by_query(
            index=",".join([INDEX_EPISODIC, INDEX_SEMANTIC, INDEX_PROCEDURAL]),
            body={"query": {"terms": {"user_id": user_ids}}},
            refresh=True,
            conflicts="proceed",
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("cleanup failed: %s", exc)


# ---------------------------------------------------------------------------
# A. Basic CRUD
# ---------------------------------------------------------------------------

@scenario("A1", "A. Basic CRUD", "Write a semantic fact and recall by text overlap")
def s_a1(es: Elasticsearch, user_a: str, user_b: str) -> tuple[bool, str, str | None]:
    text = "Sarah owns a Lumio Hub v2 and lives in Bristol."
    w = write_memory(es, user_id=user_a, memory_type="semantic", text=text,
                     fact_type="identity", refresh=True)
    hits = recall_memory(es, query="Hub v2 Bristol", user_id=user_a, k=5)
    ids = [h["id"] for h in hits]
    if w["id"] in ids:
        rank = ids.index(w["id"]) + 1
        return True, f"new doc {w['id']} found at rank {rank}", None
    return False, f"new doc {w['id']} missing from recall (got {ids[:3]})", \
        "Check _hybrid_retriever's user_id filter and reranker pass-through."


@scenario("A2", "A. Basic CRUD", "Write an episodic event and list_memories returns it")
def s_a2(es: Elasticsearch, user_a: str, user_b: str) -> tuple[bool, str, str | None]:
    text = "User: my hub keeps disconnecting."
    w = write_memory(es, user_id=user_a, memory_type="episodic", text=text,
                     session_id="stress-sess", event_type="user_message",
                     role="user", refresh=True)
    rows = list_memories(es, user_id=user_a, memory_type="episodic", limit=20)
    ids = [r["id"] for r in rows]
    if w["id"] in ids:
        return True, f"episodic doc {w['id']} present in list_memories", None
    return False, f"episodic doc {w['id']} missing from list_memories", \
        "Check list_memories filter and the episodic mapping."


@scenario("A3", "A. Basic CRUD", "Write a procedural playbook and recall by trigger")
def s_a3(es: Elasticsearch, user_a: str, user_b: str) -> tuple[bool, str, str | None]:
    trigger = "Hub disconnect after power cut on Zigbee channel"
    w = write_memory(es, user_id=user_a, memory_type="procedural", text=trigger,
                     name="zigbee_channel_fix",
                     description="Change Zigbee channel to fix disconnects after power outage",
                     steps=[{"order": 1, "instruction": "Change Zigbee channel", "tool": "ask_user"}],
                     refresh=True)
    hits = recall_memory(es, query="hub disconnect Zigbee", user_id=user_a, k=5,
                        memory_types=["procedural"])
    ids = [h["id"] for h in hits]
    if w["id"] in ids:
        return True, f"procedural {w['id']} recalled", None
    return False, f"procedural {w['id']} missing from recall", \
        "Verify procedural mapping and that trigger_text feeds the retriever."


@scenario("A4", "A. Basic CRUD", "forget_memory deletes the doc")
def s_a4(es: Elasticsearch, user_a: str, user_b: str) -> tuple[bool, str, str | None]:
    w = write_memory(es, user_id=user_a, memory_type="semantic",
                     text="Disposable fact to forget", fact_type="preference",
                     refresh=True)
    forget_memory(es, user_id=user_a, memory_type="semantic", memory_id=w["id"])
    es.indices.refresh(index=INDEX_SEMANTIC)
    try:
        es.get(index=INDEX_SEMANTIC, id=w["id"])
        return False, f"doc {w['id']} still exists after forget", \
            "forget_memory at operations.py:644 — verify es.delete is called with correct id."
    except NotFoundError:
        return True, "doc gone after forget_memory", None


# ---------------------------------------------------------------------------
# B. Contradictions
# ---------------------------------------------------------------------------

@scenario("B1", "B. Contradictions", "Natural supersession: new doc at full confidence")
def s_b1(es: Elasticsearch, user_a: str, user_b: str) -> tuple[bool, str, str | None]:
    old = write_memory(es, user_id=user_a, memory_type="semantic",
                       text="User lives in Bristol", fact_type="identity",
                       confidence=0.9, refresh=True)
    new = write_memory(es, user_id=user_a, memory_type="semantic",
                       text="User lives in Edinburgh", fact_type="identity",
                       confidence=0.9, supersedes_id=old["id"],
                       contradiction="natural", refresh=True)
    new_doc = es.get(index=INDEX_SEMANTIC, id=new["id"])["_source"]
    old_doc = es.get(index=INDEX_SEMANTIC, id=old["id"])["_source"]
    if new_doc["confidence"] == 0.9 and old_doc.get("superseded_by") == new["id"]:
        return True, f"natural: new confidence={new_doc['confidence']} (no penalty), old.superseded_by set", None
    return False, f"new confidence={new_doc['confidence']}, old.superseded_by={old_doc.get('superseded_by')}", \
        "Check operations.py:107-108 conditional penalty branch."


@scenario("B2", "B. Contradictions", "Harsh supersession applies SUPERSEDE_CONFIDENCE_PENALTY")
def s_b2(es: Elasticsearch, user_a: str, user_b: str) -> tuple[bool, str, str | None]:
    old = write_memory(es, user_id=user_a, memory_type="semantic",
                       text="User owns a Hub v2", fact_type="identity",
                       confidence=0.9, refresh=True)
    new = write_memory(es, user_id=user_a, memory_type="semantic",
                       text="User never owned a Hub v2", fact_type="identity",
                       confidence=0.9, supersedes_id=old["id"],
                       contradiction="harsh", refresh=True)
    new_doc = es.get(index=INDEX_SEMANTIC, id=new["id"])["_source"]
    expected = round(0.9 - SUPERSEDE_CONFIDENCE_PENALTY, 6)
    if abs(new_doc["confidence"] - expected) < 1e-6:
        return True, f"harsh: confidence dropped {0.9} → {new_doc['confidence']} (penalty {SUPERSEDE_CONFIDENCE_PENALTY})", None
    return False, f"expected {expected}, got {new_doc['confidence']}", \
        "Check that contradiction=='harsh' triggers the penalty branch at operations.py:107."


@scenario("B3", "B. Contradictions", "Omitting `contradiction` defaults to natural (no penalty)")
def s_b3(es: Elasticsearch, user_a: str, user_b: str) -> tuple[bool, str, str | None]:
    old = write_memory(es, user_id=user_a, memory_type="semantic",
                       text="Prefers dark mode", fact_type="preference",
                       confidence=0.85, refresh=True)
    new = write_memory(es, user_id=user_a, memory_type="semantic",
                       text="Prefers light mode", fact_type="preference",
                       confidence=0.85, supersedes_id=old["id"], refresh=True)
    new_doc = es.get(index=INDEX_SEMANTIC, id=new["id"])["_source"]
    if abs(new_doc["confidence"] - 0.85) < 1e-6:
        return True, f"omit-contradiction: confidence preserved at {new_doc['confidence']}", None
    return False, f"expected 0.85, got {new_doc['confidence']}", \
        "operations.py:107 should only apply penalty when contradiction=='harsh' (None should be natural)."


@scenario("B4", "B. Contradictions", "3-level supersession chain (abc → xyz → pqr)")
def s_b4(es: Elasticsearch, user_a: str, user_b: str) -> tuple[bool, str, str | None]:
    abc = write_memory(es, user_id=user_a, memory_type="semantic",
                       text="Lives in Bristol", fact_type="identity", refresh=True)
    xyz = write_memory(es, user_id=user_a, memory_type="semantic",
                       text="Lives in Edinburgh", fact_type="identity",
                       supersedes_id=abc["id"], contradiction="natural", refresh=True)
    pqr = write_memory(es, user_id=user_a, memory_type="semantic",
                       text="Lives in Glasgow", fact_type="identity",
                       supersedes_id=xyz["id"], contradiction="natural", refresh=True)
    abc_doc = es.get(index=INDEX_SEMANTIC, id=abc["id"])["_source"]
    xyz_doc = es.get(index=INDEX_SEMANTIC, id=xyz["id"])["_source"]
    pqr_doc = es.get(index=INDEX_SEMANTIC, id=pqr["id"])["_source"]
    if (abc_doc.get("superseded_by") == xyz["id"]
        and xyz_doc.get("superseded_by") == pqr["id"]
        and pqr_doc.get("superseded_by") is None):
        return True, f"chain intact: abc→xyz→pqr; pqr is current", None
    return False, (
        f"chain broken: abc.superseded_by={abc_doc.get('superseded_by')}, "
        f"xyz.superseded_by={xyz_doc.get('superseded_by')}, "
        f"pqr.superseded_by={pqr_doc.get('superseded_by')}"
    ), "Check the supersedes-old soft-mark step at operations.py:128-142."


@scenario("B5", "B. Contradictions", "Recall filters out superseded docs (only current surfaces)")
def s_b5(es: Elasticsearch, user_a: str, user_b: str) -> tuple[bool, str, str | None]:
    old = write_memory(es, user_id=user_a, memory_type="semantic",
                       text="Owner has a Hub v1 specifically", fact_type="identity", refresh=True)
    new = write_memory(es, user_id=user_a, memory_type="semantic",
                       text="Owner has a Hub v3 now", fact_type="identity",
                       supersedes_id=old["id"], contradiction="natural", refresh=True)
    hits = recall_memory(es, query="Hub owner v1 v3", user_id=user_a, k=10)
    ids = [h["id"] for h in hits]
    if old["id"] not in ids and new["id"] in ids:
        return True, f"superseded {old['id']} hidden, current {new['id']} present", None
    return False, f"superseded={old['id']} in_recall={old['id'] in ids}; current={new['id']} in_recall={new['id'] in ids}", \
        "Verify the must_not exists field=superseded_by filter at operations.py:307."


@scenario("B6", "B. Contradictions", "Audit chain reachable via direct es.get on superseded doc")
def s_b6(es: Elasticsearch, user_a: str, user_b: str) -> tuple[bool, str, str | None]:
    old = write_memory(es, user_id=user_a, memory_type="semantic",
                       text="iOS 17.2", fact_type="identity", refresh=True)
    new = write_memory(es, user_id=user_a, memory_type="semantic",
                       text="iOS 17.4", fact_type="identity",
                       supersedes_id=old["id"], contradiction="natural", refresh=True)
    doc = es.get(index=INDEX_SEMANTIC, id=old["id"])["_source"]
    if doc.get("superseded_by") == new["id"] and "superseded_at" in doc:
        return True, f"audit fields intact on {old['id']}: superseded_by, superseded_at", None
    return False, f"audit fields missing: {doc.get('superseded_by')}, {doc.get('superseded_at')}", \
        "Check write_memory's update at operations.py:132-138."


# ---------------------------------------------------------------------------
# C. Multi-tenant isolation
# ---------------------------------------------------------------------------

@scenario("C1", "C. Isolation", "A writes, B recalls — zero leak")
def s_c1(es: Elasticsearch, user_a: str, user_b: str) -> tuple[bool, str, str | None]:
    secret = "Private fact: user A owns a tropical-themed smart-lamp set"
    w = write_memory(es, user_id=user_a, memory_type="semantic", text=secret,
                     fact_type="identity", refresh=True)
    b_hits = recall_memory(es, query="tropical smart lamp", user_id=user_b, k=10)
    a_owns = [h["id"] for h in b_hits if h["source"].get("user_id") == user_a]
    if not a_owns:
        return True, f"B's recall returned {len(b_hits)} hits, none from A", None
    return False, f"LEAK: B saw A's docs: {a_owns}", \
        "URGENT: check _hybrid_retriever's user_id filter at operations.py:297."


@scenario("C2", "C. Isolation", "forget on another user's doc returns unauthorized")
def s_c2(es: Elasticsearch, user_a: str, user_b: str) -> tuple[bool, str, str | None]:
    w = write_memory(es, user_id=user_a, memory_type="semantic",
                     text="A-only fact", fact_type="identity", refresh=True)
    result = forget_memory(es, user_id=user_b, memory_type="semantic", memory_id=w["id"])
    if result.get("deleted") is False and result.get("reason") == "unauthorized":
        # Confirm the doc is still there
        try:
            es.get(index=INDEX_SEMANTIC, id=w["id"])
            return True, f"forget rejected: {result['reason']}; doc still exists", None
        except NotFoundError:
            return False, "doc was deleted despite ownership check", \
                "Critical: forget_memory at operations.py:651 should reject before es.delete."
    return False, f"forget result unexpected: {result}", \
        "forget_memory should return reason='unauthorized' when user_id mismatch."


@scenario("C3", "C. Isolation", "Catalog docs visible when include_catalog=True")
def s_c3(es: Elasticsearch, user_a: str, user_b: str) -> tuple[bool, str, str | None]:
    # Write a temp catalog doc (no user_id) to ensure there's something to find
    cat_id = f"stress-cat-{int(time.time())}"
    es.index(index=INDEX_CATALOG, id=cat_id,
             document={"text": "Lumio Hub v2 supports Zigbee 3.0 and Matter via firmware 3.x",
                       "fact_type": "world"},
             refresh=True)
    try:
        hits = recall_memory(es, query="Lumio Hub Zigbee Matter firmware", user_id=user_a,
                           k=10, include_catalog=True)
        cat_hits = [h for h in hits if h["index"] == INDEX_CATALOG]
        if cat_hits:
            return True, f"catalog hits surfaced: {len(cat_hits)}", None
        return False, f"include_catalog=True but no catalog hits in {len(hits)} total", \
            "Check _user_or_catalog_filter at operations.py:152."
    finally:
        try:
            es.delete(index=INDEX_CATALOG, id=cat_id, refresh=True)
        except Exception:  # noqa: BLE001
            pass


# ---------------------------------------------------------------------------
# D. Same-turn write→recall (refresh=True propagation)
# ---------------------------------------------------------------------------

@scenario("D1", "D. Same-turn", "Write then immediate recall sees the new doc")
def s_d1(es: Elasticsearch, user_a: str, user_b: str) -> tuple[bool, str, str | None]:
    # Use a unique marker so we know the doc is fresh
    marker = f"stress-marker-{int(time.time()*1000)}"
    text = f"Customer mentioned distinctive token {marker} in this turn"
    w = write_memory(es, user_id=user_a, memory_type="semantic", text=text,
                     fact_type="world", refresh=True)
    hits = recall_memory(es, query=marker, user_id=user_a, k=5)
    ids = [h["id"] for h in hits]
    if w["id"] in ids:
        return True, f"refresh=True propagated: doc {w['id']} immediately visible", None
    return False, f"new doc {w['id']} not visible in immediate recall (got {ids[:3]})", \
        "URGENT: refresh=True at write_memory may not be reaching the index. Check tools.py:208 / operations.py:134."


# ---------------------------------------------------------------------------
# E. Recall payload — timestamp field (new fix)
# ---------------------------------------------------------------------------

@scenario("E1", "E. Timestamp payload", "dispatch's compact payload includes `timestamp` key")
def s_e1(es: Elasticsearch, user_a: str, user_b: str) -> tuple[bool, str, str | None]:
    w = write_memory(es, user_id=user_a, memory_type="semantic",
                     text="Marker for E1 test", fact_type="world", refresh=True)
    result = dispatch(es, user_id=user_a, name="recall_memory",
                      arguments={"query": "Marker E1", "k": 5})
    hits = result["hits"]
    if not hits:
        return False, "dispatch returned no hits", "First check A1 passes."
    missing = [h["id"] for h in hits if "timestamp" not in h]
    if not missing:
        return True, f"all {len(hits)} hits include `timestamp`", None
    return False, f"hits missing timestamp field: {missing}", \
        "Verify tools.py:192-197 — the timestamp key should be in every compact hit dict."


@scenario("E2", "E. Timestamp payload", "Episodic timestamp = doc's event time")
def s_e2(es: Elasticsearch, user_a: str, user_b: str) -> tuple[bool, str, str | None]:
    w = write_memory(es, user_id=user_a, memory_type="episodic",
                     text="E2 marker episodic", session_id="stress",
                     event_type="user_message", role="user", refresh=True)
    raw_doc = es.get(index=INDEX_EPISODIC, id=w["id"])["_source"]
    result = dispatch(es, user_id=user_a, name="recall_memory",
                      arguments={"query": "E2 marker", "k": 10, "memory_types": ["episodic"]})
    hits = [h for h in result["hits"] if h["id"] == w["id"]]
    if not hits:
        return False, f"episodic {w['id']} not in recall", "First check A2 passes."
    hit_ts = hits[0].get("timestamp")
    if hit_ts == raw_doc.get("timestamp"):
        return True, f"episodic timestamp matches: {hit_ts}", None
    return False, f"hit timestamp={hit_ts}, doc.timestamp={raw_doc.get('timestamp')}", \
        "tools.py:192-197 should prefer doc['timestamp'] for episodic."


@scenario("E3", "E. Timestamp payload", "Semantic timestamp falls back to created_at")
def s_e3(es: Elasticsearch, user_a: str, user_b: str) -> tuple[bool, str, str | None]:
    w = write_memory(es, user_id=user_a, memory_type="semantic",
                     text="E3 marker semantic", fact_type="world", refresh=True)
    raw_doc = es.get(index=INDEX_SEMANTIC, id=w["id"])["_source"]
    result = dispatch(es, user_id=user_a, name="recall_memory",
                      arguments={"query": "E3 marker", "k": 10, "memory_types": ["semantic"]})
    hits = [h for h in result["hits"] if h["id"] == w["id"]]
    if not hits:
        return False, f"semantic {w['id']} not in recall", "First check A1 passes."
    hit_ts = hits[0].get("timestamp")
    if hit_ts == raw_doc.get("created_at"):
        return True, f"semantic timestamp falls back to created_at: {hit_ts}", None
    return False, f"hit timestamp={hit_ts}, doc.created_at={raw_doc.get('created_at')}", \
        "tools.py:192-197 fallback chain should be source.timestamp OR source.created_at."


# ---------------------------------------------------------------------------
# F. Consolidation
# ---------------------------------------------------------------------------

@scenario("F1", "F. Consolidation", "Seed durable episodes → consolidate writes new semantic fact(s)")
def s_f1(es: Elasticsearch, user_a: str, user_b: str) -> tuple[bool, str, str | None]:
    # Seed episodes that strongly imply a durable identity fact
    for text in [
        "I just got a new Lumio Hub v3 today.",
        "Setting up my Lumio Hub v3, the LED is flashing blue.",
        "All my devices are now connected to the Hub v3.",
    ]:
        write_memory(es, user_id=user_a, memory_type="episodic", text=text,
                    session_id="stress-cons", event_type="user_message",
                    role="user", refresh=True)
    before = list_memories(es, user_id=user_a, memory_type="semantic", limit=50)
    before_ids = {r["id"] for r in before}
    result = consolidate(es, user_id=user_a, lookback=10)
    after = list_memories(es, user_id=user_a, memory_type="semantic", limit=50)
    new_ids = [r["id"] for r in after if r["id"] not in before_ids]
    if new_ids:
        texts = [r["source"].get("text", "") for r in after if r["id"] in new_ids]
        return True, f"consolidation wrote {len(new_ids)} new facts: {texts[:2]}", None
    return False, f"consolidate produced no new facts ({result.get('reason') or 'unknown'})", \
        "Possible: LLM didn't extract a fact. Check consolidate.py:24-91 prompt rules."


@scenario("F2", "F. Consolidation", "Sparse / transient episodes → consolidate writes nothing")
def s_f2(es: Elasticsearch, user_a: str, user_b: str) -> tuple[bool, str, str | None]:
    # Pure chitchat with no durable content
    for text in [
        "Hello",
        "Yes that worked",
        "Thanks!",
    ]:
        write_memory(es, user_id=user_a, memory_type="episodic", text=text,
                    session_id="stress-sparse", event_type="user_message",
                    role="user", refresh=True)
    before = list_memories(es, user_id=user_a, memory_type="semantic", limit=50)
    before_ids = {r["id"] for r in before}
    result = consolidate(es, user_id=user_a, lookback=3)
    after = list_memories(es, user_id=user_a, memory_type="semantic", limit=50)
    new_ids = [r["id"] for r in after if r["id"] not in before_ids]
    if not new_ids:
        return True, f"sparse turn produced 0 new facts (as expected)", None
    return False, f"sparse turn produced {len(new_ids)} new fact(s) — LLM over-extracted", \
        "Tighten consolidation prompt to refuse non-durable extracts; consider raising FACT_CONFIDENCE floor."


@scenario("F3", "F. Consolidation", "update_procedural increments success_count exactly once")
def s_f3(es: Elasticsearch, user_a: str, user_b: str) -> tuple[bool, str, str | None]:
    w = write_memory(es, user_id=user_a, memory_type="procedural",
                     text="Reboot the hub when LED is steady red",
                     name="hub_reboot_red_led",
                     description="Reboot fix for steady red LED",
                     steps=[{"order": 1, "instruction": "Hold power 10s", "tool": "ask_user"}],
                     refresh=True)
    update_procedural(es, user_id=user_a, memory_id=w["id"], outcome="success")
    es.indices.refresh(index=INDEX_PROCEDURAL)
    doc = es.get(index=INDEX_PROCEDURAL, id=w["id"])["_source"]
    sc = doc.get("success_count", 0)
    fc = doc.get("failure_count", 0)
    if sc == 1 and fc == 0:
        return True, f"success_count=1 after one success outcome", None
    return False, f"got success_count={sc} failure_count={fc} (expected 1, 0)", \
        "Check update_procedural's Painless script at operations.py:700."


# ---------------------------------------------------------------------------
# G. Edge cases
# ---------------------------------------------------------------------------

@scenario("G1", "G. Edge cases", "Supersede non-existent id → graceful (no crash)")
def s_g1(es: Elasticsearch, user_a: str, user_b: str) -> tuple[bool, str, str | None]:
    try:
        w = write_memory(es, user_id=user_a, memory_type="semantic",
                         text="Replacement fact", fact_type="identity",
                         supersedes_id="nonexistent-id-12345",
                         contradiction="natural", refresh=True)
        es.get(index=INDEX_SEMANTIC, id=w["id"])  # confirm new doc exists
        return True, f"graceful: new doc {w['id']} written, no crash on dangling supersedes_id", None
    except Exception as exc:  # noqa: BLE001
        return False, f"raised {type(exc).__name__}: {exc}", \
            "write_memory at operations.py:128-142 should catch NotFoundError on the supersede update."


@scenario("G2", "G. Edge cases", "forget non-existent id → returns not-found, no crash")
def s_g2(es: Elasticsearch, user_a: str, user_b: str) -> tuple[bool, str, str | None]:
    try:
        result = forget_memory(es, user_id=user_a, memory_type="semantic",
                              memory_id="definitely-not-real-id")
        if result.get("deleted") is False and result.get("reason") == "not_found":
            return True, f"graceful: {result}", None
        return False, f"unexpected result: {result}", \
            "forget_memory at operations.py:644-649 should return not_found."
    except Exception as exc:  # noqa: BLE001
        return False, f"raised {type(exc).__name__}: {exc}", \
            "forget_memory should catch NotFoundError and return a result, not raise."


@scenario("G3", "G. Edge cases", "Write 5KB text → succeeds, recall finds it")
def s_g3(es: Elasticsearch, user_a: str, user_b: str) -> tuple[bool, str, str | None]:
    marker = f"BIGDOC-{int(time.time())}"
    long_text = marker + " " + ("Lumio Hub diagnostic logs " * 200)
    if len(long_text) < 5000:
        long_text = long_text + (" " * (5000 - len(long_text)))
    try:
        w = write_memory(es, user_id=user_a, memory_type="semantic", text=long_text,
                         fact_type="world", refresh=True)
        hits = recall_memory(es, query=marker, user_id=user_a, k=5)
        if w["id"] in [h["id"] for h in hits]:
            return True, f"5KB doc written and recalled successfully", None
        return False, f"5KB doc written but not in recall hits", \
            "Investigate semantic_text chunking behavior on long input."
    except Exception as exc:  # noqa: BLE001
        return False, f"raised {type(exc).__name__}: {exc}", \
            "Long inputs should be accepted; check mapping limits."


@scenario("G4", "G. Edge cases", "Unicode + emoji text preserved through write/recall")
def s_g4(es: Elasticsearch, user_a: str, user_b: str) -> tuple[bool, str, str | None]:
    text = "Sarah's nickname is Sárka 🌟 — likes café au lait ☕ in 京都 (Kyoto)"
    w = write_memory(es, user_id=user_a, memory_type="semantic", text=text,
                     fact_type="preference", refresh=True)
    raw = es.get(index=INDEX_SEMANTIC, id=w["id"])["_source"]
    if raw.get("text") == text:
        return True, f"unicode preserved exactly", None
    return False, f"text mismatch:\n  in:  {text!r}\n  out: {raw.get('text')!r}", \
        "ES is unicode-safe; this should never fail. Check serialization in the API path."


@scenario("G5", "G. Edge cases", "Empty query to recall_memory → graceful")
def s_g5(es: Elasticsearch, user_a: str, user_b: str) -> tuple[bool, str, str | None]:
    try:
        hits = recall_memory(es, query="", user_id=user_a, k=5)
        # Either empty hits or a small result set — both are fine. The key is no crash.
        return True, f"empty query handled: returned {len(hits)} hits", None
    except Exception as exc:  # noqa: BLE001
        return False, f"raised {type(exc).__name__}: {exc}", \
            "Add an early-return for empty query at recall_memory's entry."


@scenario("G6", "G. Edge cases", "Episodic write with supersedes_id → no penalty (only semantic uses)")
def s_g6(es: Elasticsearch, user_a: str, user_b: str) -> tuple[bool, str, str | None]:
    try:
        w = write_memory(es, user_id=user_a, memory_type="episodic",
                         text="User: I'm here.", session_id="stress",
                         event_type="user_message", role="user",
                         supersedes_id="some-id-ignored",
                         contradiction="harsh",  # would penalize a semantic; should be noop here
                         refresh=True)
        doc = es.get(index=INDEX_EPISODIC, id=w["id"])["_source"]
        if "confidence" not in doc:
            return True, f"episodic write ignored confidence/supersedes_id semantics", None
        return False, f"episodic doc has confidence={doc.get('confidence')} (shouldn't)", \
            "operations.py episodic branch should not apply the semantic penalty path."
    except Exception as exc:  # noqa: BLE001
        return False, f"raised {type(exc).__name__}: {exc}", \
            "Episodic writes should silently ignore supersedes_id/contradiction."


# ---------------------------------------------------------------------------
# H. Recency signal
# ---------------------------------------------------------------------------

@scenario("H1", "H. Recency", "Fresh fact outranks stale identical-text fact")
def s_h1(es: Elasticsearch, user_a: str, user_b: str) -> tuple[bool, str, str | None]:
    text = f"Unique recency-test claim {int(time.time())}"
    # Write two facts with identical text
    fresh = write_memory(es, user_id=user_a, memory_type="semantic", text=text,
                        fact_type="world", refresh=True)
    stale = write_memory(es, user_id=user_a, memory_type="semantic", text=text,
                        fact_type="world", refresh=True)
    # Backdate the second one's last_used_at by 5 years
    stale_date = (datetime.now(timezone.utc) - timedelta(days=5 * 365)).isoformat()
    es.update(index=INDEX_SEMANTIC, id=stale["id"],
              doc={"last_used_at": stale_date, "created_at": stale_date},
              refresh=True)
    # Recall and check ordering
    hits = recall_memory(es, query=text, user_id=user_a, k=10, rerank=False)
    ids = [h["id"] for h in hits]
    if fresh["id"] not in ids or stale["id"] not in ids:
        return False, f"one of the two facts missing from recall: {ids[:5]}", \
            "Both should be retrieved; check filter/recall paths."
    fresh_rank = ids.index(fresh["id"])
    stale_rank = ids.index(stale["id"])
    if fresh_rank < stale_rank:
        return True, f"fresh ranks above stale: fresh@{fresh_rank+1}, stale@{stale_rank+1}", None
    return False, f"stale ranks above or equal to fresh: fresh@{fresh_rank+1}, stale@{stale_rank+1}", \
        "Check the gauss-shape decay in _decay_script (semantic branch reads last_used_at)."


# ---------------------------------------------------------------------------
# Runner + report
# ---------------------------------------------------------------------------

def run_all() -> tuple[list[ScenarioResult], str, str]:
    """Run all scenarios; return (results, user_a, user_b)."""
    es = get_es_client()
    ts = int(time.time())
    user_a = f"stress_a_{ts}"
    user_b = f"stress_b_{ts}"
    print(f"Running stress test as users: {user_a}, {user_b}")
    print(f"Total scenarios: {len(SCENARIOS)}\n")

    results: list[ScenarioResult] = []
    for name, category, description, func in SCENARIOS:
        print(f"  [{name}] {description}...", end=" ", flush=True)
        try:
            passed, detail, fix = func(es, user_a, user_b)
        except Exception as exc:  # noqa: BLE001
            passed = False
            detail = f"UNCAUGHT {type(exc).__name__}: {exc}\n{traceback.format_exc()}"
            fix = "Scenario raised an unexpected exception. See traceback in report."
        results.append(ScenarioResult(name=name, category=category,
                                      description=description, passed=passed,
                                      detail=detail, fix_suggestion=fix))
        print("PASS" if passed else "FAIL")

    return results, user_a, user_b


def write_report(results: list[ScenarioResult]) -> Path:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = REPORT_DIR / f"stress_test_report-{ts}.md"

    passed = sum(1 for r in results if r.passed)
    failed = len(results) - passed

    # Group by category
    by_cat: dict[str, list[ScenarioResult]] = {}
    for r in results:
        by_cat.setdefault(r.category, []).append(r)

    lines: list[str] = []
    lines.append(f"# Atlas Stress Test Report — {ts}\n")
    lines.append(f"**Total:** {len(results)}  |  **Passed:** {passed}  |  **Failed:** {failed}\n")

    # Summary by category
    lines.append("\n## Summary by category\n")
    for cat in sorted(by_cat):
        items = by_cat[cat]
        p = sum(1 for r in items if r.passed)
        fail_names = [r.name for r in items if not r.passed]
        line = f"- **{cat}**: {p}/{len(items)}"
        if fail_names:
            line += f" — failed: {', '.join(fail_names)}"
        lines.append(line)

    # Failures with fix suggestions
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
        lines.append("\n## Failures\n\n_None — all scenarios passed._\n")

    # Per-scenario detail
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

    results, user_a, user_b = run_all()

    # Cleanup
    es = get_es_client()
    print("\nCleaning up test users...")
    cleanup(es, [user_a, user_b])

    # Write report
    report_path = write_report(results)
    passed = sum(1 for r in results if r.passed)
    failed = len(results) - passed
    print(f"\n=== Summary ===")
    print(f"Total: {len(results)}  Passed: {passed}  Failed: {failed}")
    print(f"Report: {report_path}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
