"""Atlas chat route — SSE streaming for the personal-assistant demo."""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from typing import Any

from elasticsearch import Elasticsearch
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from ..agent import run_turn
from ...elasticsearch.client import es_client

router = APIRouter(prefix="/api/atlas", tags=["atlas"])
logger = logging.getLogger(__name__)


class ChatRequest(BaseModel):
    user_id: str
    session_id: str
    message: str
    history: list[dict[str, Any]] = Field(default_factory=list)


@router.post("/chat")
def chat(req: ChatRequest, es: Elasticsearch = Depends(es_client)) -> StreamingResponse:
    """Stream agent events back as SSE."""

    def event_stream() -> Iterator[bytes]:
        try:
            for payload in run_turn(
                es,
                user_id=req.user_id,
                session_id=req.session_id,
                history=req.history,
                user_message=req.message,
            ):
                yield f"data: {json.dumps(payload)}\n\n".encode()
        except Exception as exc:  # noqa: BLE001
            logger.exception("Atlas chat failed")
            err = {"event": "error", "message": str(exc)}
            yield f"data: {json.dumps(err)}\n\n".encode()

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
