"""Tests for the remaining Release 1 changes.

Each test pins a behaviour that was previously wrong, so a regression is
attributable rather than merely visible.
"""

from __future__ import annotations

import pytest

from app.atlas.memory.constants import CORE_MEMORY_LIMIT
from app.atlas.memory.operations import core_memory, list_memories, write_memory
from app.atlas.tools import tool_schemas


class _FakeES:
    def __init__(self, hits=None):
        self._hits = hits or []
        self.searches: list[dict] = []
        self.indexed: list[dict] = []
        self.updates: list[dict] = []

    def search(self, **kwargs):
        self.searches.append(kwargs)
        return {"hits": {"hits": self._hits}}

    def index(self, **kwargs):
        self.indexed.append(kwargs)
        return {"result": "created"}

    def update(self, **kwargs):
        self.updates.append(kwargs)
        return {"result": "updated"}


# ---------------------------------------------------------------------------
# A1: core memory
# ---------------------------------------------------------------------------

def test_core_memory_selects_only_identity_and_constraint():
    es = _FakeES()
    core_memory(es, user_id="sarah")
    body = es.searches[0]["body"]
    filters = body["query"]["bool"]["filter"]
    assert {"term": {"user_id": "sarah"}} in filters
    assert {"terms": {"fact_type": ["constraint", "identity"]}} in filters


def test_core_memory_excludes_superseded_facts():
    es = _FakeES()
    core_memory(es, user_id="sarah")
    must_not = es.searches[0]["body"]["query"]["bool"]["must_not"]
    assert {"exists": {"field": "superseded_by"}} in must_not


def test_core_memory_orders_constraints_before_identity_then_oldest_first():
    """Two load-bearing sort decisions.

    'constraint' before 'identity': when the cap bites it should drop biography,
    not a hard limit the agent must respect.

    Oldest-first WITHIN a type: newest-first evicted the foundational facts,
    because consolidation output is always newer than the durable facts it was
    derived from. On the live corpus "Sarah owns a Lumio Hub v2" was pushed out
    of the block by "Sarah's tone shifted from enthusiastic to tired".
    """
    es = _FakeES()
    core_memory(es, user_id="sarah")
    assert es.searches[0]["body"]["sort"] == [
        {"fact_type": "asc"},
        {"created_at": "asc"},
    ]


def test_core_memory_overfetches_then_caps():
    """Dedup must happen before truncation, or duplicates consume slots and
    silently shrink the effective block."""
    es = _FakeES()
    core_memory(es, user_id="sarah")
    assert es.searches[0]["body"]["size"] > CORE_MEMORY_LIMIT


def test_core_memory_caps_returned_facts():
    es = _FakeES(hits=[
        {"_id": str(i), "_source": {"text": f"Distinct fact number {i} about the customer.",
                                    "fact_type": "identity"}}
        for i in range(CORE_MEMORY_LIMIT * 3)
    ])
    assert len(core_memory(es, user_id="sarah")) == CORE_MEMORY_LIMIT


def test_core_memory_drops_near_duplicates():
    """The live corpus had 'shares her home with her partner and their newborn
    son Theo' twice, byte-identical, both inside the same block."""
    es = _FakeES(hits=[
        {"_id": "a", "_source": {"text": "Sarah shares her home with her partner and their newborn son Theo.",
                                 "fact_type": "identity"}},
        {"_id": "b", "_source": {"text": "Sarah shares her home with her partner and their newborn son Theo.",
                                 "fact_type": "identity"}},
        {"_id": "c", "_source": {"text": "Sarah owns a Lumio Hub v2 as her primary controller.",
                                 "fact_type": "identity"}},
    ])
    out = core_memory(es, user_id="sarah")
    assert [f["id"] for f in out] == ["a", "c"]


def test_core_memory_can_be_disabled(monkeypatch):
    """Operators upgrading a corpus with poor fact_type hygiene need an off
    switch that does not require a code change."""
    import app.atlas.memory.operations as ops
    monkeypatch.setattr(ops, "CORE_MEMORY_ENABLED", False)
    es = _FakeES(hits=[{"_id": "a", "_source": {"text": "x" * 40, "fact_type": "identity"}}])
    assert core_memory(es, user_id="sarah") == []
    assert es.searches == [], "must not even query when disabled"


def test_core_memory_drops_blank_text():
    es = _FakeES(hits=[
        {"_id": "a", "_source": {"text": "Sarah owns a Hub v2.", "fact_type": "identity"}},
        {"_id": "b", "_source": {"text": "   ", "fact_type": "identity"}},
        {"_id": "c", "_source": {"fact_type": "constraint"}},
    ])
    out = core_memory(es, user_id="sarah")
    assert [f["id"] for f in out] == ["a"]


# ---------------------------------------------------------------------------
# C5: list_memories superseded filter is parameterised, not global
# ---------------------------------------------------------------------------

