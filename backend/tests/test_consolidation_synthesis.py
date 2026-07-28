"""Cross-turn synthesis context (P2) and unconfirmed-advice records (P3).

P2: the watermark means a pass normally sees one new user message. Facts that
exist across turns rather than within one need the earlier messages visible as
context, without re-extracting from them.

P3: a conversation usually ends right after advice is given, so nobody says
whether it worked. That outcome is recorded as a typed, resolvable marker
instead of being lost.
"""

from __future__ import annotations

import pytest

from app.atlas.consolidate import CONSOLIDATION_PROMPT, _summarize_existing, consolidate
from app.atlas.memory.constants import CONSOLIDATION_CONTEXT_EPISODES
from app.atlas.memory.operations import write_memory
from app.atlas.memory.state import episodes_before


class _FakeES:
    def __init__(self, new_eps=None, earlier_eps=None, existing=None):
        self._new = new_eps or []
        self._earlier = earlier_eps or []
        self._existing = existing or []
        self.searches: list[dict] = []
        self.indexed: list[dict] = []

    def search(self, **kwargs):
        self.searches.append(kwargs)
        body = kwargs.get("body", {})
        idx = kwargs.get("index", "")
        if "episodic" in idx:
            filters = body.get("query", {}).get("bool", {}).get("filter", [])
            is_earlier = any("lt" in f.get("range", {}).get("timestamp", {}) for f in filters)
            return {"hits": {"hits": self._earlier if is_earlier else self._new}}
        if "semantic" in idx:
            return {"hits": {"hits": self._existing}}
        return {"hits": {"hits": []}}

    def index(self, **kwargs):
        self.indexed.append(kwargs)
        return {"result": "created"}

    def get(self, **kwargs):
        from elasticsearch import NotFoundError
        raise NotFoundError("not found", meta=None, body=None)

    def update(self, **kwargs):
        return {"result": "updated"}


def _ep(_id, text, ts="2026-07-27T10:00:00+00:00"):
    return {"_id": _id, "_source": {"text": text, "role": "user", "timestamp": ts}}


@pytest.fixture
def captured(monkeypatch):
    seen = {}

    def fake_complete_chat(*, inference_id, messages, max_completion_tokens):
        seen["prompt"] = messages[0]["content"]
        return '{"new_facts": [], "new_procedures": [], "procedural_updates": []}'

    monkeypatch.setattr("app.atlas.consolidate.complete_chat", fake_complete_chat)
    return seen


def _block(prompt: str, tag: str) -> str:
    return prompt.rsplit(f"<{tag}>", 1)[1].split(f"</{tag}>")[0]


# ---------------------------------------------------------------------------
# P2: cross-turn synthesis
# ---------------------------------------------------------------------------

def test_earlier_episodes_are_fetched_strictly_before_the_new_ones():
    """The two blocks must not overlap, or facts get double-counted."""
    es = _FakeES()
    episodes_before(es, user_id="sarah", before="2026-07-27T10:00:00+00:00", limit=5)
    body = es.searches[0]["body"]
    filters = body["query"]["bool"]["filter"]
    assert {"range": {"timestamp": {"lt": "2026-07-27T10:00:00+00:00"}}} in filters
    assert body["sort"] == [{"timestamp": "desc"}], "newest-first so the limit picks recent ones"


def test_earlier_episodes_are_returned_oldest_first():
    """Fetched newest-first to select, then reversed: the prompt reasons about order."""
    es = _FakeES(earlier_eps=[_ep("c", "third"), _ep("b", "second"), _ep("a", "first")])
    out = episodes_before(es, user_id="sarah", before="2026-07-28T00:00:00+00:00", limit=5)
    assert [r["id"] for r in out] == ["a", "b", "c"]


def test_earlier_events_render_in_their_own_block(captured):
    es = _FakeES(new_eps=[_ep("n1", "NEW_MESSAGE")],
                 earlier_eps=[_ep("o1", "OLD_MESSAGE", "2026-07-20T10:00:00+00:00")])
    consolidate(es, user_id="sarah", dry_run=True)
    prompt = captured["prompt"]
    assert "OLD_MESSAGE" in _block(prompt, "earlier_events")
    assert "NEW_MESSAGE" in _block(prompt, "recent_events")
    assert "OLD_MESSAGE" not in _block(prompt, "recent_events")


