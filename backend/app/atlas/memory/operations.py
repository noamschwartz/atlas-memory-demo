"""Atlas memory operations: write, recall, forget, list.

Storage is split across three indices (episodic / semantic / procedural).
Recall uses an RRF hybrid retriever fusing BM25 over `text` with the
`semantic` query against `semantic_content` (Jina v5 dense embeddings).
"""

from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Iterable, Literal

from elasticsearch import Elasticsearch, NotFoundError
from elasticsearch import helpers as es_helpers

from .constants import (
    CATALOG_SOURCE_PRIOR,
    CORE_MEMORY_DEDUP_THRESHOLD,
    CORE_MEMORY_ENABLED,
    CORE_MEMORY_LIMIT,
    CORE_MEMORY_RECENT_SLOTS,
    CORE_MEMORY_SALIENT_SLOTS,
    DECAY_EPISODIC_OFFSET,
    DECAY_EPISODIC_SCALE,
    DECAY_GAUSS,
    DECAY_SEMANTIC_OFFSET,
    DECAY_SEMANTIC_SCALE,
    INDEX_CATALOG,
    INDEX_EPISODIC,
    INDEX_PROCEDURAL,
    INDEX_SEMANTIC,
    MEMORY_INDICES,
    RECALL_OVER_FETCH_K,
    RERANKER_INFERENCE_ID,
    SUPERSEDE_CONFIDENCE_PENALTY,
    USE_COUNT_BOOST_WEIGHT,
)

logger = logging.getLogger(__name__)

MemoryType = Literal["episodic", "semantic", "procedural"]


