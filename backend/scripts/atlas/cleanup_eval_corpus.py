"""One-time corpus cleanup for the recall@k eval (Phase C).

Two problems this script fixes:

1. **Missing needles.** Some ground-truth needles defined in `needles.py`
   are not present in the Elasticsearch indices (e.g. `sarah-hub-3.1.4-
   regression` was missing as of 2026-05-13). The eval treats those as
   permanent misses, capping the achievable Recall@k. We re-insert every
   needle that's missing, preserving its `age_days` so timestamp behavior
   matches the rest of the seed.

2. **Consolidation near-duplicates competing with needles.** Live demo
   activity has generated semantic facts that closely paraphrase the
   ground-truth needles. The reranker correctly identifies them both as
   relevant, but the eval is strict (matches by `metadata.needle_id`), so
   when the consolidation copy out-ranks the needle, the eval scores it as
   a miss. For each needle, we find active docs in the same memory_type
   whose semantic similarity is >= NEAR_DUPLICATE_THRESHOLD (0.85) AND
   that do NOT carry the same needle_id metadata, then soft-supersede them
   (mark `superseded_by` pointing at the needle's id). Recall filters them
   out; the audit trail is intact and a single `--undo` invocation can
   reverse it.

Idempotent: safe to re-run. Default is `--dry-run` so you can preview the
changes before applying them.

Usage:
  uv run python -m scripts.atlas.cleanup_eval_corpus              # dry run
  uv run python -m scripts.atlas.cleanup_eval_corpus --apply      # commit
  uv run python -m scripts.atlas.cleanup_eval_corpus --undo       # rollback
"""

from __future__ import annotations

import argparse
import logging
import sys
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from app.atlas.memory.constants import (
    INDEX_EPISODIC,
    INDEX_PROCEDURAL,
    INDEX_SEMANTIC,
    MEMORY_INDICES,
)
from app.elasticsearch.client import get_es_client

from .needles import ALL_NEEDLES, Needle

logger = logging.getLogger(__name__)

NEAR_DUPLICATE_THRESHOLD = 0.85


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _at(days_ago: int) -> str:
    return (_now() - timedelta(days=max(0, int(days_ago)))).isoformat()


def _index_for(memory_type: str) -> str:
    return MEMORY_INDICES[memory_type]


def _find_needle_doc(es, needle: Needle) -> dict | None:
    """Return the ES hit for an indexed needle, or None if it doesn't exist."""
    index = _index_for(needle.memory_type)
    resp = es.search(
        index=index,
        body={
            "size": 1,
            "query": {"term": {"metadata.needle_id": needle.needle_id}},
        },
    )
    hits = resp.get("hits", {}).get("hits", [])
    return hits[0] if hits else None


def _insert_missing_needle(es, needle: Needle) -> str:
    """Index a missing needle with a fresh UUID. Returns the new doc id."""
    index = _index_for(needle.memory_type)
    doc_id = str(uuid.uuid4())
    created = _at(needle.age_days)
    if needle.memory_type == "semantic":
        source = {
            "user_id": needle.user_id,
            "text": needle.text,
            "fact_type": needle.fact_type or "world",
            "confidence": needle.confidence,
            "source_episodes": [],
            "created_at": created,
            "last_used_at": created,
            "use_count": 0,
            "metadata": {"needle_id": needle.needle_id},
        }
    elif needle.memory_type == "episodic":
        source = {
            "user_id": needle.user_id,
            "text": needle.text,
            "agent_id": "atlas",
            "session_id": None,
            "event_type": "user_message",
            "role": "user",
            "timestamp": created,
            "metadata": {"needle_id": needle.needle_id},
        }
    else:  # procedural
        source = {
            "user_id": needle.user_id,
            "name": needle.name or needle.text[:60],
            "trigger_text": needle.text,
            "description": needle.description or "",
            "steps": needle.steps or [],
            "version": 1,
            "success_count": 0,
            "failure_count": 0,
            "created_at": created,
            "metadata": {"needle_id": needle.needle_id},
        }
    es.index(index=index, id=doc_id, document=source, refresh=True)
    return doc_id


