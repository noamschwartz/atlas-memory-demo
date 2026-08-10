"""Retrieval-backed dedup.

The recency slice handed to the extractor is a window with a cliff: the fact one
position past the limit is invisible, so it can be neither deduplicated against
nor superseded. These tests pin the behaviour that removes the cliff, plus the
case a recency window structurally cannot catch, where two facts contradict each
other while sharing almost no vocabulary.
"""

from __future__ import annotations

import pytest

from app.atlas.dedup import _similarity, deduplicate


def _hit(_id, text, fact_type="identity"):
    return {"id": _id, "memory_type": "semantic", "score": 1.0,
            "source": {"text": text, "fact_type": fact_type}}


def _cand(text, **kw):
    return {"text": text, "fact_type": "identity", **kw}


@pytest.fixture
def wiring(monkeypatch):
    """Control what retrieval returns and what the judge decides."""
    state = {"neighbours": [], "verdicts": {}, "judge_calls": 0, "queries": []}

    def fake_neighbours(es, user_id, text, k=5):
        state["queries"].append(text)
        return state["neighbours"]

    def fake_judge(pairs, inference_id):
        state["judge_calls"] += 1
        return state["verdicts"]

    monkeypatch.setattr("app.atlas.dedup._neighbours", fake_neighbours)
    monkeypatch.setattr("app.atlas.dedup._judge", fake_judge)
    return state


# ---------------------------------------------------------------------------
# similarity
# ---------------------------------------------------------------------------

def test_identical_text_scores_one():
    assert _similarity("The customer owns a Hub v2.", "The customer owns a Hub v2.") == 1.0


def test_unrelated_text_scores_low():
    assert _similarity("The customer owns a Hub v2.", "The customer lives in Bristol.") < 0.5


def test_similarity_is_order_and_case_insensitive():
    assert _similarity("Owns a HUB", "hub a owns") == 1.0


# ---------------------------------------------------------------------------
# the near-identical short circuit
# ---------------------------------------------------------------------------

def test_near_identical_is_dropped_without_a_judge_call(wiring):
    wiring["neighbours"] = [_hit("f1", "The customer owns a Lumio Hub v2.")]
    kept, dropped, linked = deduplicate(
        None, user_id="sarah", candidates=[_cand("The customer owns a Lumio Hub v2.")]
    )
    assert kept == [] and linked == []
    assert dropped[0]["_duplicate_of"] == "f1"
    assert dropped[0]["_reason"] == "near-identical"
    assert wiring["judge_calls"] == 0, "exact duplicates must not cost an LLM call"


def test_the_cliff_case_a_recency_window_cannot_catch(wiring):
    """The whole point. An old fact outside the recency slice is still found,
    because neighbours are chosen by meaning rather than by age."""
    wiring["neighbours"] = [_hit("ancient", "The customer owns a Lumio Hub v2.")]
    _, dropped, _ = deduplicate(
        None, user_id="sarah", candidates=[_cand("The customer owns a Lumio Hub v2.")]
    )
    assert dropped and dropped[0]["_duplicate_of"] == "ancient"


def test_no_neighbours_means_keep(wiring):
    wiring["neighbours"] = []
    kept, dropped, _ = deduplicate(None, user_id="sarah", candidates=[_cand("Something new.")])
    assert len(kept) == 1 and dropped == []
    assert wiring["judge_calls"] == 0


# ---------------------------------------------------------------------------
# judged outcomes
# ---------------------------------------------------------------------------

def test_judged_duplicate_is_dropped(wiring):
    wiring["neighbours"] = [_hit("f1", "The customer has a newborn son called Theo.")]
    wiring["verdicts"] = {1: {"n": 1, "decision": "duplicate", "existing_id": "f1"}}
    kept, dropped, _ = deduplicate(
        None, user_id="sarah", candidates=[_cand("The customer recently became a parent to Theo.")]
    )
    assert kept == []
    assert dropped[0]["_reason"] == "judged duplicate"


def test_judged_update_recovers_a_supersession_the_extractor_missed(wiring):
    """The contradiction a recency window cannot see: these two share almost no
    vocabulary, so nothing lexical or age-ordered would pair them."""
    wiring["neighbours"] = [_hit("old", "The customer prefers to be contacted by email.")]
    wiring["verdicts"] = {1: {"n": 1, "decision": "update", "existing_id": "old"}}
    kept, dropped, linked = deduplicate(
        None, user_id="sarah",
        candidates=[_cand("The customer asked us to stop sending them email.")],
    )
    assert dropped == []
    assert kept[0]["supersedes_id"] == "old"
    assert kept[0]["contradiction"] == "natural"
    assert len(linked) == 1


