"""Atlas Memory MCP server.

Exposes Atlas's four memory operations (recall / write / forget / list) as
an MCP-compatible JSON-RPC 2.0 endpoint, so any MCP-aware agent (Claude
Desktop, Cursor, custom) can plug into the same memory layer the Atlas
chat UI uses.

Transport: HTTP POST with JSON-RPC 2.0 bodies.
URL shape: POST /api/atlas/mcp/{user_id}
  - The user_id segment scopes the agent's view to one user's memory.
  - In production you would also require an auth header here.

Methods supported (subset of MCP 2024-11-05):
  - initialize / notifications/initialized
  - ping
  - tools/list
  - tools/call

Connect from Claude Desktop or Cursor via `mcp-remote`:
  {
    "mcpServers": {
      "atlas-memory-sarah": {
        "command": "npx",
        "args": ["-y", "mcp-remote", "http://localhost:8001/api/atlas/mcp/sarah"]
      }
    }
  }
"""

from __future__ import annotations

import json
import logging
from typing import Any

from elasticsearch import Elasticsearch
from fastapi import APIRouter, Depends, HTTPException, Path

from ..tools import dispatch, tool_schemas
from ...elasticsearch.client import es_client
from ..memory.user_keys import get_user_client

router = APIRouter(prefix="/api/atlas/mcp", tags=["atlas-mcp"])
logger = logging.getLogger(__name__)

PROTOCOL_VERSION = "2024-11-05"
SERVER_NAME = "atlas-memory"
SERVER_VERSION = "1.0.0"


def _to_mcp_tool(spec: dict[str, Any]) -> dict[str, Any]:
    """Convert our OpenAI-style tool spec to MCP tool shape."""
    fn = spec["function"]
    return {
        "name": fn["name"],
        "description": fn.get("description", ""),
        "inputSchema": fn.get("parameters", {"type": "object"}),
    }


def _ok(rpc_id: Any, result: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": rpc_id, "result": result}


def _err(rpc_id: Any, code: int, message: str, data: Any = None) -> dict[str, Any]:
    err: dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        err["data"] = data
    return {"jsonrpc": "2.0", "id": rpc_id, "error": err}


def _handle_tools_call(
    es: Elasticsearch, user_id: str, params: dict[str, Any]
) -> dict[str, Any]:
    name = params.get("name", "")
    arguments = params.get("arguments") or {}

    # Use DLS-scoped client if available so memory MCP enforces isolation
    # at the cluster, not just app-side. The admin client is passed
    # separately for the recall stat bump (DLS keys are read-only).
    user_es = get_user_client(user_id) or es
    stats_es = es if user_es is not es else None

    try:
        result = dispatch(
            user_es,
            user_id=user_id,
            name=name,
            arguments=arguments,
            stats_es=stats_es,
        )
    except ValueError as exc:
        return {
            "isError": True,
            "content": [{"type": "text", "text": f"Unknown tool: {exc}"}],
        }
    except Exception as exc:  # noqa: BLE001
        logger.exception("MCP tool %s failed", name)
        return {
            "isError": True,
            "content": [{"type": "text", "text": f"Tool error: {exc}"}],
        }

    return {
        "isError": False,
        "content": [{"type": "text", "text": json.dumps(result, default=str)}],
        "structuredContent": result,
    }


@router.post("/{user_id}")
async def mcp_endpoint(
    body: dict[str, Any],
    user_id: str = Path(..., min_length=1),
    es: Elasticsearch = Depends(es_client),
) -> dict[str, Any] | None:
    """Single JSON-RPC entry point per user."""
    if body.get("jsonrpc") != "2.0":
        raise HTTPException(status_code=400, detail="invalid jsonrpc")
    method = body.get("method", "")
    rpc_id = body.get("id")
    params = body.get("params") or {}

    if method == "initialize":
        return _ok(
            rpc_id,
            {
                "protocolVersion": PROTOCOL_VERSION,
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
                "capabilities": {"tools": {"listChanged": False}},
            },
        )
    if method == "notifications/initialized":
        # No response expected per JSON-RPC for notifications.
        return None
    if method == "ping":
        return _ok(rpc_id, {})
    if method == "tools/list":
        tools = [_to_mcp_tool(s) for s in tool_schemas()]
        return _ok(rpc_id, {"tools": tools})
    if method == "tools/call":
        return _ok(rpc_id, _handle_tools_call(es, user_id, params))

    return _err(rpc_id, -32601, f"method not found: {method}")


@router.get("/{user_id}/info")
def mcp_info(user_id: str) -> dict[str, Any]:
    """Human-readable info plus a paste-ready Claude Desktop / Cursor config."""
    cfg = {
        "mcpServers": {
            f"atlas-memory-{user_id}": {
                "command": "npx",
                "args": [
                    "-y",
                    "mcp-remote",
                    f"http://localhost:8001/api/atlas/mcp/{user_id}",
                ],
            }
        }
    }
    return {
        "server": SERVER_NAME,
        "version": SERVER_VERSION,
        "user_id": user_id,
        "endpoint": f"/api/atlas/mcp/{user_id}",
        "tools": [t["function"]["name"] for t in tool_schemas()],
        "client_config": cfg,
    }