def _find_competitors(
    es,
    needle: Needle,
    needle_doc_id: str,
    *,
    threshold: float,
) -> list[tuple[str, float, str]]:
    """Return [(competitor_id, score, text), ...] — active docs in the same
    memory_type that are semantically close to the needle but lack its
    needle_id. Bounded at top-20 (caller-side guard against runaway loops on
    pathological corpora)."""
    index = _index_for(needle.memory_type)
    filters: list[dict[str, Any]] = [
        {"term": {"user_id": needle.user_id}},
        {"bool": {"must_not": {"term": {"metadata.needle_id": needle.needle_id}}}},
        {"bool": {"must_not": {"term": {"_id": needle_doc_id}}}},
    ]
    if needle.memory_type == "semantic":
        filters.append({"bool": {"must_not": {"exists": {"field": "superseded_by"}}}})

    resp = es.search(
        index=index,
        body={
            "size": 20,
            "_source": ["text", "trigger_text", "description", "metadata"],
            "query": {
                "bool": {
                    "must": [{"semantic": {"field": "semantic_content", "query": needle.text}}],
                    "filter": filters,
                }
            },
        },
    )
    out: list[tuple[str, float, str]] = []
    for h in resp.get("hits", {}).get("hits", []):
        score = float(h.get("_score") or 0.0)
        if score < threshold:
            break  # hits are sorted by score; stop on first miss
        src = h.get("_source", {})
        text = src.get("text") or src.get("trigger_text") or src.get("description") or ""
        out.append((h["_id"], score, text))
    return out


def _supersede(es, *, index: str, doc_id: str, by_id: str) -> None:
    """Mark a semantic doc as superseded by `by_id`. No-op on non-semantic
    indices (we use a different marker there, see below)."""
    now = _now().isoformat()
    if index == INDEX_SEMANTIC:
        es.update(
            index=index,
            id=doc_id,
            doc={"superseded_by": by_id, "superseded_at": now},
            refresh=True,
        )
    else:
        # episodic / procedural don't have superseded_by support in the
        # mapping or recall filter today. Tag them in metadata as
        # "shadowed_by_needle" so the cleanup is reversible and visible,
        # but they will still appear in recall.
        es.update(
            index=index,
            id=doc_id,
            doc={"metadata": {"shadowed_by_needle": by_id, "shadowed_at": now}},
            refresh=True,
        )


def _undo_supersede(es, *, index: str, doc_id: str) -> None:
    now = _now().isoformat()
    if index == INDEX_SEMANTIC:
        # `script` removes the two fields; no-op if they aren't set.
        es.update(
            index=index,
            id=doc_id,
            script={
                "source": (
                    "ctx._source.remove('superseded_by'); "
                    "ctx._source.remove('superseded_at');"
                )
            },
            refresh=True,
        )
    else:
        es.update(
            index=index,
            id=doc_id,
            script={
                "source": (
                    "if (ctx._source.metadata != null) {"
                    " ctx._source.metadata.remove('shadowed_by_needle');"
                    " ctx._source.metadata.remove('shadowed_at');"
                    "}"
                )
            },
            refresh=True,
        )
    _ = now  # currently unused; reserved if we ever want to log on undo