def _index_for(memory_type: str) -> str:
    try:
        return MEMORY_INDICES[memory_type]
    except KeyError as exc:
        raise ValueError(
            f"unknown memory_type {memory_type!r}; must be one of "
            f"{sorted(MEMORY_INDICES)}"
        ) from exc


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_memory(
    es: Elasticsearch,
    *,
    user_id: str,
    memory_type: MemoryType,
    text: str,
    agent_id: str | None = None,
    session_id: str | None = None,
    event_type: str | None = None,
    role: str | None = None,
    fact_type: str | None = None,
    confidence: float | None = None,
    source_episodes: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
    name: str | None = None,
    description: str | None = None,
    steps: list[dict[str, Any]] | None = None,
    supersedes_id: str | None = None,
    contradiction: str | None = None,
    allow_retraction: bool = True,
    pending_outcome: bool | None = None,
    valid_from: str | None = None,
    valid_to: str | None = None,
    refresh: bool = False,
) -> dict[str, str]:
    """Insert a memory document.

    `semantic_text` auto-generates Jina v5 embeddings at index time.

    When `supersedes_id` is provided on a semantic write, the old fact is
    soft-marked as superseded (`superseded_by`, `superseded_at`) rather than
    hard-deleted. Recall filters superseded facts out by default, keeping the
    audit trail intact.

    The `SUPERSEDE_CONFIDENCE_PENALTY` is applied to the new fact's confidence
    only when `contradiction == "harsh"` — i.e., the customer explicitly
    denied or corrected the prior fact. Natural updates (moved, upgraded,
    preference change) are written at full confidence.
    """
    index = _index_for(memory_type)
    doc_id = str(uuid.uuid4())
    now = _now_iso()
    doc: dict[str, Any] = {"user_id": user_id}

    if memory_type == "episodic":
        doc.update(
            text=text,
            agent_id=agent_id,
            session_id=session_id,
            event_type=event_type or "user_message",
            role=role or "user",
            timestamp=now,
            metadata=metadata or {},
        )
    elif memory_type == "semantic":
        base_confidence = confidence if confidence is not None else 1.0
        if supersedes_id and contradiction == "harsh":
            base_confidence = max(0.0, base_confidence - SUPERSEDE_CONFIDENCE_PENALTY)
        doc.update(
            text=text,
            fact_type=fact_type or "preference",
            confidence=base_confidence,
            source_episodes=source_episodes or [],
            created_at=now,
            last_used_at=now,
            use_count=0,
            metadata=metadata or {},
        )
        # Validity time: when the fact was true in the world, as distinct
        # from created_at / superseded_at, which record when the system
        # LEARNED it. The two coincide only if customers report changes
        # immediately. Someone who moved in November and mentions it in
        # January leaves a 14-month gap, and without these fields a
        # point-in-time question is answered from the wrong interval.
        if valid_from:
            doc["valid_from"] = valid_from
        if valid_to:
            doc["valid_to"] = valid_to
        if pending_outcome is not None:
            # Marks a record of advice whose result was never established.
            # Queryable so a later pass can resolve it rather than having to
            # rediscover it by matching prose.
            doc["pending_outcome"] = bool(pending_outcome)
        if supersedes_id:
            doc["supersedes"] = supersedes_id
    else:  # procedural
        doc.update(
            name=name or text[:60],
            trigger_text=text,
            description=description or "",
            steps=steps or [],
            version=1,
            success_count=0,
            failure_count=0,
            created_at=now,
            metadata=metadata or {},
        )

    es.index(index=index, id=doc_id, document=doc, refresh=refresh)

    if memory_type == "semantic" and supersedes_id:
        try:
            # `retracted` distinguishes the two things supersession was being
            # asked to represent with one mechanism:
            #
            #   natural  — the fact WAS true and has stopped being true
            #              ("we moved to Edinburgh"). Prior state. Legitimate
            #              history, safe to recount on a retrospective question.
            #   harsh    — the fact was NEVER true ("I never lived in Bristol,
            #              that was my sister"). A retraction, not history.
            #
            # Before this, both wrote byte-identical updates to the old
            # document, and the agent rule "hits carrying superseded_at are
            # archived state; treat them as the prior state" then narrated a
            # denied fact straight back to the user as something they had done.
            # `retracted` is only set from evidence we can trust. A harsh
            # contradiction is a strong claim — it tells the agent never to
            # recount the old fact as something the customer did — so it is
            # accepted only when the denial was observed first-hand, i.e. the
            # customer's own words were in context when the call was made.
            #
            # Consolidation passes allow_retraction=False. It infers intent
            # second-hand from a window of stored episodes, and a misread there
            # would permanently flag a legitimate memory as never-true. It still
            # gets the confidence penalty, which is the soft version of the same
            # signal and is recoverable.
            superseded_doc: dict[str, Any] = {
                "superseded_by": doc_id,
                "superseded_at": now,
            }
            if contradiction == "harsh" and allow_retraction:
                superseded_doc["retracted"] = True
            es.update(
                index=INDEX_SEMANTIC,
                id=supersedes_id,
                doc=superseded_doc,
                refresh=refresh,
            )
        except NotFoundError:
            logger.warning("supersedes_id %s not found in semantic index", supersedes_id)
        except Exception:  # noqa: BLE001
            logger.warning("failed to mark %s as superseded", supersedes_id, exc_info=True)

    return {"id": doc_id, "memory_type": memory_type, "index": index}


def _user_or_catalog_filter(user_id: str | None) -> dict[str, Any]:
    """Filter clause that admits docs belonging to `user_id` OR the shared
    catalog (catalog docs have no `user_id` field)."""
    if not user_id:
        return {"match_all": {}}
    return {
        "bool": {
            "should": [
                {"term": {"user_id": user_id}},
                {"bool": {"must_not": {"exists": {"field": "user_id"}}}},
            ],
            "minimum_should_match": 1,
        }
    }


