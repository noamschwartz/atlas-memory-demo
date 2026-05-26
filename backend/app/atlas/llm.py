"""Streaming client for Elasticsearch's chat_completion EIS endpoint.

Wraps the OpenAI-compatible SSE protocol so the agent loop can iterate over
either text chunks or completed tool calls without re-implementing parsing.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

import requests

from ..config import settings

logger = logging.getLogger(__name__)


@dataclass
class ToolCallAccumulator:
    id: str = ""
    name: str = ""
    arguments: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "name": self.name, "arguments": self.arguments}


@dataclass
class StreamEvent:
    """Normalized event yielded by `stream_chat`."""
    kind: str  # "text" | "tool_call" | "stop"
    text: str = ""
    tool_call: dict[str, Any] | None = None
    finish_reason: str | None = None


@dataclass
class StreamResult:
    """Accumulated end-of-stream snapshot for the agent loop."""
    text: str = ""
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    finish_reason: str | None = None


def complete_chat(
    *,
    inference_id: str,
    messages: list[dict[str, Any]],
    max_completion_tokens: int = 2048,
) -> str:
    """Drive the streaming endpoint to completion and return the full text.

    Used by non-interactive flows like consolidation that don't need to
    surface intermediate tokens.
    """
    out: list[str] = []
    for ev in stream_chat(
        inference_id=inference_id,
        messages=messages,
        max_completion_tokens=max_completion_tokens,
    ):
        if ev.kind == "text" and ev.text:
            out.append(ev.text)
    return "".join(out)


def stream_chat(
    *,
    inference_id: str,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None = None,
    max_completion_tokens: int = 1024,
) -> Iterator[StreamEvent]:
    """Yield normalized events from the EIS chat_completion stream.

    Also accumulates the full snapshot into a `StreamResult` accessible via
    `stream_chat.result` after iteration (set as a function attribute) — but
    callers should prefer building their own result object from the events.
    """
    url = f"{settings.ELASTICSEARCH_URL}/_inference/chat_completion/{inference_id}/_stream"
    headers = {
        "Authorization": f"ApiKey {settings.ELASTIC_API_KEY}",
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
    }
    body: dict[str, Any] = {
        "messages": messages,
        "max_completion_tokens": max_completion_tokens,
    }
    if tools:
        body["tools"] = tools

    tool_calls: dict[int, ToolCallAccumulator] = {}

    with requests.post(url, headers=headers, json=body, stream=True, timeout=120) as resp:
        resp.raise_for_status()
        resp.encoding = "utf-8"  # force UTF-8; EIS SSE has no explicit charset in Content-Type
        for raw_line in resp.iter_lines(decode_unicode=True):
            if not raw_line:
                continue
            # Strip BOM and 'data: ' prefix; ignore non-data lines.
            line = raw_line.lstrip("﻿").strip()
            if line.startswith("event:"):
                continue
            if not line.startswith("data:"):
                continue
            payload = line[len("data:"):].strip()
            if payload == "[DONE]":
                break
            try:
                chunk = json.loads(payload)
            except json.JSONDecodeError:
                logger.warning("non-JSON SSE payload: %r", payload[:200])
                continue

            choices = chunk.get("choices") or []
            if not choices:
                continue
            choice = choices[0]
            delta = choice.get("delta") or {}

            content = delta.get("content")
            if content:
                yield StreamEvent(kind="text", text=content)

            for tc in delta.get("tool_calls") or []:
                idx = tc.get("index", 0)
                acc = tool_calls.setdefault(idx, ToolCallAccumulator())
                if tc.get("id"):
                    acc.id = tc["id"]
                fn = tc.get("function") or {}
                if fn.get("name"):
                    acc.name = fn["name"]
                if fn.get("arguments"):
                    acc.arguments += fn["arguments"]

            finish = choice.get("finish_reason")
            if finish:
                # Emit any completed tool calls then a stop event.
                for tc in tool_calls.values():
                    if tc.name:
                        yield StreamEvent(kind="tool_call", tool_call=tc.to_dict())
                yield StreamEvent(kind="stop", finish_reason=finish)
                return