def test_judged_distinct_is_kept_untouched(wiring):
    wiring["neighbours"] = [_hit("f1", "The customer's hub is offline.")]
    wiring["verdicts"] = {1: {"n": 1, "decision": "distinct", "existing_id": None}}
    kept, dropped, linked = deduplicate(
        None, user_id="sarah", candidates=[_cand("The customer's doorbell is offline.")]
    )
    assert len(kept) == 1 and dropped == [] and linked == []
    assert "supersedes_id" not in kept[0]


def test_an_extractor_supersession_is_not_overwritten(wiring):
    wiring["neighbours"] = [_hit("other", "Unrelated fact.")]
    wiring["verdicts"] = {1: {"n": 1, "decision": "update", "existing_id": "other"}}
    kept, _, linked = deduplicate(
        None, user_id="sarah",
        candidates=[_cand("The customer lives in Edinburgh.", supersedes_id="chosen-by-extractor")],
    )
    assert kept[0]["supersedes_id"] == "chosen-by-extractor"
    assert linked == []


# ---------------------------------------------------------------------------
# safety
# ---------------------------------------------------------------------------

def test_a_hallucinated_id_is_ignored(wiring):
    """Attaching supersedes_id to an id we never retrieved would silently hide an
    unrelated fact from every future recall."""
    wiring["neighbours"] = [_hit("real", "Some fact.")]
    wiring["verdicts"] = {1: {"n": 1, "decision": "update", "existing_id": "not-a-real-id"}}
    kept, dropped, linked = deduplicate(
        None, user_id="sarah", candidates=[_cand("A different fact entirely.")]
    )
    assert len(kept) == 1 and dropped == [] and linked == []
    assert "supersedes_id" not in kept[0]


def test_a_hallucinated_duplicate_id_does_not_drop_the_fact(wiring):
    wiring["neighbours"] = [_hit("real", "Some fact.")]
    wiring["verdicts"] = {1: {"n": 1, "decision": "duplicate", "existing_id": "invented"}}
    kept, dropped, _ = deduplicate(
        None, user_id="sarah", candidates=[_cand("A different fact entirely.")]
    )
    assert len(kept) == 1 and dropped == [], "never drop on an unverifiable id"


def test_judge_failure_keeps_everything(monkeypatch):
    """A missed duplicate is recoverable. Discarding a real fact is not."""
    monkeypatch.setattr("app.atlas.dedup._neighbours",
                        lambda es, u, t, k=5: [_hit("f1", "Something vaguely related here.")])
    monkeypatch.setattr("app.atlas.dedup._judge",
                        lambda pairs, inference_id: {})
    kept, dropped, _ = deduplicate(None, user_id="sarah", candidates=[_cand("A brand new fact.")])
    assert len(kept) == 1 and dropped == []


def test_one_judge_call_covers_every_candidate(wiring):
    """Cost is one extra call per pass, not one per candidate."""
    wiring["neighbours"] = [_hit("f1", "Some loosely related existing fact.")]
    wiring["verdicts"] = {n: {"n": n, "decision": "distinct", "existing_id": None} for n in (1, 2, 3)}
    kept, _, _ = deduplicate(
        None, user_id="sarah",
        candidates=[_cand("Fact one here."), _cand("Fact two here."), _cand("Fact three here.")],
    )
    assert len(kept) == 3
    assert wiring["judge_calls"] == 1


def test_blank_candidates_are_skipped(wiring):
    kept, dropped, _ = deduplicate(
        None, user_id="sarah", candidates=[_cand("   "), _cand("")]
    )
    assert kept == [] and dropped == []


def test_empty_input_short_circuits(wiring):
    assert deduplicate(None, user_id="sarah", candidates=[]) == ([], [], [])
    assert wiring["queries"] == []


def test_the_candidate_text_is_what_gets_searched(wiring):
    """Neighbours must be nearest to the CANDIDATE, not to the conversation."""
    wiring["neighbours"] = []
    deduplicate(None, user_id="sarah", candidates=[_cand("The customer owns a barge.")])
    assert wiring["queries"] == ["The customer owns a barge."]
