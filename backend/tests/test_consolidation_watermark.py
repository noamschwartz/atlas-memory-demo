"""Tests for the per-user consolidation watermark (`app.atlas.memory.state`).

The behaviour that matters most here is the degradation path. `atlas_memory_state`
is a new index, and an existing deployment's application API key will not have
access to it until it is provisioned. If an unreadable watermark were treated as
"now", `episodes_since` would match nothing and consolidation would silently stop
running. These tests pin the contract that an unavailable store yields None, so
the caller falls back to the previous recent-window behaviour.
"""

from __future__ import annotations

import pytest
from elasticsearch import NotFoundError

from app.atlas.memory.state import (
    ensure_watermark,
    episodes_since,
    get_watermark,
    set_watermark,
)


class _FakeES:
    """Minimal stand-in recording calls and replaying scripted outcomes."""

    def __init__(self, *, get_result=None, get_exc=None, index_exc=None, hits=None):
        self._get_result = get_result
        self._get_exc = get_exc
        self._index_exc = index_exc
        self._hits = hits or []
        self.indexed: list[dict] = []
        self.searches: list[dict] = []

    def get(self, **kwargs):
        if self._get_exc:
            raise self._get_exc
        return self._get_result

    def index(self, **kwargs):
        if self._index_exc:
            raise self._index_exc
        self.indexed.append(kwargs)
        return {"result": "created"}

    def search(self, **kwargs):
        self.searches.append(kwargs)
        return {"hits": {"hits": self._hits}}


def _not_found() -> NotFoundError:
    return NotFoundError("not found", meta=None, body=None)


# ---------------------------------------------------------------------------
# get_watermark
# ---------------------------------------------------------------------------

def test_get_watermark_returns_stored_value():
    es = _FakeES(get_result={"_source": {"last_consolidated_at": "2026-07-01T00:00:00+00:00"}})
    assert get_watermark(es, "sarah") == "2026-07-01T00:00:00+00:00"


def test_get_watermark_missing_doc_is_none_not_an_error():
    es = _FakeES(get_exc=_not_found())
    assert get_watermark(es, "sarah") is None


def test_get_watermark_swallows_transport_errors():
    """A watermark read must never take down a chat turn."""
    es = _FakeES(get_exc=RuntimeError("403 unauthorized for index atlas_memory_state"))
    assert get_watermark(es, "sarah") is None


# ---------------------------------------------------------------------------
# set_watermark
# ---------------------------------------------------------------------------

def test_set_watermark_writes_doc_keyed_by_user_and_reports_success():
    es = _FakeES()
    assert set_watermark(es, "sarah", "2026-07-01T00:00:00+00:00") is True
    (call,) = es.indexed
    assert call["id"] == "sarah"
    assert call["document"]["user_id"] == "sarah"
    assert call["document"]["last_consolidated_at"] == "2026-07-01T00:00:00+00:00"
    assert call["refresh"] is True


def test_set_watermark_reports_failure_rather_than_raising():
    es = _FakeES(index_exc=RuntimeError("403 unauthorized"))
    assert set_watermark(es, "sarah", "2026-07-01T00:00:00+00:00") is False


# ---------------------------------------------------------------------------
# ensure_watermark -- the degradation contract
# ---------------------------------------------------------------------------

def test_ensure_watermark_returns_existing_without_writing():
    es = _FakeES(get_result={"_source": {"last_consolidated_at": "2026-06-01T00:00:00+00:00"}})
    assert ensure_watermark(es, "sarah") == "2026-06-01T00:00:00+00:00"
    assert es.indexed == [], "must not overwrite an existing watermark"


def test_ensure_watermark_initialises_to_now_when_absent():
    """Initialising to now (not the epoch) is what makes this non-breaking:
    existing episodic history counts as already consolidated, so upgrading does
    not trigger a re-extraction storm."""
    es = _FakeES(get_exc=_not_found())
    got = ensure_watermark(es, "sarah")
    assert got is not None
    assert len(es.indexed) == 1
    assert es.indexed[0]["document"]["last_consolidated_at"] == got


def test_ensure_watermark_returns_none_when_store_unavailable():
    """The critical case: unreadable AND unwritable store must yield None, so the
    caller falls back to the legacy path instead of consolidating nothing."""
    es = _FakeES(
        get_exc=RuntimeError("403 unauthorized"),
        index_exc=RuntimeError("403 unauthorized"),
    )
    assert ensure_watermark(es, "sarah") is None


# ---------------------------------------------------------------------------
# episodes_since
# ---------------------------------------------------------------------------

def test_episodes_since_filters_strictly_after_and_sorts_oldest_first():
    es = _FakeES(hits=[{"_id": "e1", "_source": {"text": "first"}}])
    out = episodes_since(es, user_id="sarah", since="2026-07-01T00:00:00+00:00", limit=30)

    (call,) = es.searches
    body = call["body"]
    filters = body["query"]["bool"]["filter"]
    assert {"term": {"user_id": "sarah"}} in filters
    assert {"range": {"timestamp": {"gt": "2026-07-01T00:00:00+00:00"}}} in filters, \
        "must be strictly greater-than so the boundary episode is not reprocessed"
    assert body["sort"] == [{"timestamp": "asc"}], \
        "oldest-first: the consolidation prompt reasons about event order"
    assert body["size"] == 30
    assert out == [{"id": "e1", "source": {"text": "first"}}]


def test_episodes_since_excludes_embeddings_from_source():
    es = _FakeES(hits=[])
    episodes_since(es, user_id="sarah", since="2026-07-01T00:00:00+00:00", limit=5)
    assert es.searches[0]["body"]["_source"] == {"excludes": ["semantic_content"]}
