"""Validity time (P4): when a fact was true, as distinct from when it was learned.

`created_at` and `superseded_at` are transaction time. They coincide with
validity time only if customers report changes immediately. Someone who moves in
November and mentions it in January leaves a 14-month gap, and a point-in-time
question answered from the transaction interval gets the wrong answer.
"""

from __future__ import annotations

import json
import pathlib

import pytest

from app.atlas.agent import SYSTEM_PROMPT_TEMPLATE
from app.atlas.consolidate import CONSOLIDATION_PROMPT, _clean_date
from app.atlas.memory.operations import write_memory
from app.atlas.tools import tool_schemas


class _FakeES:
    def __init__(self):
        self.indexed: list[dict] = []

    def index(self, **kwargs):
        self.indexed.append(kwargs)
        return {"result": "created"}

    def update(self, **kwargs):
        return {"result": "updated"}


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------

def test_validity_dates_are_persisted_when_supplied():
    es = _FakeES()
    write_memory(es, user_id="sarah", memory_type="semantic",
                 text="Sarah lives in Edinburgh", fact_type="identity",
                 valid_from="2024-11-01")
    assert es.indexed[0]["document"]["valid_from"] == "2024-11-01"


def test_validity_dates_are_absent_unless_supplied():
    """Every pre-existing document lacks them; a range filter must tolerate that."""
    es = _FakeES()
    write_memory(es, user_id="sarah", memory_type="semantic", text="x", fact_type="identity")
    doc = es.indexed[0]["document"]
    assert "valid_from" not in doc and "valid_to" not in doc


def test_fields_are_mapped_as_dates():
    mapping = json.loads(
        (pathlib.Path(__file__).resolve().parents[1]
         / "app/atlas/memory/mappings/semantic.json").read_text()
    )
    props = mapping["mappings"]["properties"]
    assert props["valid_from"]["type"] == "date"
    assert props["valid_to"]["type"] == "date"


# ---------------------------------------------------------------------------
# Model output is not trusted verbatim
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("raw,expected", [
    ("2024-11-01", "2024-11-01"),
    ("2024-11", "2024-11-01"),      # month precision is normalised
    ("  2024-11-01  ", "2024-11-01"),
    ("last November", None),
    ("November 2024", None),
    ("2024/11/01", None),
    ("", None),
    (None, None),
    (12345, None),
])
def test_clean_date_rejects_anything_elasticsearch_would_choke_on(raw, expected):
    """A bad date would fail the write and lose every fact in the pass. A fact
    without validity dates is still a useful fact, so drop rather than raise."""
    assert _clean_date(raw) == expected


# ---------------------------------------------------------------------------
# The dates have to reach the model, or they change nothing
# ---------------------------------------------------------------------------

def test_agent_can_set_validity_dates_when_writing_a_fact():
    props = [s["function"]["parameters"]["properties"]
             for s in tool_schemas() if s["function"]["name"] == "write_memory"][0]
    assert "valid_from" in props and "valid_to" in props
    assert props["valid_from"]["type"] == "string"


def test_added_fields_stay_optional():
    """Additive only: existing MCP clients must keep working."""
    params = [s["function"]["parameters"]
              for s in tool_schemas() if s["function"]["name"] == "write_memory"][0]
    assert params["required"] == ["memory_type", "text"]


def test_agent_prompt_prefers_validity_over_recording_time():
    assert "valid_from" in SYSTEM_PROMPT_TEMPLATE
    assert "never from `timestamp` or `superseded_at`" in SYSTEM_PROMPT_TEMPLATE


def test_context_block_no_longer_contradicts_the_validity_rule():
    """The header used to say plainly: use `timestamp` for 'when' questions."""
    assert "prefer validity dates where present" in SYSTEM_PROMPT_TEMPLATE


def test_extraction_prompt_forbids_guessing_dates():
    assert "leave both null rather than guessing" in CONSOLIDATION_PROMPT
    assert "not the same as when the customer told you" in CONSOLIDATION_PROMPT
