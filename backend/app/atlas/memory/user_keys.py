"""Per-user Elasticsearch clients backed by DLS-scoped API keys.

The keys are minted by `scripts/bootstrap_users.py` and stored in
`.secrets/atlas_users.env` as `ATLAS_USER_KEY_<USERID>=<encoded>` lines.

When a user-scoped client exists, the recall path uses it: the cluster
itself enforces tenant isolation via the DLS query embedded in the role,
which is the demo's "isolation is enforced by Elasticsearch, not by app
code" moment. Falls back to the admin client (with an explicit filter)
if no user key is registered.
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path

from dotenv import dotenv_values
from elasticsearch import Elasticsearch

from ...config import settings

logger = logging.getLogger(__name__)

_SECRETS_PATH = Path(__file__).resolve().parents[4] / ".secrets" / "atlas_users.env"

_clients: dict[str, Elasticsearch] = {}
_lock = threading.Lock()


def _load_keys() -> dict[str, str]:
    if not _SECRETS_PATH.exists():
        return {}
    raw = dotenv_values(_SECRETS_PATH)
    out: dict[str, str] = {}
    for k, v in raw.items():
        if k and k.startswith("ATLAS_USER_KEY_") and v:
            user_id = k[len("ATLAS_USER_KEY_"):].lower()
            out[user_id] = v
    return out


def _build_client(api_key: str) -> Elasticsearch:
    if settings.ELASTIC_CLOUD_ID:
        return Elasticsearch(
            cloud_id=settings.ELASTIC_CLOUD_ID,
            api_key=api_key,
        )
    return Elasticsearch(
        hosts=[settings.ELASTICSEARCH_URL],
        api_key=api_key,
    )


def get_user_client(user_id: str) -> Elasticsearch | None:
    """Return a DLS-scoped client for `user_id`, or None if no key registered."""
    if not user_id:
        return None
    user_id = user_id.lower()
    with _lock:
        if user_id in _clients:
            return _clients[user_id]
        keys = _load_keys()
        if user_id not in keys:
            return None
        client = _build_client(keys[user_id])
        _clients[user_id] = client
        logger.info("Registered DLS-scoped client for user %s", user_id)
        return client


def has_user_key(user_id: str) -> bool:
    return user_id.lower() in _load_keys()