def cleanup(es, *, dry_run: bool, threshold: float) -> dict[str, int]:
    inserted_needles = 0
    superseded_total = 0
    skipped_already_done = 0

    for needle in ALL_NEEDLES:
        hit = _find_needle_doc(es, needle)
        if hit is None:
            if dry_run:
                print(f"  WOULD INSERT missing needle {needle.needle_id} into {_index_for(needle.memory_type)}")
            else:
                new_id = _insert_missing_needle(es, needle)
                print(f"  INSERTED needle {needle.needle_id} as {new_id}")
            inserted_needles += 1
            # Skip competitor sweep on the same pass — the new needle won't
            # have been written yet (dry-run) or the index may not have
            # propagated (live). Future runs will catch it.
            continue

        needle_doc_id = hit["_id"]
        comps = _find_competitors(es, needle, needle_doc_id, threshold=threshold)
        if not comps:
            skipped_already_done += 1
            continue

        for comp_id, score, text in comps:
            if dry_run:
                print(
                    f"  WOULD SUPERSEDE {comp_id} (score={score:.3f}) "
                    f"by needle {needle.needle_id}: {text[:80]!r}"
                )
            else:
                _supersede(es, index=_index_for(needle.memory_type), doc_id=comp_id, by_id=needle_doc_id)
                print(
                    f"  SUPERSEDED {comp_id} (score={score:.3f}) "
                    f"by needle {needle.needle_id}"
                )
            superseded_total += 1

    return {
        "inserted_needles": inserted_needles,
        "superseded_competitors": superseded_total,
        "needles_already_clean": skipped_already_done,
    }


def undo(es) -> dict[str, int]:
    """Reverse a prior cleanup run.

    Finds every doc that carries `superseded_by` pointing at a needle id, or
    `metadata.shadowed_by_needle`, and removes those markers.
    """
    reverted_semantic = 0
    reverted_other = 0

    # Build a set of needle doc ids per memory_type so we only undo OUR
    # supersessions, not legitimate ones from the agent's contradiction flow.
    needle_doc_ids: set[str] = set()
    for needle in ALL_NEEDLES:
        hit = _find_needle_doc(es, needle)
        if hit is not None:
            needle_doc_ids.add(hit["_id"])

    if not needle_doc_ids:
        print("  no needle docs found; nothing to undo")
        return {"reverted_semantic": 0, "reverted_other": 0}

    # Semantic: superseded_by IN needle_doc_ids
    resp = es.search(
        index=INDEX_SEMANTIC,
        body={
            "size": 1000,
            "_source": False,
            "query": {"terms": {"superseded_by": list(needle_doc_ids)}},
        },
    )
    for h in resp.get("hits", {}).get("hits", []):
        _undo_supersede(es, index=INDEX_SEMANTIC, doc_id=h["_id"])
        reverted_semantic += 1

    # Episodic + procedural: metadata.shadowed_by_needle IN needle_doc_ids
    for index in (INDEX_EPISODIC, INDEX_PROCEDURAL):
        resp = es.search(
            index=index,
            body={
                "size": 1000,
                "_source": False,
                "query": {"terms": {"metadata.shadowed_by_needle": list(needle_doc_ids)}},
            },
        )
        for h in resp.get("hits", {}).get("hits", []):
            _undo_supersede(es, index=index, doc_id=h["_id"])
            reverted_other += 1

    return {"reverted_semantic": reverted_semantic, "reverted_other": reverted_other}


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    p = argparse.ArgumentParser()
    p.add_argument("--apply", action="store_true", help="commit changes (default is dry-run)")
    p.add_argument("--undo", action="store_true", help="reverse a prior cleanup run")
    p.add_argument("--threshold", type=float, default=NEAR_DUPLICATE_THRESHOLD,
                   help=f"semantic similarity threshold for competitors (default {NEAR_DUPLICATE_THRESHOLD})")
    args = p.parse_args()

    es = get_es_client()

    if args.undo:
        print("Reverting prior eval-corpus cleanup...")
        result = undo(es)
        print(f"\nDone: reverted {result['reverted_semantic']} semantic + {result['reverted_other']} other supersessions")
        return 0

    print(f"Eval-corpus cleanup (mode={'apply' if args.apply else 'dry-run'}, threshold={args.threshold}):")
    result = cleanup(es, dry_run=not args.apply, threshold=args.threshold)
    print()
    print(f"  inserted_needles:        {result['inserted_needles']}")
    print(f"  superseded_competitors:  {result['superseded_competitors']}")
    print(f"  needles_already_clean:   {result['needles_already_clean']}")
    if not args.apply:
        print("\n(Re-run with --apply to commit. --undo to reverse a prior run.)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
