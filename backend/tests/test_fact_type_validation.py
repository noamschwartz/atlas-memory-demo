"""`fact_type` is the field with the widest blast radius and had no validation.

Facts typed `identity` or `constraint` are injected into the system prompt on
every future turn. The agent's tool schema constrains the value with a JSON
enum, but consolidation hands `write_memory` the extractor's raw JSON, so an
invented or misspelled type reached the index unchallenged.
"""

from __future__ import annotations

import pytest

from app.atlas.memory.constants import DEFAULT_FACT_TYPE, VALID_FACT_TYPES
from app.atlas.memory.operations import write_memory


class _FakeES:
    def __init__(self):
        self.indexed: list[dict] = []

    def index(self, **kwargs):
        self.indexed.append(kwargs)
        return {"result": "created"}

    def update(self, **kwargs):
        return {"result": "updated"}


def _written(fact_type) -> str:
    es = _FakeES()
    write_memory(es, user_id="sarah", memory_type="semantic", text="x", fact_type=fact_type)
    return es.indexed[0]["document"]["fact_type"]


@pytest.mark.parametrize("value", sorted(VALID_FACT_TYPES))
def test_valid_types_pass_through_unchanged(value):
    assert _written(value) == value


@pytest.mark.parametrize("value", ["Identity", "CONSTRAINT", "  world  ", "Preference\n"])
def test_case_and_whitespace_are_normalised(value):
    """Correction, not inference: the intent is unambiguous."""
    assert _written(value) == value.strip().lower()


@pytest.mark.parametrize("value", ["constraints", "critical", "fact", "", "identity!"])
def test_unrecognised_values_fall_back_to_the_default(value):
    assert _written(value) == DEFAULT_FACT_TYPE


def test_a_misspelling_is_not_repaired_to_the_nearest_valid_type():
    """"constraints" is one character from "constraint" and must NOT be coerced
    to it. Guessing intent would promote an unverified fact into the block that
    is injected on every future turn."""
    assert _written("constraints") != "constraint"


def test_the_fallback_is_never_a_core_memory_type():
    """An unrecognised value must not land in the always-in-context block."""
    assert DEFAULT_FACT_TYPE not in ("identity", "constraint")


@pytest.mark.parametrize("value", [None, 7, ["identity"], {"t": "identity"}])
def test_non_strings_do_not_raise(value):
    """A bad value costs one field, not the consolidation pass it arrived in."""
    assert _written(value) == DEFAULT_FACT_TYPE


def test_episodic_writes_are_unaffected():
    es = _FakeES()
    write_memory(es, user_id="sarah", memory_type="episodic", text="hello")
    assert "fact_type" not in es.indexed[0]["document"]


def test_procedural_writes_are_unaffected():
    es = _FakeES()
    write_memory(es, user_id="sarah", memory_type="procedural", text="hub drops devices")
    assert "fact_type" not in es.indexed[0]["document"]