def _decay_script() -> dict[str, Any]:
    """Painless script combining time decay and a use-count boost.

    Cross-index queries can't use `gauss` directly because ES parses the
    field name against every index's mapping. This script safely picks the
    right multiplier per doc:
      - episodic: timestamp (decay only)
      - semantic: last_used_at (else created_at) for decay, plus a log boost
        on use_count so frequently-recalled facts rank higher
      - catalog: returns CATALOG_SOURCE_PRIOR — soft tilt below 1.0 so user
        memory wins on near-ties (only fires when include_catalog=True)
      - procedural: returns 1.0 (no decay, no source prior)
    """
    return {
        "script": {
            "source": """
                String idx = doc['_index'].value;
                double decay = 1.0;
                double useBoost = 1.0;
                // Use doubles throughout the math so scale^2 doesn't overflow
                // long arithmetic (730d in ms ~6.3e10, squared exceeds long max).
                double lnInvDecay = Math.log(1.0 / params.decay);
                if (idx == params.episodic_index) {
                    if (doc['timestamp'].empty) { return 1.0; }
                    double ageMs = (double)(params.now - doc['timestamp'].value.toInstant().toEpochMilli());
                    double scaleMs = (double) params.episodic_scale_ms;
                    double offsetMs = (double) params.episodic_offset_ms;
                    double effAge = ageMs - offsetMs;
                    if (effAge > 0) {
                        double sigmaSq = (scaleMs * scaleMs) / (2.0 * lnInvDecay);
                        decay = Math.exp(-(effAge * effAge) / (2.0 * sigmaSq));
                    }
                } else if (idx == params.semantic_index) {
                    long t;
                    if (!doc['last_used_at'].empty) {
                        t = doc['last_used_at'].value.toInstant().toEpochMilli();
                    } else if (!doc['created_at'].empty) {
                        t = doc['created_at'].value.toInstant().toEpochMilli();
                    } else {
                        t = params.now;
                    }
                    double ageMs = (double)(params.now - t);
                    double scaleMs = (double) params.semantic_scale_ms;
                    double offsetMs = (double) params.semantic_offset_ms;
                    double effAge = ageMs - offsetMs;
                    if (effAge > 0) {
                        double sigmaSq = (scaleMs * scaleMs) / (2.0 * lnInvDecay);
                        decay = Math.exp(-(effAge * effAge) / (2.0 * sigmaSq));
                    }
                    long uc = doc['use_count'].empty ? 0L : doc['use_count'].value;
                    if (uc > 0) {
                        useBoost = 1.0 + Math.log10(1.0 + uc) * params.use_count_weight;
                    }
                } else if (idx == params.catalog_index) {
                    return params.catalog_prior;
                } else {
                    return 1.0;
                }
                return decay * useBoost;
            """,
            "params": {
                "now": _now_ms(),
                "decay": DECAY_GAUSS,
                "episodic_index": INDEX_EPISODIC,
                "semantic_index": INDEX_SEMANTIC,
                "catalog_index": INDEX_CATALOG,
                "episodic_scale_ms": _duration_to_ms(DECAY_EPISODIC_SCALE),
                "episodic_offset_ms": _duration_to_ms(DECAY_EPISODIC_OFFSET),
                "semantic_scale_ms": _duration_to_ms(DECAY_SEMANTIC_SCALE),
                "semantic_offset_ms": _duration_to_ms(DECAY_SEMANTIC_OFFSET),
                "use_count_weight": USE_COUNT_BOOST_WEIGHT,
                "catalog_prior": CATALOG_SOURCE_PRIOR,
            },
        }
    }


def _now_ms() -> int:
    return int(datetime.now(timezone.utc).timestamp() * 1000)


def _duration_to_ms(s: str) -> int:
    """Convert ES duration string (e.g. '30d', '7d') to milliseconds."""
    unit = s[-1]
    value = int(s[:-1])
    if unit == "d":
        return value * 86400 * 1000
    if unit == "h":
        return value * 3600 * 1000
    if unit == "m":
        return value * 60 * 1000
    raise ValueError(f"unsupported duration unit in {s!r}")


def _wrap_with_decay(query: dict[str, Any]) -> dict[str, Any]:
    """Wrap a query in a function_score that adds time-decay per index."""
    return {
        "function_score": {
            "query": query,
            "script_score": _decay_script(),
            "boost_mode": "multiply",
        }
    }


