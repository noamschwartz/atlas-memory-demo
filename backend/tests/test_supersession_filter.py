"""Regression tests for the include_superseded flag on recall.

These verify that `_hybrid_retriever` adds the soft-supersession exclusion
clause by default, and drops it when `include_superseded=True`. The flag
exists so retrospective queries ("places I've lived") can see archived
state; default recall must continue to hide superseded docs.

Pure structural tests, no ES connection needed.

Usage:
    cd backend
    pytest tests/test_supersession_filter.py -v
"""

import json

import pytest

from app.atlas.memory.operations import _hybrid_retriever


SUPERSEDED_CLAUSE = {
    "bool": {"must_not": {"exists": {"field": "superseded_by"}}}
}


def _filter_clauses(retriever: dict) -> list[dict]:
    """Pull the `filter` clauses out of the retriever's first bool query.

    Works for both the single-leg and RRF-wrapped forms because each leg's
    `standard.query` contains the function_score-wrapped bool we're checking.
    """
    if "rrf" in retriever:
        leg = retriever["rrf"]["retrievers"][0]
    else:
        leg = retriever
    bool_query = leg["standard"]["query"]["function_score"]["query"]["bool"]
    return bool_query.get("filter", [])


class TestDefaultHidesSuperseded:
    """Without the flag, the must_not-exists clause should be present."""

    def test_with_user_id(self):
        retriever = _hybrid_retriever(query="hello", user_id="sarah", k=10)
        clauses = _filter_clauses(retriever)
        assert SUPERSEDED_CLAUSE in clauses, (
            "default recall must hide superseded docs; clause missing"
        )

    def test_with_user_id_and_catalog(self):
        retriever = _hybrid_retriever(
            query="hello", user_id="sarah", k=10, include_catalog=True
        )
        clauses = _filter_clauses(retriever)
        assert SUPERSEDED_CLAUSE in clauses

    def test_without_user_id(self):
        retriever = _hybrid_retriever(query="hello", user_id=None, k=10)
        clauses = _filter_clauses(retriever)
        assert SUPERSEDED_CLAUSE in clauses


class TestIncludeSupersededDropsTheClause:
    """With the flag, the must_not-exists clause should not be present."""

    def test_with_user_id(self):
        retriever = _hybrid_retriever(
            query="hello", user_id="sarah", k=10, include_superseded=True
        )
        clauses = _filter_clauses(retriever)
        assert SUPERSEDED_CLAUSE not in clauses, (
            "include_superseded=True must drop the must_not exists clause"
        )

    def test_with_user_id_and_catalog(self):
        retriever = _hybrid_retriever(
            query="hello",
            user_id="sarah",
            k=10,
            include_catalog=True,
            include_superseded=True,
        )
        clauses = _filter_clauses(retriever)
        assert SUPERSEDED_CLAUSE not in clauses

    def test_without_user_id(self):
        retriever = _hybrid_retriever(
            query="hello", user_id=None, k=10, include_superseded=True
        )
        clauses = _filter_clauses(retriever)
        assert SUPERSEDED_CLAUSE not in clauses


class TestUserScopingUnchanged:
    """Independent of the flag, the user_id term must still scope the query.

    Regression guard: an over-eager edit that conditionally drops more than
    intended would also leak across tenants. DLS is the production guarantee,
    but the in-code paranoia filter must remain in place too.
    """

    def test_default_carries_user_term(self):
        retriever = _hybrid_retriever(query="hello", user_id="sarah", k=10)
        clauses = _filter_clauses(retriever)
        user_terms = [c for c in clauses if c.get("term", {}).get("user_id")]
        assert any(c["term"]["user_id"] == "sarah" for c in user_terms), (
            "default recall must scope by user_id"
        )

    def test_include_superseded_carries_user_term(self):
        retriever = _hybrid_retriever(
            query="hello", user_id="sarah", k=10, include_superseded=True
        )
        clauses = _filter_clauses(retriever)
        user_terms = [c for c in clauses if c.get("term", {}).get("user_id")]
        assert any(c["term"]["user_id"] == "sarah" for c in user_terms), (
            "include_superseded must not weaken user-scoping"
        )
