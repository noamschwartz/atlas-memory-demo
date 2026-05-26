"""One-shot reset + deep-seed for Atlas memory indices.

Drops the three memory indices (episodic / semantic / procedural), re-runs
init_memory to recreate them from the JSON mappings, then bulk-loads the
generated narratives + ground-truth needles for all personas.

Catalog index is left alone — it's user-agnostic and doesn't carry the
per-user history we're rebuilding.

Usage:
  uv run python -m scripts.atlas.reset_and_seed
"""

from __future__ import annotations

import sys

from app.elasticsearch.client import get_es_client
from app.atlas.memory.constants import MEMORY_INDICES

from .bootstrap_users import main as bootstrap_users_main
from .bulk_seed import seed_user
from .deep_narratives import DATA_DIR, PERSONAS
from .init_memory import create_indices, verify_inference_endpoints


def _drop_memory_indices(es) -> None:
    print("Dropping memory indices...")
    for index in MEMORY_INDICES.values():
        if es.indices.exists(index=index):
            es.indices.delete(index=index)
            print(f"  deleted {index}")
        else:
            print(f"  skip    {index} (did not exist)")


def main() -> int:
    es = get_es_client()
    available_personas = [u for u in PERSONAS if (DATA_DIR / f"{u}.json").exists()]
    if not available_personas:
        print(
            "No narrative cache found.\n"
            "Run: uv run python -m scripts.atlas.deep_narratives",
            file=sys.stderr,
        )
        return 1
    missing = [u for u in PERSONAS if u not in available_personas]
    if missing:
        print(f"Note: skipping missing narratives for {', '.join(missing)}")

    try:
        verify_inference_endpoints(es)
    except Exception as exc:  # noqa: BLE001
        print(f"Inference verification failed: {exc}", file=sys.stderr)
        return 1

    _drop_memory_indices(es)
    create_indices(es)

    print("\nBulk-seeding deep narratives + needles...")
    for user_id in available_personas:
        counts = seed_user(es, user_id)
        print(
            f"  {user_id}: indexed={counts['indexed']} "
            f"episodic={counts['episodic']} semantic={counts['semantic']} "
            f"procedural={counts['procedural']} (needles={counts['needles']})"
        )

    print("\nMinting per-user DLS API keys...")
    try:
        bootstrap_users_main()
    except Exception as exc:  # noqa: BLE001
        # bootstrap_users prints its own diagnostic on graceful failure;
        # only catch unexpected import/runtime errors here so the seed step
        # still reports success.
        print(f"  DLS bootstrap raised unexpectedly: {exc}", file=sys.stderr)

    print("\nReset + deep seed complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