def _hybrid_retriever(
    query: str,
    user_id: str | None,
    k: int,
    include_catalog: bool = False,
    include_superseded: bool = False,
    text_leg_on: bool = True,
    semantic_leg_on: bool = True,
) -> dict[str, Any]:
    """Build an RRF retriever combining BM25 + semantic against `semantic_content`.

    Each leg is wrapped in a function_score that applies time-decay per index
    (recent episodic events ranked higher; recently-used semantic facts ranked
    higher; procedurals and catalog unaffected).

    When `include_catalog` is True, the user_id filter is widened to include
    the shared catalog index (whose docs lack `user_id`).

    When `include_superseded` is True, the soft-supersession filter is dropped
    so retrospective queries ("places I've lived") can see archived facts.

    `text_leg_on` / `semantic_leg_on` allow disabling either leg for ablation.
    With only one leg the RRF wrapper is dropped — the single retriever is
    returned directly so its native scores reach the reranker untouched.
    """
    if not (text_leg_on or semantic_leg_on):
        raise ValueError("at least one of text_leg_on / semantic_leg_on must be True")

    if user_id and not include_catalog:
        base_filter: list[dict[str, Any]] = [{"term": {"user_id": user_id}}]
    elif user_id and include_catalog:
        base_filter = [_user_or_catalog_filter(user_id)]
    else:
        base_filter = []

    # Hide soft-superseded semantic facts from results unless include_superseded
    # is set (e.g. for retrospective queries). Other indices don't have this
    # field, so the clause is a no-op for them.
    if not include_superseded:
        base_filter = base_filter + [
            {"bool": {"must_not": {"exists": {"field": "superseded_by"}}}}
        ]

    text_leg: dict[str, Any] = {
        "standard": {
            "query": _wrap_with_decay({
                "bool": {
                    "must": [
                        {
                            "multi_match": {
                                "query": query,
                                "fields": [
                                    "text^2",
                                    "title^2",
                                    "name",
                                    "description",
                                    "trigger_text",
                                ],
                            }
                        }
                    ],
                    "filter": base_filter,
                }
            })
        }
    }

    semantic_leg: dict[str, Any] = {
        "standard": {
            "query": _wrap_with_decay({
                "bool": {
                    "must": [
                        {
                            "semantic": {
                                "field": "semantic_content",
                                "query": query,
                            }
                        }
                    ],
                    "filter": base_filter,
                }
            })
        }
    }

    legs: list[dict[str, Any]] = []
    if text_leg_on:
        legs.append(text_leg)
    if semantic_leg_on:
        legs.append(semantic_leg)

    if len(legs) == 1:
        # Single leg — skip the RRF wrapper so the native score reaches the
        # reranker directly. (Ablation paths only.)
        return legs[0]

    return {
        "rrf": {
            "retrievers": legs,
            # Bigger window so RRF fuses across more candidates before the
            # reranker re-orders them. rank_constant 30 is tighter than the
            # default 60 — top-ranked items dominate the fused score more.
            "rank_window_size": max(RECALL_OVER_FETCH_K, k * 8),
            "rank_constant": 30,
        }
    }


def _rerank(
    es: Elasticsearch,
    *,
    query: str,
    candidates: list[dict[str, Any]],
    k: int,
) -> list[dict[str, Any]]:
    """Re-order RRF candidates with the Jina reranker and truncate to top-k.

    Returns the input candidate dicts in their new order. Each kept candidate
    has its `score` overwritten with the reranker's relevance_score (higher =
    more relevant; can be negative) and its `rank` re-numbered 1..k.

    Falls through to a truncated RRF order if the reranker call fails — recall
    quality stays at least as good as before reranking was added.
    """
    if not candidates:
        return candidates

    texts: list[str] = []
    for c in candidates:
        src = c.get("source") or {}
        # For procedurals, the reranker only sees `trigger_text` by default —
        # which is one sentence and tends to lose to richer episodic prose.
        # Fold in name + description + the first step instruction to give the
        # reranker enough signal. Episodic / semantic use `text` (catalog
        # uses `title` + `text`).
        if "trigger_text" in src:
            parts = [
                src.get("name") or "",
                src.get("trigger_text") or "",
                src.get("description") or "",
            ]
            steps = src.get("steps") or []
            if steps and isinstance(steps[0], dict):
                parts.append(steps[0].get("instruction") or "")
            text = " ".join(p for p in parts if p)
        else:
            text = (
                src.get("text")
                or " ".join(filter(None, [src.get("title"), src.get("text")]))
                or ""
            )
        texts.append(text)
    try:
        resp = es.inference.inference(
            inference_id=RERANKER_INFERENCE_ID,
            input=texts,
            query=query,
        )
    except Exception:  # noqa: BLE001
        logger.warning("rerank call failed; falling back to RRF order", exc_info=True)
        return candidates[:k]

    ranked = resp.get("rerank") or []
    ordered: list[dict[str, Any]] = []
    for new_rank, entry in enumerate(ranked[:k], start=1):
        idx = entry.get("index")
        if idx is None or idx < 0 or idx >= len(candidates):
            continue
        c = dict(candidates[idx])  # shallow copy so we don't mutate caller's list
        c["score"] = float(entry.get("relevance_score") or 0.0)
        c["rank"] = new_rank
        ordered.append(c)
    if not ordered:
        # Reranker returned nothing usable — fall back to RRF.
        return candidates[:k]
    return ordered


