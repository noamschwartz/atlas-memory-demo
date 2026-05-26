"""Atlas memory REST endpoints.

Thin HTTP wrappers around the operations module so the frontend, MCP server,
and external agents can read/write the same memory layer.
"""

from __future__ import annotations

import logging
from typing import Any, Iterable

from elasticsearch import Elasticsearch
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from ..consolidate import consolidate
from ...elasticsearch.client import es_client
from ..memory.constants import MEMORY_INDICES
from ..memory.operations import (
    MemoryType,
    forget_memory,
    list_memories,
    recall_memory,
    write_memory,
)
from ..memory.user_keys import get_user_client, has_user_key

router = APIRouter(prefix="/api/memory", tags=["memory"])
logger = logging.getLogger(__name__)


# ---------- request models ----------

class WriteRequest(BaseModel):
    user_id: str
    memory_type: MemoryType
    text: str
    agent_id: str | None = None
    session_id: str | None = None
    event_type: str | None = None
    role: str | None = None
    fact_type: str | None = None
    confidence: float | None = None
    source_episodes: list[str] | None = None
    name: str | None = None
    description: str | None = None
    steps: list[dict[str, Any]] | None = None
    metadata: dict[str, Any] | None = None
    supersedes_id: str | None = None
    refresh: bool = False


class RecallRequest(BaseModel):
    user_id: str | None = None
    query: str
    memory_types: list[MemoryType] | None = None
    k: int = Field(default=10, ge=1, le=50)
    include_catalog: bool = False


class ForgetRequest(BaseModel):
    user_id: str
    memory_type: MemoryType
    memory_id: str


class ConsolidateRequest(BaseModel):
    user_id: str
    lookback: int = Field(default=30, ge=1, le=200)
    dry_run: bool = False


# ---------- routes ----------

@router.get("/health")
def health(es: Elasticsearch = Depends(es_client)) -> dict[str, Any]:
    counts: dict[str, int] = {}
    for memory_type, index in MEMORY_INDICES.items():
        try:
            counts[memory_type] = es.count(index=index)["count"]
        except Exception as exc:  # noqa: BLE001
            counts[memory_type] = -1
            logger.warning("count failed for %s: %s", index, exc)
    return {"status": "ok", "indices": MEMORY_INDICES, "counts": counts}


@router.post("/write")
def write(req: WriteRequest, es: Elasticsearch = Depends(es_client)) -> dict[str, Any]:
    return write_memory(
        es,
        user_id=req.user_id,
        memory_type=req.memory_type,
        text=req.text,
        agent_id=req.agent_id,
        session_id=req.session_id,
        event_type=req.event_type,
        role=req.role,
        fact_type=req.fact_type,
        confidence=req.confidence,
        source_episodes=req.source_episodes,
        metadata=req.metadata,
        name=req.name,
        description=req.description,
        steps=req.steps,
        supersedes_id=req.supersedes_id,
        refresh=req.refresh,
    )


@router.post("/recall")
def recall(req: RecallRequest, es: Elasticsearch = Depends(es_client)) -> dict[str, Any]:
    # Prefer the per-user DLS-scoped client. When it's available, ES enforces
    # isolation at the cluster level, so the application filter on user_id
    # is redundant — surfacing this in the response makes the demo concrete.
    isolation = "app_filter"
    admin_es = es
    user_client = get_user_client(req.user_id) if req.user_id else None
    if user_client is not None:
        es = user_client
        isolation = "dls"
    hits = recall_memory(
        es,
        query=req.query,
        user_id=None if isolation == "dls" else req.user_id,
        memory_types=req.memory_types,
        k=req.k,
        include_catalog=req.include_catalog,
        update_stats=True,
        stats_es=admin_es if isolation == "dls" else None,
    )
    return {
        "hits": hits,
        "count": len(hits),
        "isolation": isolation,
        "include_catalog": req.include_catalog,
    }


@router.get("/list")
def list_(
    user_id: str = Query(...),
    memory_type: MemoryType = Query(...),
    limit: int = Query(50, ge=1, le=200),
    es: Elasticsearch = Depends(es_client),
) -> dict[str, Any]:
    user_client = get_user_client(user_id)
    if user_client is not None:
        es = user_client
    items = list_memories(es, user_id=user_id, memory_type=memory_type, limit=limit)
    return {
        "items": items,
        "count": len(items),
        "isolation": "dls" if user_client is not None else "app_filter",
    }


@router.get("/users/{user_id}/key-status")
def key_status(user_id: str) -> dict[str, Any]:
    """Tell the UI whether DLS isolation is wired up for this user."""
    return {"user_id": user_id, "dls_key": has_user_key(user_id)}


@router.post("/consolidate")
def consolidate_route(
    req: ConsolidateRequest, es: Elasticsearch = Depends(es_client)
) -> dict[str, Any]:
    return consolidate(
        es,
        user_id=req.user_id,
        lookback=req.lookback,
        dry_run=req.dry_run,
    )


@router.post("/forget")
def forget(req: ForgetRequest, es: Elasticsearch = Depends(es_client)) -> dict[str, Any]:
    result = forget_memory(
        es,
        memory_id=req.memory_id,
        user_id=req.user_id,
        memory_type=req.memory_type,
    )
    if not result.get("deleted") and result.get("reason") == "unauthorized":
        raise HTTPException(status_code=403, detail=result)
    if not result.get("deleted") and result.get("reason") == "not_found":
        raise HTTPException(status_code=404, detail=result)
    return result
