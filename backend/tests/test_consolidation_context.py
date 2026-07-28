"""Assistant reply reaches consolidation as context, and only as context.

The contract has two halves and both matter:
  - the reply IS shown to the extractor, so an elliptical customer turn
    ("yes", "that worked") can be interpreted and a procedure's steps grounded;
  - the reply is NOT indexed, NOT citable, and NOT itself a fact.
"""

from __future__ import annotations

import pytest

from app.atlas.consolidate import CONSOLIDATION_PROMPT, consolidate


class _FakeES:
    def __init__(self, episodes=None):
        self._episodes = episodes or []
        self.indexed: list[dict] = []
        self.searches: list[dict] = []

    def search(self, **kwargs):
        self.searches.append(kwargs)
        idx = kwargs.get("index", "")
        if "episodic" in idx:
            return {"hits": {"hits": self._episodes}}
        return {"hits": {"hits": []}}

    def index(self, **kwargs):
        self.indexed.append(kwargs)
        return {"result": "created"}

    def get(self, **kwargs):
        from elasticsearch import NotFoundError
        raise NotFoundError("not found", meta=None, body=None)

    def update(self, **kwargs):
        return {"result": "updated"}


def _episode(_id="e1", text="yes that worked, thanks"):
    return {"_id": _id, "_source": {"text": text, "role": "user",
                                    "timestamp": "2026-07-27T10:00:00+00:00"}}


@pytest.fixture
def captured(monkeypatch):
    """Capture the prompt without calling an LLM."""
    seen = {}

    def fake_complete_chat(*, inference_id, messages, max_completion_tokens):
        seen["prompt"] = messages[0]["content"]
        return '{"new_facts": [], "new_procedures": [], "procedural_updates": []}'

    monkeypatch.setattr("app.atlas.consolidate.complete_chat", fake_complete_chat)
    return seen


# ---------------------------------------------------------------------------
# The reply reaches the extractor
# ---------------------------------------------------------------------------

def test_assistant_context_is_rendered_into_the_prompt(captured):
    es = _FakeES(episodes=[_episode()])
    consolidate(es, user_id="sarah", dry_run=True,
                assistant_context="Try power-cycling the hub for 90 seconds.")
    assert "Try power-cycling the hub for 90 seconds." in captured["prompt"]


def _context_block(prompt: str) -> str:
    """The rendered block, not the rules section that also names the tag."""
    return prompt.rsplit("<assistant_reply_context>", 1)[1].split("</assistant_reply_context>")[0]


def test_assistant_context_is_in_its_own_block_not_recent_events(captured):
    """It must not be mistaken for something the customer said."""
    es = _FakeES(episodes=[_episode()])
    consolidate(es, user_id="sarah", dry_run=True, assistant_context="ASSISTANT_PROSE")
    prompt = captured["prompt"]
    events_block = prompt.split("<recent_events>")[1].split("</recent_events>")[0]
    assert "ASSISTANT_PROSE" not in events_block
    assert "ASSISTANT_PROSE" in _context_block(prompt)


# ---------------------------------------------------------------------------
# ...and only as context
# ---------------------------------------------------------------------------

def test_assistant_context_is_never_indexed(captured):
    es = _FakeES(episodes=[_episode()])
    consolidate(es, user_id="sarah", assistant_context="Try power-cycling the hub.")
    for call in es.indexed:
        body = str(call.get("document", {}))
        assert "power-cycling" not in body, "assistant prose must not be persisted"


def test_prompt_forbids_extracting_facts_from_the_context():
    """The guard against laundering model output into the customer's record."""
    assert "NEVER extract a fact from it" in CONSOLIDATION_PROMPT
    assert "unverified model output" in CONSOLIDATION_PROMPT
    assert "has no ids and can never be cited" in CONSOLIDATION_PROMPT


# ---------------------------------------------------------------------------
# Backwards compatibility
# ---------------------------------------------------------------------------

def test_omitting_the_argument_preserves_previous_behaviour(captured):
    """Every existing caller (routes/memory.py, stress_test.py) passes nothing."""
    es = _FakeES(episodes=[_episode()])
    out = consolidate(es, user_id="sarah", dry_run=True)
    assert out["dry_run"] is True
    assert "(none)" in captured["prompt"]


def test_context_spans_several_turns_so_a_confirmation_finds_its_advice(captured):
    """The case this exists for.

    A customer confirms a fix one turn AFTER receiving it. When "it worked"
    lands, the steps it refers to are in the PREVIOUS reply, so a single-turn
    context would show the extractor the confirmation and the acknowledgement of
    it, and never the procedure being confirmed.
    """
    from app.atlas.agent import _assistant_context

    history = [
        {"role": "user", "content": "my hub keeps dropping devices"},
        {"role": "assistant", "content": "Power-cycle the hub for 90 seconds, then re-pair."},
        {"role": "user", "content": "it worked"},
    ]
    ctx = _assistant_context(history, ["Great, glad that sorted it."])
    assert "Power-cycle the hub for 90 seconds" in ctx, "the advice being confirmed must be present"
    assert "Great, glad that sorted it." in ctx, "the current reply is included too"
    assert ctx.index("Power-cycle") < ctx.index("Great, glad"), "oldest first"


def test_assistant_context_ignores_user_turns_and_malformed_entries():
    """History is client-supplied and unvalidated."""
    from app.atlas.agent import _assistant_context

    history = [
        {"role": "user", "content": "USER_TEXT"},
        {"role": "system", "content": "SYSTEM_TEXT"},
        "not-a-dict",
        {"role": "assistant"},
        {"role": "assistant", "content": ""},
        {"role": "assistant", "content": 12345},
        {"role": "assistant", "content": "KEEP_ME"},
    ]
    ctx = _assistant_context(history, [])
    assert ctx == "KEEP_ME"


def test_assistant_context_is_bounded_and_drops_oldest_first():
    from app.atlas.agent import _assistant_context
    from app.atlas.memory.constants import (
        CONSOLIDATION_ASSISTANT_CONTEXT_CHARS,
        CONSOLIDATION_ASSISTANT_CONTEXT_TURNS,
    )

    history = [{"role": "assistant", "content": f"turn-{i} " + "x" * 50} for i in range(12)]
    ctx = _assistant_context(history, [])
    assert ctx.count("--- next assistant turn ---") == CONSOLIDATION_ASSISTANT_CONTEXT_TURNS - 1
    assert "turn-11" in ctx and "turn-0" not in ctx, "keeps the newest turns"

    big = [{"role": "assistant", "content": "y" * 5000} for _ in range(4)]
    assert len(_assistant_context(big, [])) <= CONSOLIDATION_ASSISTANT_CONTEXT_CHARS + 5000


def test_assistant_context_is_none_when_there_is_nothing():
    from app.atlas.agent import _assistant_context
    assert _assistant_context([], []) is None
    assert _assistant_context([{"role": "user", "content": "hi"}], []) is None


def test_blank_context_renders_as_none(captured):
    es = _FakeES(episodes=[_episode()])
    consolidate(es, user_id="sarah", dry_run=True, assistant_context="   ")
    assert _context_block(captured["prompt"]).strip() == "(none)"