def _bump_recall_stats(es: Elasticsearch, hits: list[dict[str, Any]]) -> None:
    """Bump last_used_at and use_count on top semantic/procedural hits.

    Uses partial-document updates because scripted updates are rejected on
    indices that contain `semantic_text` fields. The increment reads the
    current `use_count` from the recall hit's `_source` (already in memory)
    and writes the incremented value back; not atomic, but acceptable for a
    fire-and-forget feedback signal.

    Failures are logged but don't block recall. Per-action errors are
    surfaced so the cause is visible. The recall feedback loop only matters
    when the agent path opts in via `update_stats=True`; the eval harness
    leaves this off so re-runs are deterministic.
    """
    actions: list[dict[str, Any]] = []
    now = _now_iso()
    for hit in hits:
        if hit["memory_type"] not in ("semantic", "procedural"):
            continue
        current = int(((hit.get("source") or {}).get("use_count") or 0))
        actions.append({
            "_op_type": "update",
            "_index": hit["index"],
            "_id": hit["id"],
            "doc": {
                "last_used_at": now,
                "use_count": current + 1,
            },
        })
    if not actions:
        return
    try:
        success, errors = es_helpers.bulk(
            es,
            actions,
            raise_on_error=False,
            raise_on_exception=False,
            # refresh=False, not "wait_for". This bulk runs synchronously inside
            # recall_memory, which sits on the user-visible path (the agent
            # pre-recalls on every turn). "wait_for" blocks until the shard
            # refreshes — up to index.refresh_interval, 1s by default — and it
            # did so on every single recall, for a fire-and-forget statistics
            # write whose only consumer is a *future* recall's ranking. Nothing
            # in the current turn reads use_count or last_used_at, so there is
            # nothing to wait for. Elastic's own guidance: "Unless you have a
            # good reason to wait for the change to become visible, always use
            # refresh=false."
            refresh=False,
            stats_only=False,
        )
        if errors:
            logger.warning("bump_recall_stats: %d update(s) failed: %r", len(errors), errors[:3])
    except Exception:  # noqa: BLE001
        logger.warning("bump_recall_stats failed", exc_info=True)


def _rrf_fetch(
    es: Elasticsearch,
    *,
    query: str,
    indices: list[str],
    user_id: str | None,
    include_catalog: bool,
    fetch_k: int,
    include_superseded: bool = False,
    text_leg_on: bool = True,
    semantic_leg_on: bool = True,
) -> list[dict[str, Any]]:
    """Run one RRF hybrid search and shape the hits into recall_memory's
    candidate format."""
    body = {
        "size": fetch_k,
        "retriever": _hybrid_retriever(
            query, user_id, fetch_k, include_catalog,
            include_superseded=include_superseded,
            text_leg_on=text_leg_on, semantic_leg_on=semantic_leg_on,
        ),
        "_source": {"excludes": ["semantic_content"]},
    }
    response = es.search(index=",".join(indices), body=body, ignore_unavailable=True)
    out: list[dict[str, Any]] = []
    for rrf_rank, hit in enumerate(response["hits"]["hits"], start=1):
        out.append(
            {
                "id": hit["_id"],
                "index": hit["_index"],
                "memory_type": _memory_type_for_index(hit["_index"]),
                "score": hit.get("_score"),
                "rank": rrf_rank,
                "source": hit.get("_source", {}),
            }
        )
    return out


