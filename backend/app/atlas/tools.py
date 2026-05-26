"""Tool definitions and dispatch for the Atlas agent.

Tools are exposed to the LLM in OpenAI function-calling format and dispatched
through the same operations module the REST routes use.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from elasticsearch import Elasticsearch

from .memory.operations import (
    forget_memory,
    list_memories,
    recall_memory,
    write_memory,
)

logger = logging.getLogger(__name__)


def tool_schemas() -> list[dict[str, Any]]:
    """OpenAI-compatible tool list for chat_completion."""
    return [
        {
            "type": "function",
            "function": {
                "name": "recall_memory",
                "description": (
                    "Search the user's memory (episodic events, semantic facts, "
                    "procedural playbooks). Use at the START of every turn if "
                    "the user might be referring to past context."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Natural-language query, e.g. 'food allergies'.",
                        },
                        "memory_types": {
                            "type": "array",
                            "items": {
                                "type": "string",
                                "enum": ["episodic", "semantic", "procedural"],
                            },
                            "description": "Restrict to certain memory types. Omit for all.",
                        },
                        "k": {
                            "type": "integer",
                            "description": "How many results to return (1-20).",
                            "default": 10,
                        },
                        "include_catalog": {
                            "type": "boolean",
                            "description": (
                                "Federate over the shared catalog index in "
                                "addition to per-user memory. Useful when the "
                                "user's question can be grounded in known "
                                "world knowledge (restaurants, guides, etc.)."
                            ),
                            "default": False,
                        },
                    },
                    "required": ["query"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "write_memory",
                "description": (
                    "Store a new memory. Use SEMANTIC for stable facts about "
                    "the user (preferences, identity, constraints, allergies). "
                    "Use PROCEDURAL only when the user explicitly asks you to "
                    "remember a multi-step playbook. Do NOT write a semantic "
                    "fact that already exists in recall results. To replace a "
                    "fact that the customer just contradicted, pass "
                    "supersedes_id with the recalled id of the old fact; the "
                    "old fact will be soft-superseded (kept for audit but "
                    "hidden from future recall) instead of hard-deleted."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "memory_type": {
                            "type": "string",
                            "enum": ["semantic", "procedural"],
                        },
                        "text": {
                            "type": "string",
                            "description": "The fact or trigger text to store.",
                        },
                        "fact_type": {
                            "type": "string",
                            "enum": ["preference", "identity", "constraint", "world"],
                            "description": "For semantic: kind of fact.",
                        },
                        "confidence": {
                            "type": "number",
                            "description": "0.0-1.0 confidence in this fact.",
                        },
                        "supersedes_id": {
                            "type": "string",
                            "description": (
                                "Optional. If this semantic write replaces a "
                                "contradicted fact, pass the old fact's id "
                                "here. The old fact is soft-superseded: hidden "
                                "from future recall but kept for audit."
                            ),
                        },
                        "contradiction": {
                            "type": "string",
                            "enum": ["harsh", "natural"],
                            "description": (
                                "When set alongside supersedes_id, classifies "
                                "the contradiction. 'harsh' = customer "
                                "explicitly denied or corrected the prior "
                                "fact ('no, that's wrong', 'I never X'); "
                                "applies a small confidence penalty to the "
                                "new fact. 'natural' (default) = routine "
                                "update (moved, upgraded, preference "
                                "change); no penalty."
                            ),
                        },
                    },
                    "required": ["memory_type", "text"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "forget_memory",
                "description": "Delete a specific memory by id. Used when the user explicitly asks Atlas to forget something.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "memory_id": {"type": "string"},
                        "memory_type": {
                            "type": "string",
                            "enum": ["episodic", "semantic", "procedural"],
                        },
                    },
                    "required": ["memory_id", "memory_type"],
                },
            },
        },
    ]


def dispatch(
    es: Elasticsearch,
    *,
    user_id: str,
    name: str,
    arguments: dict[str, Any],
    stats_es: Elasticsearch | None = None,
) -> dict[str, Any]:
    """Run a tool call against the memory backend.

    `es` is the read client (typically a DLS-scoped user client when minted).
    `stats_es` is an optional admin client used only for the recall stat
    bump; pass it when the read client lacks update privileges.
    """
    if name == "recall_memory":
        hits = recall_memory(
            es,
            query=arguments["query"],
            user_id=user_id,
            memory_types=arguments.get("memory_types"),
            k=int(arguments.get("k", 10)),
            include_catalog=bool(arguments.get("include_catalog", False)),
            update_stats=True,
            stats_es=stats_es,
        )
        # Trim payload going back to the LLM.
        compact = [
            {
                "id": h["id"],
                "memory_type": h["memory_type"],
                "rank": h["rank"],
                "score": h["score"],
                "text": h["source"].get("text") or h["source"].get("trigger_text", ""),
                "fact_type": h["source"].get("fact_type"),
                # Anchor the memory in time so the agent can answer "when" questions.
                # Episodic uses the event timestamp; semantic and procedural fall
                # back to the doc's creation time.
                "timestamp": (
                    h["source"].get("timestamp")
                    or h["source"].get("created_at")
                ),
            }
            for h in hits
        ]
        return {"hits": compact, "count": len(compact)}

    if name == "write_memory":
        # Writes also use the admin client when available, so user-scoped DLS
        # keys without update privileges still record contradictions cleanly.
        write_es = stats_es or es
        return write_memory(
            write_es,
            user_id=user_id,
            memory_type=arguments["memory_type"],
            text=arguments["text"],
            fact_type=arguments.get("fact_type"),
            confidence=arguments.get("confidence"),
            supersedes_id=arguments.get("supersedes_id"),
            contradiction=arguments.get("contradiction"),
            refresh=True,
        )

    if name == "forget_memory":
        return forget_memory(
            es,
            user_id=user_id,
            memory_type=arguments["memory_type"],
            memory_id=arguments["memory_id"],
        )

    raise ValueError(f"Unknown tool {name!r}")


def parse_arguments(raw: str | dict[str, Any] | None) -> dict[str, Any]:
    """Tool arguments come as a JSON string in OpenAI format."""
    if raw is None or raw == "":
        return {}
    if isinstance(raw, dict):
        return raw
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.warning("Bad tool argument JSON: %s -- %s", exc, raw)
        return {}