def test_prompt_forbids_re_extracting_from_earlier_events():
    assert "ALREADY been consolidated, so do not re-extract" in CONSOLIDATION_PROMPT
    assert "must still cite an id from <recent_events>" in CONSOLIDATION_PROMPT


def test_context_episode_fetch_failure_does_not_lose_the_turn(captured):
    """Context is an enhancement. Failing the pass would drop the turn's facts."""
    class _Boom(_FakeES):
        def search(self, **kwargs):
            body = kwargs.get("body", {})
            filters = body.get("query", {}).get("bool", {}).get("filter", [])
            if any("lt" in f.get("range", {}).get("timestamp", {}) for f in filters):
                raise RuntimeError("cluster hiccup")
            return super().search(**kwargs)

    es = _Boom(new_eps=[_ep("n1", "still extracted")])
    out = consolidate(es, user_id="sarah", dry_run=True)
    assert out["dry_run"] is True
    assert "still extracted" in _block(captured["prompt"], "recent_events")


# ---------------------------------------------------------------------------
# P3: unconfirmed advice
# ---------------------------------------------------------------------------

def test_prompt_requires_world_type_and_forbids_customer_attribution():
    assert 'fact_type MUST be "world"' in CONSOLIDATION_PROMPT
    assert "Do NOT record the advice as though the customer stated it" in CONSOLIDATION_PROMPT


def test_prompt_explains_how_a_pending_fact_is_resolved():
    assert "[pending]" in CONSOLIDATION_PROMPT
    assert "supersede the pending fact" in CONSOLIDATION_PROMPT


def test_pending_facts_are_marked_in_the_existing_facts_listing():
    """The extractor can only resolve what it can see is unresolved."""
    rows = [
        {"id": "f1", "source": {"text": "Advised a static IP", "fact_type": "world",
                                "pending_outcome": True}},
        {"id": "f2", "source": {"text": "Lives in Bristol", "fact_type": "identity"}},
    ]
    out = _summarize_existing(rows)
    assert "id=f1 [pending]" in out
    assert "id=f2 [pending]" not in out


def test_pending_outcome_is_persisted_on_the_semantic_doc():
    es = _FakeES()
    write_memory(es, user_id="sarah", memory_type="semantic",
                 text="Assistant advised a static IP; outcome not yet confirmed.",
                 fact_type="world", pending_outcome=True)
    assert es.indexed[0]["document"]["pending_outcome"] is True


def test_pending_outcome_is_absent_unless_set():
    """Every existing document predates the field and must read as not pending."""
    es = _FakeES()
    write_memory(es, user_id="sarah", memory_type="semantic", text="x", fact_type="identity")
    assert "pending_outcome" not in es.indexed[0]["document"]


def test_pending_outcome_reaches_the_agent_payload():
    from app.atlas.tools import dispatch

    class _RecallES(_FakeES):
        def search(self, **kwargs):
            return {"hits": {"hits": [{
                "_id": "f1", "_index": "atlas_memory_semantic",
                "_score": 1.0,
                "_source": {"text": "Advised a static IP", "fact_type": "world",
                            "pending_outcome": True, "created_at": "2026-07-27T10:00:00+00:00"},
            }]}}

        def inference(self, **kwargs):
            raise RuntimeError("no reranker in unit tests")

    es = _RecallES()
    es.inference = type("I", (), {"inference": lambda *a, **k: (_ for _ in ()).throw(RuntimeError())})()
    out = dispatch(es, user_id="sarah", name="recall_memory",
                   arguments={"query": "static ip", "memory_types": ["semantic"], "k": 5})
    assert out["hits"][0]["pending_outcome"] is True


def test_agent_prompt_tells_it_to_ask_rather_than_assume():
    from app.atlas.agent import SYSTEM_PROMPT_TEMPLATE
    assert "pending_outcome: true" in SYSTEM_PROMPT_TEMPLATE
    assert "Do NOT assume it worked" in SYSTEM_PROMPT_TEMPLATE