def test_list_memories_includes_superseded_by_default():
    """The /api/memory/list route and the Memory Inspector depend on this;
    filtering globally would remove the audit view supersession exists for."""
    es = _FakeES()
    list_memories(es, user_id="sarah", memory_type="semantic")
    assert "must_not" not in es.searches[0]["body"]["query"]["bool"]


def test_list_memories_can_exclude_superseded():
    es = _FakeES()
    list_memories(es, user_id="sarah", memory_type="semantic", include_superseded=False)
    must_not = es.searches[0]["body"]["query"]["bool"]["must_not"]
    assert {"exists": {"field": "superseded_by"}} in must_not


def test_list_memories_still_filters_by_user():
    es = _FakeES()
    list_memories(es, user_id="sarah", memory_type="episodic", include_superseded=False)
    filters = es.searches[0]["body"]["query"]["bool"]["filter"]
    assert {"term": {"user_id": "sarah"}} in filters


# ---------------------------------------------------------------------------
# A5: retraction is distinguishable from prior state
# ---------------------------------------------------------------------------

def test_harsh_supersession_marks_the_old_fact_retracted():
    es = _FakeES()
    write_memory(
        es, user_id="sarah", memory_type="semantic", text="Sarah lives in Edinburgh",
        supersedes_id="old-1", contradiction="harsh",
    )
    (upd,) = es.updates
    assert upd["doc"]["retracted"] is True
    assert upd["doc"]["superseded_by"]
    assert upd["doc"]["superseded_at"]


def test_natural_supersession_does_not_mark_retracted():
    """A fact that was true and stopped being true is legitimate history."""
    es = _FakeES()
    write_memory(
        es, user_id="sarah", memory_type="semantic", text="Sarah lives in Edinburgh",
        supersedes_id="old-1", contradiction="natural",
    )
    (upd,) = es.updates
    assert "retracted" not in upd["doc"]


def test_supersession_without_contradiction_defaults_to_not_retracted():
    es = _FakeES()
    write_memory(
        es, user_id="sarah", memory_type="semantic", text="x", supersedes_id="old-1",
    )
    assert "retracted" not in es.updates[0]["doc"]


def test_consolidation_path_cannot_retract():
    """Retraction is a hard rule ("never recount this"). Consolidation infers the
    contradiction second-hand from stored episodes, so it may lower confidence
    but may not flag a fact as never-true."""
    es = _FakeES()
    write_memory(
        es, user_id="sarah", memory_type="semantic", text="x",
        supersedes_id="old-1", contradiction="harsh", allow_retraction=False,
    )
    assert "retracted" not in es.updates[0]["doc"]
    assert es.updates[0]["doc"]["superseded_by"], "still supersedes normally"


def test_consolidation_path_still_takes_the_confidence_penalty():
    """The soft, recoverable half of the signal is retained."""
    es = _FakeES()
    write_memory(
        es, user_id="sarah", memory_type="semantic", text="x", confidence=1.0,
        supersedes_id="old-1", contradiction="harsh", allow_retraction=False,
    )
    assert es.indexed[0]["document"]["confidence"] == pytest.approx(0.9)


def test_harsh_supersession_still_applies_the_confidence_penalty():
    es = _FakeES()
    write_memory(
        es, user_id="sarah", memory_type="semantic", text="x",
        confidence=1.0, supersedes_id="old-1", contradiction="harsh",
    )
    assert es.indexed[0]["document"]["confidence"] == pytest.approx(0.9)


# ---------------------------------------------------------------------------
# C1: a procedural write can actually carry a playbook
# ---------------------------------------------------------------------------

def _write_memory_schema() -> dict:
    for spec in tool_schemas():
        if spec["function"]["name"] == "write_memory":
            return spec["function"]["parameters"]
    raise AssertionError("write_memory tool not found")


@pytest.mark.parametrize("field", ["name", "description", "steps"])
def test_write_memory_schema_exposes_procedural_fields(field):
    """Without these the agent had no way to express steps, so every
    agent-written playbook was created empty while the system prompt told the
    agent to follow its steps."""
    assert field in _write_memory_schema()["properties"]


def test_steps_schema_uses_the_real_step_shape():
    steps = _write_memory_schema()["properties"]["steps"]
    assert steps["type"] == "array"
    props = steps["items"]["properties"]
    assert set(props) == {"order", "instruction", "tool"}
    assert steps["items"]["required"] == ["order", "instruction"]


def test_added_procedural_fields_are_optional():
    """Additive-only: existing MCP clients that omit them keep working."""
    assert _write_memory_schema()["required"] == ["memory_type", "text"]


def test_procedural_write_persists_steps():
    es = _FakeES()
    steps = [{"order": 1, "instruction": "Power-cycle the hub", "tool": "ask_user"}]
    write_memory(
        es, user_id="sarah", memory_type="procedural", text="hub drops devices",
        name="hub_reset", description="Recover a dropped mesh", steps=steps,
    )
    doc = es.indexed[0]["document"]
    assert doc["steps"] == steps
    assert doc["name"] == "hub_reset"
    assert doc["description"] == "Recover a dropped mesh"