def recall_memory(
    es: Elasticsearch,
    *,
    query: str,
    user_id: str | None = None,
    memory_types: Iterable[MemoryType] | None = None,
    k: int = 10,
    include_catalog: bool = False,
    include_superseded: bool = False,
    update_stats: bool = False,
    stats_es: Elasticsearch | None = None,
    rerank: bool = True,
    text_leg: bool = True,
    semantic_leg: bool = True,
) -> list[dict[str, Any]]:
    """Hybrid recall across one or more memory indices.

    Two-stage retrieval:
      1. RRF over BM25 + Jina v5 semantic. Fetches up to RECALL_OVER_FETCH_K
         candidates so the reranker has enough signal to work with. Set
         `text_leg=False` or `semantic_leg=False` to disable either leg for
         ablation; with only one leg the RRF wrapper is skipped.
      2. Jina reranker re-orders the candidates against the user query and
         returns the top-k. Set `rerank=False` to skip — useful for ablation.

    When `include_catalog` is True, the shared `atlas_catalog` index is
    included in the retrieval target. Catalog docs are user-agnostic, so
    their hits will surface alongside per-user memory.

    When `include_superseded` is True, soft-superseded semantic facts are not
    filtered out. Use for retrospective queries ("places I've lived", "fixes
    we've tried before") where prior state is the answer. Default False so
    live conversations see only current state.

    When `update_stats` is True, the FINAL top-K (post-rerank) get their
    `last_used_at` and `use_count` bumped, biasing future recalls toward
    recently-used memory. Default False so eval harnesses remain
    deterministic.

    `stats_es` is an optional separate client used only for the stat-bump
    update. Pass an admin client here when `es` is a DLS-scoped read-only
    user client that lacks index-write privileges. If omitted, the same
    `es` client is used for both reads and the bump.
    """
    # Empty queries can't go through the semantic_text inference endpoint
    # (Jina rejects empty input). Return no hits rather than raising.
    if not query or not query.strip():
        return []

    if not memory_types:
        memory_types = list(MEMORY_INDICES.keys())
    indices = [_index_for(t) for t in memory_types]
    if include_catalog:
        indices.append(INDEX_CATALOG)

    # Over-fetch from RRF so the reranker has signal to work with.
    fetch_k = max(RECALL_OVER_FETCH_K, k) if rerank else k

    candidates = _rrf_fetch(
        es,
        query=query,
        indices=indices,
        user_id=user_id,
        include_catalog=include_catalog,
        include_superseded=include_superseded,
        fetch_k=fetch_k,
        text_leg_on=text_leg,
        semantic_leg_on=semantic_leg,
    )

    hits = _rerank(es, query=query, candidates=candidates, k=k) if rerank else candidates[:k]

    if update_stats and hits:
        _bump_recall_stats(stats_es or es, hits)
    return hits


def _memory_type_for_index(index: str) -> str:
    for memory_type, name in MEMORY_INDICES.items():
        if name == index:
            return memory_type
    if index == INDEX_CATALOG:
        return "catalog"
    return "unknown"


def list_memories(
    es: Elasticsearch,
    *,
    user_id: str,
    memory_type: MemoryType,
    limit: int = 50,
    include_superseded: bool = True,
) -> list[dict[str, Any]]:
    """Recent memories for a user, newest first.

    `include_superseded` defaults to True so the existing callers are unchanged:
    the `/api/memory/list` route feeds the Memory Inspector, and hiding
    superseded facts there would remove the audit view that the whole
    supersession design exists to provide.

    Consolidation passes False. Handing the consolidation LLM a comparison set
    that still contains archived facts lets it re-supersede an already-archived
    document, and pads a finite window with entries that can never be
    legitimately matched against.
    """
    index = _index_for(memory_type)
    sort_field = (
        "timestamp"
        if memory_type == "episodic"
        else "created_at"
    )
    query: dict[str, Any] = {"bool": {"filter": [{"term": {"user_id": user_id}}]}}
    if not include_superseded:
        query["bool"]["must_not"] = [{"exists": {"field": "superseded_by"}}]

    response = es.search(
        index=index,
        body={
            "size": limit,
            "query": query,
            "sort": [{sort_field: "desc"}],
            "_source": {"excludes": ["semantic_content"]},
        },
    )
    return [
        {"id": h["_id"], "source": h["_source"]}
        for h in response["hits"]["hits"]
    ]


