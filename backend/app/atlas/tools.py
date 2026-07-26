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
                        "include_superseded": {
                            "type": "boolean",
                            "description": (
                                "Include soft-superseded semantic facts in "
                                "the results (e.g. old addresses, prior "
                                "preferences the customer has since "
                                "contradicted). Default false. Set true when "
                                "the customer asks a retrospective question "
                                "(\"places I've lived\", \"fixes we've "
                                "tried\")."
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
                                "fact ('no, that's wrong', 'I never X'); the "
                                "old fact is marked retracted (it was never "
                                "true) rather than archived as prior state, "
                                "and the new fact takes a small confidence "
                                "penalty. 'natural' (default) = routine "
                                "update (moved, upgraded, preference "
                                "change); the old fact stays as legitimate "
                                "history, no penalty."
                            ),
                        },
                        # The three fields below exist so a PROCEDURAL write can
                        # actually carry a playbook. Without them the schema
                        # offered no way to express steps, so every
                        # agent-written procedural fell through to
                        # `steps: []` / `description: ""` / `name = text[:60]`
                        # — while the system prompt instructed the agent to
                        # "follow its steps". There were none to follow.
                        "name": {
                            "type": "string",
                            "description": (
                                "For procedural: short snake_case identifier, "
                                "e.g. 'zigbee_reconnect'. Defaults to a "
                                "truncation of `text` if omitted."
                            ),
                        },
                        "description": {
                            "type": "string",
                            "description": (
                                "For procedural: one sentence on what the "
                                "playbook achieves."
                            ),
                        },
                        "steps": {
                            "type": "array",
                            "description": (
                                "For procedural: the ordered steps to follow. "
                                "Required for a playbook to be usable — a "
                                "procedural memory with no steps cannot be "
                                "acted on when it is later recalled."
                            ),
                            "items": {
                                "type": "object",
                                "properties": {
                                    "order": {"type": "integer"},
                                    "instruction": {"type": "string"},
                                    "tool": {
                                        "type": "string",
                                        "enum": ["ask_user", "recall_memory", "escalate"],
                                    },
                                },
                                "required": ["order", "instruction"],
                            },
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
            include_superseded=bool(arguments.get("include_superseded", False)),
            update_stats=True,
            stats_es=stats_es,
        )
        # Trim payload going back to the LLM. When include_superseded is set,
        # surface superseded_at / superseded_by so the agent can distinguish
        # archived state from current state in its reply.
        compact = []
        for h in hits:
            src = h["source"]
            item = {
                "id": h["id"],
                "memory_type": h["memory_type"],
                "rank": h["rank"],
                "score": h["score"],
                "text": src.get("text") or src.get("trigger_text", ""),
                "fact_type": src.get("fact_type"),
                # Anchor the memory in time so the agent can answer "when" questions.
                # Episodic uses the event timestamp; semantic and procedural fall
                # back to the doc's creation time.
                "timestamp": src.get("timestamp") or src.get("created_at"),
            }
            # Confidence was written on every semantic fact — and reduced by
            # SUPERSEDE_CONFIDENCE_PENALTY on a harsh supersession — but never
            # reached the model. The agent was asked to "hedge" on a number it
            # could not see. Surfacing it is what makes that penalty mean
            # anything at all.
            if src.get("confidence") is not None:
                item["confidence"] = src["confidence"]
            if src.get("superseded_at"):
                item["superseded_at"] = src["superseded_at"]
            if src.get("superseded_by"):
                item["superseded_by"] = src["superseded_by"]
            # A retracted fact was never true. Without this the agent cannot
            # tell it apart from a fact that has merely stopped being true, and
            # the system prompt's "treat superseded hits as prior state" rule
            # turns a denial into recounted history.
            if src.get("retracted"):
                item["retracted"] = True
            # A procedural memory is its steps. The system prompt instructs the
            # agent to "follow its steps", but the compact payload carried only
            # `trigger_text`, so a recalled playbook arrived with nothing to
            # follow and the agent said so out loud in testing:
            #   "The procedural memory matched but didn't return steps"
            # Adding the schema fields (C1) let the agent WRITE a playbook;
            # this is what lets it READ one back.
            if h["memory_type"] == "procedural":
                item["name"] = src.get("name")
                item["description"] = src.get("description")
                item["steps"] = src.get("steps") or []
                item["success_count"] = src.get("success_count", 0)
                item["failure_count"] = src.get("failure_count", 0)
            compact.append(item)
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
            # Forwarded so a procedural write can carry its playbook; these were
            # absent from both the schema and this call, so agent-written
            # procedurals were always step-less.
            name=arguments.get("name"),
            description=arguments.get("description"),
            steps=arguments.get("steps"),
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
