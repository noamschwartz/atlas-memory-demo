"""Bulk-index generated narratives + ground-truth needles into Atlas indices.

Reads `backend/data/atlas_seed/<user>.json` (output of deep_narratives.py)
and the in-code needles from `needles.py`, builds doc actions matching the
existing schemas, and ships them via `elasticsearch.helpers.bulk`. The
`semantic_text` fields trigger Jina v5 inference automatically — no
client-side embedding code.

Idempotent: clears any prior docs for the targeted users from the three
memory indices before re-seeding, so consecutive runs converge.

Usage:
  uv run python -m scripts.atlas.bulk_seed                     # all users
  uv run python -m scripts.atlas.bulk_seed --user sarah        # one user
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator

from elasticsearch import ApiError
from elasticsearch.helpers import bulk

from app.elasticsearch.client import get_es_client
from app.atlas.memory.constants import (
    INDEX_EPISODIC,
    INDEX_PROCEDURAL,
    INDEX_SEMANTIC,
    MEMORY_INDICES,
)

from .deep_narratives import DATA_DIR, PERSONAS
from .needles import ALL_NEEDLES, Needle, needles_for

logger = logging.getLogger(__name__)

# Bulk indexing parameters tuned for `semantic_text` auto-inference: chunk
# size kept small because each doc fans out to a Jina v5 inference call,
# and request_timeout is generous for the same reason.
CHUNK_SIZE = 100
REQUEST_TIMEOUT = 180
MAX_RETRIES = 5


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _at(days_ago: int) -> str:
    """Days-ago integer -> ISO timestamp."""
    return (_now() - timedelta(days=max(0, int(days_ago)))).isoformat()


def _episodic_action(user_id: str, item: dict, *, needle_id: str | None = None) -> dict:
    metadata: dict[str, Any] = dict(item.get("metadata") or {})
    if needle_id:
        metadata["needle_id"] = needle_id
    return {
        "_index": INDEX_EPISODIC,
        "_id": str(uuid.uuid4()),
        "_source": {
            "user_id": user_id,
            "text": item["text"],
            "agent_id": item.get("agent_id") or "atlas",
            "session_id": item.get("session_id"),
            "event_type": item.get("event_type") or "user_message",
            "role": item.get("role") or "user",
            "timestamp": _at(item.get("days_ago", 0)),
            "metadata": metadata,
        },
    }


def _semantic_action(user_id: str, item: dict, *, needle_id: str | None = None) -> dict:
    metadata: dict[str, Any] = dict(item.get("metadata") or {})
    if needle_id:
        metadata["needle_id"] = needle_id
    created = _at(item.get("days_ago", 0))
    return {
        "_index": INDEX_SEMANTIC,
        "_id": str(uuid.uuid4()),
        "_source": {
            "user_id": user_id,
            "text": item["text"],
            "fact_type": item.get("fact_type") or "preference",
            "confidence": float(item.get("confidence") or 0.9),
            "source_episodes": item.get("source_episodes") or [],
            "created_at": created,
            "last_used_at": created,
            "use_count": 0,
            "metadata": metadata,
        },
    }


def _procedural_action(user_id: str, item: dict, *, needle_id: str | None = None) -> dict:
    metadata: dict[str, Any] = dict(item.get("metadata") or {})
    if needle_id:
        metadata["needle_id"] = needle_id
    return {
        "_index": INDEX_PROCEDURAL,
        "_id": str(uuid.uuid4()),
        "_source": {
            "user_id": user_id,
            "name": item.get("name") or item.get("text", "")[:60],
            "trigger_text": item.get("trigger_text") or item.get("text", ""),
            "description": item.get("description") or "",
            "steps": item.get("steps") or [],
            "version": 1,
            "success_count": 0,
            "failure_count": 0,
            "created_at": _at(item.get("days_ago", 0)),
            "metadata": metadata,
        },
    }


def _actions_for_user(user_id: str, narrative: dict, needles: list[Needle]) -> Iterator[dict]:
    for ep in narrative.get("episodic", []):
        yield _episodic_action(user_id, ep)
    for sm in narrative.get("semantic", []):
        yield _semantic_action(user_id, sm)
    for pr in narrative.get("procedural", []):
        yield _procedural_action(user_id, pr)

    for n in needles:
        item = {
            "text": n.text,
            "days_ago": n.age_days,
            "fact_type": n.fact_type,
            "confidence": n.confidence,
            "name": n.name,
            "description": n.description,
            "steps": n.steps,
            "role": "user",
            "event_type": "user_message",
        }
        if n.memory_type == "episodic":
            yield _episodic_action(user_id, item, needle_id=n.needle_id)
        elif n.memory_type == "semantic":
            yield _semantic_action(user_id, item, needle_id=n.needle_id)
        else:
            yield _procedural_action(user_id, item, needle_id=n.needle_id)


def _clear_user(es, user_id: str) -> None:
    for index in MEMORY_INDICES.values():
        try:
            es.delete_by_query(
                index=index,
                body={"query": {"term": {"user_id": user_id}}},
                refresh=True,
                conflicts="proceed",
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("clearing %s for %s failed: %s", index, user_id, exc)


def _bulk_with_retry(es, actions: list[dict]) -> tuple[int, list[dict]]:
    """Bulk-index, retrying on 429s with exponential backoff."""
    delay = 2.0
    last_errors: list[dict] = []
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            success, errors = bulk(
                es,
                actions,
                chunk_size=CHUNK_SIZE,
                request_timeout=REQUEST_TIMEOUT,
                raise_on_error=False,
                raise_on_exception=False,
            )
            last_errors = list(errors) if isinstance(errors, list) else []
            transient = [e for e in last_errors if _is_transient(e)]
            if not transient:
                return success, last_errors
            # Retry only the failing actions.
            print(f"  attempt {attempt}: {len(transient)} transient errors, retrying after {delay:.1f}s")
            actions = [_action_from_error(e) for e in transient if _action_from_error(e)]
            time.sleep(delay)
            delay *= 2
        except ApiError as exc:
            print(f"  attempt {attempt}: ApiError {exc}, retrying after {delay:.1f}s")
            time.sleep(delay)
            delay *= 2
    return 0, last_errors


def _is_transient(err: dict) -> bool:
    op = next(iter(err.values()), {})
    status = op.get("status", 0) if isinstance(op, dict) else 0
    return status in (429, 503)


def _action_from_error(err: dict) -> dict | None:
    op_name, op = next(iter(err.items()), (None, {}))
    if not op_name or not isinstance(op, dict):
        return None
    return {
        "_op_type": op_name,
        "_index": op.get("_index"),
        "_id": op.get("_id"),
        "_source": op.get("data") or op.get("_source") or {},
    }


def seed_user(es, user_id: str) -> dict[str, int]:
    narrative_path = DATA_DIR / f"{user_id}.json"
    if not narrative_path.exists():
        raise FileNotFoundError(
            f"no narrative for {user_id} at {narrative_path}; run deep_narratives.py first"
        )
    narrative = json.loads(narrative_path.read_text())
    needles = needles_for(user_id)
    actions = list(_actions_for_user(user_id, narrative, needles))

    print(f"  user {user_id}: clearing prior docs...")
    _clear_user(es, user_id)
    print(f"  user {user_id}: indexing {len(actions)} docs...")
    success, errors = _bulk_with_retry(es, actions)
    if errors:
        print(f"    WARN: {len(errors)} doc errors remained after retries (showing 3): {errors[:3]}")

    for index in MEMORY_INDICES.values():
        es.indices.refresh(index=index)

    counts: dict[str, int] = {}
    for memory_type, index in MEMORY_INDICES.items():
        c = es.count(index=index, body={"query": {"term": {"user_id": user_id}}})["count"]
        counts[memory_type] = c
    counts["needles"] = len(needles)
    counts["indexed"] = success
    return counts


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    p = argparse.ArgumentParser()
    p.add_argument("--user", choices=list(PERSONAS.keys()))
    args = p.parse_args()

    es = get_es_client()
    targets = [args.user] if args.user else list(PERSONAS.keys())

    print(f"Bulk-seeding {len(targets)} user(s)...")
    for user_id in targets:
        counts = seed_user(es, user_id)
        print(
            f"  {user_id}: indexed={counts['indexed']} "
            f"episodic={counts['episodic']} semantic={counts['semantic']} "
            f"procedural={counts['procedural']} (needles={counts['needles']})"
        )
    print("\nSeeding complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