def _dedupe_core_facts(facts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Drop near-duplicate facts, keeping the first occurrence.

    Consolidation duplication is measurable on a live corpus (28 near-duplicate
    pairs across 197 live facts), and several land in the same core block: one
    persona had "shares her home with her partner and their newborn son Theo"
    twice, byte-identical, plus five separate phrasings of "stability matters
    because there is a newborn". Paying for both copies of every duplicate on
    every single turn is the worst place to absorb that cost, so the block is
    deduplicated at selection time.

    Uses token-set Jaccard rather than an embedding call: this runs on every
    turn, and the duplicates in question are lexically near-identical because
    they were re-extracted from the same episodes.
    """
    kept: list[dict[str, Any]] = []
    seen_tokens: list[set[str]] = []
    for f in facts:
        tokens = set(re.findall(r"[a-z0-9]+", f["text"].lower()))
        if not tokens:
            continue
        if any(
            len(tokens & prev) / len(tokens | prev) >= CORE_MEMORY_DEDUP_THRESHOLD
            for prev in seen_tokens
        ):
            continue
        kept.append(f)
        seen_tokens.append(tokens)
    return kept


def _select_core_facts(
    pool: list[dict[str, Any]],
    limit: int,
) -> list[dict[str, Any]]:
    """Choose which facts occupy the always-in-context block.

    Filled from three directions rather than one, because any single ordering
    has a blind spot. Newest-first lets recent churn evict foundational facts.
    Oldest-first buries what the customer said today. Neither reaches the
    middle, where a fact can be neither old enough nor new enough to qualify
    while still being the one the agent needs most.

    So: a recency quota, a salience quota keyed on how often a fact has actually
    been recalled, and the remainder to the oldest. Salience is the interesting
    one because it is earned rather than assumed. A fact with use_count nine has
    proven itself; a fact with use_count zero has not, and is skipped for that
    quota so the slots go to facts with real evidence behind them.
    """
    if len(pool) <= limit:
        return pool

    def created(f: dict[str, Any]) -> str:
        return f.get("created_at") or ""

    picked: dict[str, dict[str, Any]] = {}

    def take(ordered: list[dict[str, Any]], n: int) -> None:
        for fact in ordered:
            if len(picked) >= limit or n <= 0:
                return
            if fact["id"] in picked:
                continue
            picked[fact["id"]] = fact
            n -= 1

    # Newest first, so today's news is never invisible.
    take(sorted(pool, key=created, reverse=True), CORE_MEMORY_RECENT_SLOTS)

    # Then earned importance. Facts never recalled are excluded here: without
    # that guard every use_count is zero, ties break on age, and this quota
    # silently becomes a second foundations pass.
    used = [f for f in pool if (f.get("use_count") or 0) > 0]
    take(sorted(used, key=lambda f: (-(f.get("use_count") or 0), created(f))),
         CORE_MEMORY_SALIENT_SLOTS)

    # Whatever is left goes to the oldest, where stable attributes live.
    take(sorted(pool, key=created), limit)

    # Constraints first, then oldest first, so the rendered block reads
    # consistently regardless of which quota admitted each fact.
    return sorted(picked.values(), key=lambda f: (f.get("fact_type") or "", created(f)))


def core_memory(
    es: Elasticsearch,
    *,
    user_id: str,
    limit: int = CORE_MEMORY_LIMIT,
) -> list[dict[str, Any]]:
    """Facts that should be in context on every turn, regardless of the query.

    Retrieval is the wrong mechanism for a whole class of fact. A constraint
    like "the nursery must stay quiet between 19:00 and 07:00" is
    unconditionally relevant to what the agent should say, but its relevance is
    not *query-conditional*: it shares almost no vocabulary with "my hub keeps
    dropping off wifi", so neither BM25 nor the dense leg will surface it on
    that turn, and the cross-encoder scores candidates against the query, which
    guarantees it stays out. The fact was correctly stored, correctly typed, and
    had no path into the context.

    This is the tier Letta calls core memory, and that file-backed agent setups
    get from a static profile document. `fact_type` already carried the labels
    needed to build it here, written on every semantic fact, indexed as a
    keyword, and used in no query at all.

    Constraints are returned ahead of identity facts, because when the cap binds
    it should bite on biography rather than on a hard limit the agent must
    respect.
    """
    if not CORE_MEMORY_ENABLED:
        return []

    base_filter = [
        {"term": {"user_id": user_id}},
        {"terms": {"fact_type": ["constraint", "identity"]}},
    ]
    query = {
        "bool": {
            "filter": base_filter,
            "must_not": [{"exists": {"field": "superseded_by"}}],
        }
    }
    # One round trip, three orderings. A single sorted query cannot supply the
    # pool: fetching the oldest N would never show the newest fact, and at a few
    # hundred facts per user an over-fetch large enough to cover every ordering
    # stops being cheap.
    per_slice = limit * 2
    body = {"size": per_slice, "query": query, "_source": ["text", "fact_type", "created_at", "use_count"]}
    header: dict[str, Any] = {"index": INDEX_SEMANTIC}
    searches = [
        header, {**body, "sort": [{"created_at": "asc"}]},
        header, {**body, "sort": [{"created_at": "desc"}]},
        header, {**body, "sort": [{"use_count": "desc"}, {"created_at": "asc"}]},
    ]
    responses = es.msearch(searches=searches, index=INDEX_SEMANTIC)["responses"]

    pool: dict[str, dict[str, Any]] = {}
    for resp in responses:
        for hit in (resp.get("hits", {}) or {}).get("hits", []) or []:
            src = hit.get("_source") or {}
            text = (src.get("text") or "").strip()
            if not text:
                continue
            pool[hit["_id"]] = {
                "id": hit["_id"],
                "text": text,
                "fact_type": src.get("fact_type"),
                "created_at": src.get("created_at"),
                "use_count": src.get("use_count") or 0,
            }

    selected = _select_core_facts(_dedupe_core_facts(list(pool.values())), limit)
    return [
        {"id": f["id"], "text": f["text"], "fact_type": f["fact_type"]}
        for f in selected
    ]


def forget_memory(
    es: Elasticsearch,
    *,
    memory_id: str,
    user_id: str,
    memory_type: MemoryType,
) -> dict[str, Any]:
    """Delete one memory if it belongs to the given user.

    Writes a tombstone event into the episodic index for audit.
    """
    index = _index_for(memory_type)

    try:
        existing = es.get(index=index, id=memory_id, source=True)
    except NotFoundError:
        return {"deleted": False, "reason": "not_found"}

    owner = existing["_source"].get("user_id")
    if owner != user_id:
        return {"deleted": False, "reason": "unauthorized"}

    es.delete(index=index, id=memory_id)

    # Audit tombstone (best-effort; does not block on failure).
    try:
        es.index(
            index=INDEX_EPISODIC,
            document={
                "user_id": user_id,
                "event_type": "memory_forgotten",
                "role": "system",
                "timestamp": _now_iso(),
                "text": f"forgot {memory_type} memory {memory_id}",
                "metadata": {"forgotten_id": memory_id, "memory_type": memory_type},
            },
        )
    except Exception:  # noqa: BLE001
        logger.warning("Failed to write tombstone for forgotten memory %s", memory_id)

    return {"deleted": True, "memory_type": memory_type, "id": memory_id}


def update_procedural(
    es: Elasticsearch,
    *,
    memory_id: str,
    user_id: str,
    outcome: str,
    refined_steps: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Atomically increment success/failure counts and optionally refine steps.

    outcome must be "success" or "failure".
    refined_steps replaces the steps array and bumps the version number.
    Verifies user_id ownership before writing.
    """
    if outcome not in ("success", "failure"):
        return {"updated": False, "reason": f"invalid outcome {outcome!r}"}

    try:
        existing = es.get(index=INDEX_PROCEDURAL, id=memory_id, source=True)
    except NotFoundError:
        return {"updated": False, "reason": "not_found"}

    owner = existing["_source"].get("user_id")
    if owner != user_id:
        return {"updated": False, "reason": "unauthorized"}

    counter_field = "success_count" if outcome == "success" else "failure_count"

    if refined_steps:
        script = {
            "source": (
                f"ctx._source.{counter_field}++; "
                "ctx._source.steps = params.steps; "
                "ctx._source.version = (ctx._source.version ?: 1) + 1;"
            ),
            "params": {"steps": refined_steps},
        }
    else:
        script = {
            "source": f"ctx._source.{counter_field}++;",
        }

    es.update(index=INDEX_PROCEDURAL, id=memory_id, script=script, refresh=True)
    return {"updated": True, "memory_type": "procedural", "id": memory_id, "outcome": outcome}


__all__ = [
    "INDEX_EPISODIC",
    "INDEX_PROCEDURAL",
    "INDEX_SEMANTIC",
    "MEMORY_INDICES",
    "MemoryType",
    "core_memory",
    "forget_memory",
    "list_memories",
    "recall_memory",
    "update_procedural",
    "write_memory",
]
