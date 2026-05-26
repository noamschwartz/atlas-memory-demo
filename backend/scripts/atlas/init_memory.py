"""Initialize Atlas memory indices.

Idempotent: safe to re-run. Verifies the Jina v5 and Claude EIS endpoints
are reachable, then creates the three memory indices from JSON mappings.

Usage: uv run python -m scripts.init_memory
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from elasticsearch import BadRequestError

from app.elasticsearch.client import get_es_client
from app.atlas.memory.constants import (
    EMBEDDING_INFERENCE_ID,
    INDEX_CATALOG,
    LLM_INFERENCE_ID,
    MEMORY_INDICES,
)

MAPPINGS_DIR = Path(__file__).resolve().parents[2] / "app" / "atlas" / "memory" / "mappings"


def _endpoint_not_found_hint(inference_id: str, exc: Exception) -> str:
    """Build a clearer message for the common 'endpoint not found' failure."""
    return (
        f"Inference endpoint '{inference_id}' is not reachable on this cluster.\n"
        f"  Underlying error: {exc}\n\n"
        f"  Elastic Serverless inference endpoint IDs differ between projects.\n"
        f"  List the endpoints available on your cluster with:\n"
        f"    GET /_inference\n"
        f"  Then update the four IDs in backend/app/atlas/memory/constants.py:\n"
        f"    EMBEDDING_INFERENCE_ID, LLM_INFERENCE_ID, LLM_INFERENCE_ID_FAST, RERANKER_INFERENCE_ID\n"
        f"  and the matching 'inference_id' values in backend/app/atlas/memory/mappings/*.json."
    )


def verify_inference_endpoints(es) -> None:
    """Hit each EIS endpoint with a small request to confirm availability."""
    print("Verifying inference endpoints...")

    try:
        es.inference.inference(
            inference_id=EMBEDDING_INFERENCE_ID,
            input=["healthcheck"],
            task_type="text_embedding",
        )
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(_endpoint_not_found_hint(EMBEDDING_INFERENCE_ID, exc)) from exc
    print(f"  OK   {EMBEDDING_INFERENCE_ID}")

    # chat_completion is stream-only; confirm presence via GET instead.
    try:
        es.inference.get(inference_id=LLM_INFERENCE_ID)
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(_endpoint_not_found_hint(LLM_INFERENCE_ID, exc)) from exc
    print(f"  OK   {LLM_INFERENCE_ID}")


def create_indices(es) -> None:
    """Create the three memory indices + the shared catalog index from JSON mappings.

    Idempotent. If an index already exists, the mapping JSON is pushed via
    `PUT /<index>/_mapping` so additive field changes (e.g. adding
    `superseded_by`) take effect without dropping data. Field type changes
    are not supported and require a re-create.
    """
    print("Creating memory indices...")

    targets = list(MEMORY_INDICES.items()) + [("catalog", INDEX_CATALOG)]
    for memory_type, index_name in targets:
        mapping_file = MAPPINGS_DIR / f"{memory_type}.json"
        if not mapping_file.exists():
            print(f"  SKIP {index_name}: no mapping at {mapping_file}")
            continue

        with mapping_file.open() as f:
            body = json.load(f)

        if es.indices.exists(index=index_name):
            try:
                es.indices.put_mapping(
                    index=index_name,
                    body=body["mappings"],
                )
                print(f"  OK   {index_name} mapping updated")
            except BadRequestError as e:
                print(f"  WARN {index_name}: mapping update skipped ({e})")
            continue

        try:
            es.indices.create(index=index_name, body=body)
            print(f"  OK   {index_name} created")
        except BadRequestError as e:
            print(f"  FAIL {index_name}: {e}")
            raise


def main() -> int:
    es = get_es_client()
    try:
        verify_inference_endpoints(es)
    except Exception as e:
        print(f"\nInference verification failed: {e}", file=sys.stderr)
        return 1

    create_indices(es)
    print("\nMemory layer ready.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
