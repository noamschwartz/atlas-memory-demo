"""Mint per-user DLS API keys for Atlas.

Creates an Elasticsearch API key per seed user with:
  - read on the three Atlas memory indices,
  - a Document-Level-Security query filter pinning reads to that user_id.

The encoded keys are written to `.secrets/atlas_users.env` (chmod 600).
The backend uses these for any read path so that isolation is enforced at
the Elasticsearch layer, not just by application filters.

If the configured admin key is the cloud-managed "Unrestricted API Key", it
cannot directly derive narrowed sub-keys (Serverless rejects the request).
We work around that by minting an intermediate `atlas-bootstrap` admin key
with explicit broad privileges, then using THAT key to derive each user's
DLS-scoped key.

Usage: uv run python -m scripts.bootstrap_users
"""

from __future__ import annotations

import base64
import json
import os
import sys
from pathlib import Path
from typing import Iterable

from elasticsearch import Elasticsearch

from app.config import settings
from app.elasticsearch.client import get_es_client
from app.atlas.memory.constants import INDEX_CATALOG, MEMORY_INDICES

SEED_USERS = ["sarah", "james", "priya"]
SECRETS_DIR = Path(__file__).resolve().parents[2].parent / ".secrets"
USERS_ENV = SECRETS_DIR / "atlas_users.env"


def make_role_descriptor(user_id: str) -> dict:
    # DLS query admits the user's own docs OR docs with no `user_id` field
    # (the shared catalog index). This matches the application-level filter
    # widening in operations._user_or_catalog_filter so a DLS-scoped client
    # can recall against catalog when include_catalog=true.
    dls_query = {
        "bool": {
            "should": [
                {"term": {"user_id": user_id}},
                {"bool": {"must_not": {"exists": {"field": "user_id"}}}},
            ],
            "minimum_should_match": 1,
        }
    }
    return {
        f"atlas-user-{user_id}": {
            "indices": [
                {
                    "names": list(MEMORY_INDICES.values()) + [INDEX_CATALOG],
                    "privileges": ["read", "view_index_metadata"],
                    "query": json.dumps(dls_query),
                }
            ]
        }
    }


def make_admin_role_descriptor() -> dict:
    """Broad descriptor for the intermediate admin key — must be a strict
    subset of the parent (the cloud-managed Unrestricted key) so its derived
    children can be narrowed."""
    return {
        "atlas-bootstrap": {
            "cluster": ["manage_security", "monitor"],
            "indices": [
                {
                    "names": list(MEMORY_INDICES.values()) + [INDEX_CATALOG],
                    "privileges": ["read", "write", "view_index_metadata", "manage"],
                }
            ],
        }
    }


def mint_intermediate_admin(es: Elasticsearch) -> str:
    """Return an `id:api_key` encoded admin key with explicit privileges."""
    result = es.security.create_api_key(
        body={
            "name": "atlas-bootstrap-admin",
            "role_descriptors": make_admin_role_descriptor(),
            "metadata": {"app": "atlas-memory-demo", "purpose": "bootstrap-parent"},
        }
    )
    print(f"  OK   intermediate admin key id={result['id']}")
    return result["encoded"]


def mint_keys(intermediate_es: Elasticsearch, user_ids: Iterable[str]) -> dict[str, str]:
    """Create one DLS-scoped API key per user using the intermediate admin."""
    keys: dict[str, str] = {}
    for user_id in user_ids:
        body = {
            "name": f"atlas-user-{user_id}",
            "role_descriptors": make_role_descriptor(user_id),
            "metadata": {"app": "atlas-memory-demo", "user_id": user_id},
        }
        result = intermediate_es.security.create_api_key(body=body)
        keys[user_id] = result["encoded"]
        print(
            f"  OK   key for {user_id}: id={result['id']} dls=user_id=={user_id!r}"
        )
    return keys


def _build_intermediate_client(encoded_key: str) -> Elasticsearch:
    if settings.ELASTIC_CLOUD_ID:
        return Elasticsearch(cloud_id=settings.ELASTIC_CLOUD_ID, api_key=encoded_key)
    return Elasticsearch(hosts=[settings.ELASTICSEARCH_URL], api_key=encoded_key)


