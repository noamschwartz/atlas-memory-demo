"""Per-user consolidation watermark.

Consolidation used to re-read the 30 most recent episodic events on *every*
turn, with nothing recording which events had already been distilled. Two
consequences followed:

  * The same episodes were handed to the consolidation LLM turn after turn, so
    the cost of a turn that contained nothing durable was identical to one that
    did.
  * The only thing standing between that and duplicate facts was a prose
    instruction ("DO NOT duplicate any existing fact") evaluated against a
    capped window of existing facts. Once a user's fact count exceeds that
    window, re-extraction of an old fact is not unlikely, it is unpreventable.

The obvious fix - stamp `consolidated_at` onto each episodic document - has two
problems. It needs a backfill (otherwise every historical episode reads as
unconsolidated and the first run after upgrade re-processes the entire backlog,
which is worse than the bug), and the natural way to write that backfill is a
scripted `_update_by_query`, which Elasticsearch rejects on indices containing a
`semantic_text` field because it runs through the bulk path.

So the watermark lives beside the memory indices instead, one small document per
user in `atlas_memory_state`. That index carries no `semantic_text` field, so it
has none of the update restrictions, and an existing deployment needs no
backfill at all: `ensure_watermark` initialises a missing watermark to *now*,
which means an upgrade starts with zero backlog.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from elasticsearch import AuthorizationException, Elasticsearch, NotFoundError

from .constants import INDEX_EPISODIC, INDEX_STATE

logger = logging.getLogger(__name__)

# "The watermark index is not provisioned" is an expected, recoverable state,
# not an incident. It would otherwise raise on every read and every write of
# every turn, so a stack trace per occurrence buries real errors. Warn once per
# process and stay quiet after that.
_unavailable_warned = False


def _warn_unavailable_once() -> None:
    global _unavailable_warned
    if _unavailable_warned:
        return
    _unavailable_warned = True
    logger.warning(
        "Consolidation watermark store %s is unavailable; consolidation is "
        "falling back to the recent-window path. To enable incremental "
        "consolidation, create the index and grant the application API key "
        "read/write on it (see scripts/atlas/init_memory.py).",
        INDEX_STATE,
    )


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_watermark(es: Elasticsearch, user_id: str) -> str | None:
    """Return the user's `last_consolidated_at`, or None if never set.

    A missing index or a missing document both mean "no watermark yet" and are
    not errors; the caller decides what to do about it.
    """
    try:
        doc = es.get(index=INDEX_STATE, id=user_id, source=True)
    except NotFoundError:
        # Index exists, no watermark for this user yet. Normal for a new user.
        return None
    except AuthorizationException:
        # Index not provisioned, or the key lacks access. Expected until the
        # one-time provisioning step is done; warned about once per process.
        _warn_unavailable_once()
        return None
    except Exception:  # noqa: BLE001
        # A watermark read must never take down a chat turn. Returning None
        # degrades to "consolidate the recent window", i.e. the old behaviour.
        logger.warning("watermark read failed for %s", user_id, exc_info=True)
        return None
    return (doc.get("_source") or {}).get("last_consolidated_at")


def set_watermark(es: Elasticsearch, user_id: str, timestamp: str) -> bool:
    """Advance the user's watermark to `timestamp`. Returns success."""
    try:
        es.index(
            index=INDEX_STATE,
            id=user_id,
            document={
                "user_id": user_id,
                "last_consolidated_at": timestamp,
                "updated_at": _now_iso(),
            },
            refresh=True,
        )
        return True
    except AuthorizationException:
        _warn_unavailable_once()
        return False
    except Exception:  # noqa: BLE001
        logger.warning("watermark write failed for %s", user_id, exc_info=True)
        return False


def ensure_watermark(es: Elasticsearch, user_id: str) -> str | None:
    """Return the user's watermark, initialising it to *now* if absent.

    Initialising to now (rather than to the epoch) is what makes this a
    non-breaking change for an already-deployed system: existing episodic
    history is treated as already consolidated, so upgrading does not trigger a
    re-extraction storm over months of accumulated events.

    Returns None when the watermark store is unavailable - most commonly because
    `atlas_memory_state` has not been provisioned yet, or the application API
    key has not been granted access to it. That case MUST NOT be confused with
    "watermark is now": treating an unreadable watermark as the current time
    would mean `episodes_since` matches nothing and consolidation silently stops
    running altogether. Returning None lets the caller fall back to the previous
    "most recent N episodes" behaviour, so the system degrades to where it was
    rather than to something worse.
    """
    existing = get_watermark(es, user_id)
    if existing:
        return existing
    now = _now_iso()
    if not set_watermark(es, user_id, now):
        # set_watermark has already warned (once) if the store is unavailable.
        return None
    logger.info("initialised consolidation watermark for %s at %s", user_id, now)
    return now


def episodes_since(
    es: Elasticsearch,
    *,
    user_id: str,
    since: str,
    limit: int,
) -> list[dict[str, Any]]:
    """Episodic events strictly newer than `since`, oldest first.

    Oldest-first is deliberate. The consolidation prompt asks the model which
    event supersedes which, and to spot a complete multi-step resolution; both
    are order-dependent and both were previously being shown the events
    newest-first.
    """
    resp = es.search(
        index=INDEX_EPISODIC,
        body={
            "size": limit,
            "query": {
                "bool": {
                    "filter": [
                        {"term": {"user_id": user_id}},
                        {"range": {"timestamp": {"gt": since}}},
                    ]
                }
            },
            "sort": [{"timestamp": "asc"}],
            "_source": {"excludes": ["semantic_content"]},
        },
    )
    return [
        {"id": h["_id"], "source": h["_source"]}
        for h in resp["hits"]["hits"]
    ]


__all__ = [
    "ensure_watermark",
    "episodes_since",
    "get_watermark",
    "set_watermark",
]