def write_secrets(keys: dict[str, str]) -> None:
    SECRETS_DIR.mkdir(exist_ok=True)
    lines = [
        "# Atlas per-user DLS API keys — regenerate via scripts/bootstrap_users.py",
        "",
    ]
    for user_id, encoded in sorted(keys.items()):
        lines.append(f"ATLAS_USER_KEY_{user_id.upper()}={encoded}")
    USERS_ENV.write_text("\n".join(lines) + "\n")
    os.chmod(USERS_ENV, 0o600)
    print(f"\nWrote {USERS_ENV} (mode 600)")


def _is_serverless_derived_key_block(err: Exception) -> bool:
    """Detect the Serverless restriction that blocks derived API keys with explicit
    privileges. Empirically the error text is:
      "creating derived api keys requires an explicit role descriptor that is empty
       (has no privileges)"
    See SERVERLESS_DLS_DERIVED_KEYS.md in hive-mind for full background.
    """
    msg = str(err).lower()
    return "derived api key" in msg and ("empty" in msg or "no privileges" in msg)


def _print_serverless_kibana_recipe() -> None:
    """Print copy-pasteable Kibana-UI instructions for the Serverless case."""
    print(
        "\n"
        "This cluster is Elastic Cloud Serverless. API-key-authenticated requests\n"
        "cannot mint derived keys with explicit privileges, so this script's\n"
        "automated path doesn't work here. The Kibana UI authenticates as your\n"
        "user session (not an API key), so per-user DLS keys minted there DO work.\n"
        "\n"
        "Steps:\n"
        "  1. Kibana > Stack Management > API Keys > Create API key.\n"
        "  2. For each user below: name the key `atlas-user-<userid>`, toggle\n"
        "     \"Restrict privileges\" on, and paste the role descriptor for that user.\n"
        "  3. Copy the encoded value Kibana returns into `.secrets/atlas_users.env`\n"
        f"     ({USERS_ENV}) as:\n"
        "         ATLAS_USER_KEY_<USERID>=<encoded>\n"
        "     (chmod the file to 600 once written).\n"
        "\n"
        "Role descriptors (one per user):\n"
    )
    for user_id in SEED_USERS:
        descriptor = make_role_descriptor(user_id)
        print(f"  --- atlas-user-{user_id} ---")
        print(json.dumps(descriptor, indent=2))
        print()
    print(
        "Once `.secrets/atlas_users.env` is in place, the running app picks up the\n"
        "DLS-scoped clients automatically via `user_keys.get_user_client(user_id)`.\n"
        "Verify with the test suite in the README, or run a quick `match_all` count\n"
        "from each user's client and confirm only that user's docs come back.\n"
    )


def main() -> int:
    parent = get_es_client()
    try:
        print("Minting per-user DLS keys (direct from configured admin)...")
        keys = mint_keys(parent, SEED_USERS)
    except Exception as direct_err:
        print(f"  direct path failed: {direct_err}")
        if _is_serverless_derived_key_block(direct_err):
            # Serverless prohibits the derived-key approach regardless of which admin
            # key we use, so the intermediate-admin retry is wasted. Skip straight
            # to the Kibana-UI recipe.
            _print_serverless_kibana_recipe()
            return 0
        print("Trying intermediate admin parent...")
        try:
            intermediate_encoded = mint_intermediate_admin(parent)
            intermediate = _build_intermediate_client(intermediate_encoded)
            keys = mint_keys(intermediate, SEED_USERS)
        except Exception as indirect_err:
            print(f"  intermediate path also failed: {indirect_err}")
            if _is_serverless_derived_key_block(indirect_err):
                _print_serverless_kibana_recipe()
                return 0
            print(
                "\n"
                "DLS bootstrap could not run on this cluster, and the error doesn't\n"
                "match the known Serverless derived-key restriction. The configured\n"
                "ELASTIC_API_KEY may lack `manage_security` or similar. Check the\n"
                "error above and mint a project-level admin key with the privileges\n"
                "documented in this script's `make_admin_role_descriptor`.\n"
                "\n"
                "Atlas is still tenant-isolated in the meantime: every recall goes\n"
                "through `recall_memory(user_id=...)`, which adds a `term: user_id`\n"
                "filter into the RRF retriever's filter clauses. Functionally\n"
                "equivalent, just enforced in app code rather than inside\n"
                "Elasticsearch."
            )
            return 0
    write_secrets(keys)
    print("\nUser DLS keys bootstrapped.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
