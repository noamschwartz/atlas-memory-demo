"""Atlas agent loop — multi-turn tool use over an EIS chat_completion model.

Each user turn:
  1. Persist the user message as an episodic memory (event_type=user_message).
  2. Run the LLM with the memory tools available; loop on tool calls up to
     MAX_ITERATIONS times.
  3. Persist the final assistant message as episodic.
  4. Yield structured SSE events to the caller for live UI rendering.
"""

from __future__ import annotations

import json
import logging
import uuid
from collections.abc import Iterator
from datetime import datetime, timezone
from typing import Any

from elasticsearch import Elasticsearch

from .consolidate import consolidate
from .memory.constants import LLM_INFERENCE_ID
from .memory.operations import core_memory, write_memory
from .llm import StreamResult, stream_chat
from .tools import dispatch, parse_arguments, tool_schemas

logger = logging.getLogger(__name__)

MAX_ITERATIONS = 5

SYSTEM_PROMPT_TEMPLATE = """<context>
Today is {today}. Recalled memories include a `timestamp` field (event time for episodic, creation time for semantic and procedural) — use it when the customer asks "when" questions, and prefer it over guessing from prose.
</context>

<customer_profile>
Durable facts about this customer — their identity and their hard constraints. These are always
in context because their relevance does not depend on what was asked: a constraint about a
sleeping baby or a barge's shore power matters to a troubleshooting answer even when the
customer's message shares no words with it. Treat these as established. Do not ask the customer
to repeat any of it, and do not contradict it.
{core_memory}
</customer_profile>

<role>
You are the Lumio Support Assistant — a friendly, knowledgeable support agent for Lumio smart home devices.
</role>

<memory_rules>
- An initial `recall_memory` call on the customer's verbatim message has already been made for this turn. Use those hits to personalize your response. Issue additional `recall_memory` calls if you want to search with refined queries — when you do, preserve the customer's literal version numbers, model names, error codes, and proper nouns in the query string.
- For any question about products, firmware, known issues, or policies, call `recall_memory` with `include_catalog=true` so the shared Lumio knowledge base is searched too.
- When the customer reveals a stable fact (devices they own, issues they have, firmware version, OS version, location, setup details), save it via `write_memory(memory_type="semantic")` IMMEDIATELY — even on a first interaction where prior recall returned nothing, and even if you also need to ask clarifying questions afterward. Save what was clearly stated; don't make the customer repeat it. Don't write a fact that already appears in recall.
- If the customer contradicts a recalled fact, supersede the old fact instead of deleting it. Call `write_memory(text=<new>, supersedes_id=<old id>, contradiction="harsh"|"natural")`. The old fact is soft-superseded — kept in the index for audit but hidden from future recall. Don't call `forget_memory` on the old fact.
  - Use `contradiction="harsh"` when the customer explicitly denies or corrects the prior fact ("no, that's wrong", "I never X", "I don't have an X"). The old fact is marked **retracted**: it was never true. The new fact is written with a small confidence penalty.
  - Use `contradiction="natural"` for routine updates (the customer moved, upgraded a device, changed a preference). The old fact was true and has stopped being true, so it stays on record as legitimate prior state. The new fact is written at full confidence.
  - Never ask the customer to confirm before superseding — the contradiction itself is the signal.
  - If recall returns multiple facts contradicted by the same new statement, issue one `write_memory(supersedes_id=…)` call per old id. Don't supersede facts that mention the same entity but remain true (e.g. *"Victorian flats in Bristol have thick walls"* stays unsuperseded after Sarah moves).
- If recall returns a procedural memory whose trigger matches the customer's issue, follow its steps. Don't invent a different troubleshooting flow.
- When the customer asks a retrospective question ("places I've lived", "what fixes have we tried", "what was on this device last time"), call `recall_memory` with `include_superseded=true` so soft-superseded facts also surface. In the reply, distinguish current state from prior state ("you live in Edinburgh now; you previously lived in Bristol").
  - A hit with `superseded_at` but no `retracted` flag is **prior state**: it was true, and it is legitimate history. Recount it as such.
  - A hit with `retracted: true` was **never true** — the customer denied it. Never recount it back to them as something they did, owned, or experienced. If it is relevant at all, refer to it only as a correction you have already applied ("I had that noted incorrectly and have removed it"). Never say "you previously..." about a retracted fact.
- Recalled facts may carry a `confidence` value (0.0-1.0). Treat anything below 0.7 as provisional: use it, but phrase it as something to confirm rather than as established fact.
- Use `forget_memory` only when the customer explicitly asks you to forget something. It is not the contradiction tool.
</memory_rules>

<response_guidelines>
- Be concise and solution-focused. Lead with the fix, then explain.
- Acknowledge recalled context naturally: "Since your Hub v2 was reset in March..."
- Never ask a customer to repeat information you already have in memory.
- If a prior fix didn't resolve the issue, acknowledge it and try something different.
</response_guidelines>
"""


def _normalize_finish(finish: str | None) -> str:
    if finish in ("tool_calls", "function_call"):
        return "tool_calls"
    return finish or "stop"


def _format_core_memory(facts: list[dict[str, Any]]) -> str:
    """Render core facts as a bulleted block for the system prompt."""
    if not facts:
        return "(no durable profile facts recorded for this customer yet)"
    return "\n".join(f"- [{f.get('fact_type', 'fact')}] {f['text']}" for f in facts)


def _system_prompt(core_facts: list[dict[str, Any]] | None = None) -> str:
    """Build the system prompt with today's date and the customer's core memory.

    Core memory is fetched per turn rather than cached: supersession and
    consolidation can both change it mid-conversation, and a stale profile block
    is worse than a slightly more expensive one (it is a filtered term query, no
    vector search).
    """
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return SYSTEM_PROMPT_TEMPLATE.format(
        today=today,
        core_memory=_format_core_memory(core_facts or []),
    )


def run_turn(
    es: Elasticsearch,
    *,
    user_id: str,
    session_id: str,
    history: list[dict[str, Any]],
    user_message: str,
    inference_id: str | None = None,
) -> Iterator[dict[str, Any]]:
    """Drive one user turn end-to-end and yield structured events.

    Each yielded dict is a JSON-serializable SSE payload with at minimum an
    `event` field. Caller wraps each as `data: <json>\\n\\n`.
    """
    inference_id = inference_id or LLM_INFERENCE_ID
    turn_id = str(uuid.uuid4())

    # Guard: empty/whitespace user messages would be rejected by the chat
    # completion endpoint (Claude returns 400). Respond gracefully instead;
    # no episodic write, no pre-recall, no LLM call.
    if not user_message or not user_message.strip():
        yield {"event": "text_chunk", "text": "I didn't catch that — could you say it again?"}
        yield {"event": "done", "turn_id": turn_id}
        return

    # 1. persist user turn
    user_doc = write_memory(
        es,
        user_id=user_id,
        memory_type="episodic",
        text=user_message,
        session_id=session_id,
        event_type="user_message",
        role="user",
    )
    yield {
        "event": "memory_write",
        "id": user_doc["id"],
        "memory_type": "episodic",
        "text": user_message,
        "role": "user",
    }

    # Core memory: identity + constraint facts, injected unconditionally. These
    # are the facts whose relevance is not query-conditional, so retrieval is
    # structurally unable to surface them on an unrelated turn.
    try:
        core_facts = core_memory(es, user_id=user_id)
    except Exception:  # noqa: BLE001
        # A profile-block failure must not take down the turn; the agent simply
        # falls back to retrieval-only, which is the previous behaviour.
        logger.warning("core memory fetch failed for %s", user_id, exc_info=True)
        core_facts = []
    if core_facts:
        yield {
            "event": "core_memory",
            "count": len(core_facts),
            "facts": core_facts,
        }

    # Working message list seeded with system + history + user turn.
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": _system_prompt(core_facts)}
    ]
    messages.extend(history)
    messages.append({"role": "user", "content": user_message})

    # Pre-recall on the user's verbatim message so BM25 always sees literal
    # keywords (version numbers, model names, error codes) before the LLM has
    # a chance to paraphrase them in its own tool calls. The result is
    # injected as a synthetic assistant tool_call + tool_result so the LLM
    # treats it as recall it just made.
    pre_recall_call_id = f"call_pre_{turn_id[:8]}"
    pre_recall_args = {"query": user_message, "k": 10, "include_catalog": True}
    yield {
        "event": "tool_call",
        "id": pre_recall_call_id,
        "name": "recall_memory",
        "arguments": pre_recall_args,
    }
    try:
        pre_recall_result = dispatch(
            es,
            user_id=user_id,
            name="recall_memory",
            arguments=pre_recall_args,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("pre-recall failed")
        pre_recall_result = {"error": str(exc), "hits": [], "count": 0}
    yield {
        "event": "tool_result",
        "id": pre_recall_call_id,
        "name": "recall_memory",
        "result": pre_recall_result,
    }
    messages.append({
        "role": "assistant",
        "tool_calls": [{
            "id": pre_recall_call_id,
            "type": "function",
            "function": {
                "name": "recall_memory",
                "arguments": json.dumps(pre_recall_args),
            },
        }],
    })
    messages.append({
        "role": "tool",
        "tool_call_id": pre_recall_call_id,
        "content": json.dumps(pre_recall_result),
    })

    final_assistant_text = ""

    for iteration in range(1, MAX_ITERATIONS + 1):
        result = StreamResult()
        for ev in stream_chat(
            inference_id=inference_id,
            messages=messages,
            tools=tool_schemas(),
            max_completion_tokens=2048,
        ):
            if ev.kind == "text":
                result.text += ev.text
                yield {"event": "text_chunk", "text": ev.text}
            elif ev.kind == "tool_call":
                result.tool_calls.append(ev.tool_call)
            elif ev.kind == "stop":
                result.finish_reason = ev.finish_reason

        finish = _normalize_finish(result.finish_reason)

        # Append the assistant turn to messages, including tool_calls if any.
        assistant_msg: dict[str, Any] = {"role": "assistant"}
        if result.text:
            assistant_msg["content"] = result.text
        if result.tool_calls:
            assistant_msg["tool_calls"] = [
                {
                    "id": tc["id"] or f"call_{i}",
                    "type": "function",
                    "function": {
                        "name": tc["name"],
                        "arguments": tc["arguments"] or "{}",
                    },
                }
                for i, tc in enumerate(result.tool_calls)
            ]
        # OpenAI-compatible spec: assistant turn must have content OR tool_calls
        if "content" not in assistant_msg and "tool_calls" not in assistant_msg:
            assistant_msg["content"] = ""
        messages.append(assistant_msg)

        if finish != "tool_calls" or not result.tool_calls:
            final_assistant_text = result.text
            break

        # Dispatch each tool call in order; surface result as a tool message.
        for i, tc in enumerate(result.tool_calls):
            args = parse_arguments(tc["arguments"])
            yield {
                "event": "tool_call",
                "id": tc["id"],
                "name": tc["name"],
                "arguments": args,
            }
            try:
                tool_result = dispatch(
                    es,
                    user_id=user_id,
                    name=tc["name"],
                    arguments=args,
                )
            except Exception as exc:  # noqa: BLE001
                logger.exception("tool %s failed", tc["name"])
                tool_result = {"error": str(exc)}
            yield {
                "event": "tool_result",
                "id": tc["id"],
                "name": tc["name"],
                "result": tool_result,
            }
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc["id"] or f"call_{i}",
                    "content": json.dumps(tool_result),
                }
            )
    else:
        logger.warning("Atlas hit MAX_ITERATIONS=%s without finishing", MAX_ITERATIONS)

    # Agent replies are intentionally NOT persisted as episodic memory:
    # they're already in the conversation history passed back to the LLM,
    # and they would otherwise pollute recall (long assistant prose dominates
    # BM25). Consolidation (Phase 5) is what distills durable knowledge.

    yield {"event": "done", "turn_id": turn_id}

    # Auto-consolidate inline — runs after chat completes so the inspector
    # shows new facts/procedures as soon as the stream closes.
    yield {"event": "consolidation_start"}
    try:
        result = consolidate(es, user_id=user_id)
        for item in result.get("created", []):
            yield {
                "event": "consolidation_fact",
                "id": item["id"],
                "memory_type": "semantic",
                "text": item["fact"].get("text", ""),
                "fact_type": item["fact"].get("fact_type"),
            }
        for item in result.get("created_procedures", []):
            yield {
                "event": "consolidation_fact",
                "id": item["id"],
                "memory_type": "procedural",
                "text": item["procedure"].get("trigger_text") or item["procedure"].get("name", ""),
            }
        for item in result.get("updated_procedures", []):
            yield {
                "event": "consolidation_update",
                "id": item.get("id", ""),
                "outcome": item.get("outcome", ""),
            }
        yield {
            "event": "consolidation_done",
            "created": len(result.get("created", [])),
            "created_procedures": len(result.get("created_procedures", [])),
            "updated_procedures": len(result.get("updated_procedures", [])),
            "superseded": len(result.get("superseded", [])),
        }
    except Exception:
        logger.warning("auto-consolidation failed", exc_info=True)
        yield {"event": "consolidation_done", "created": 0,
               "created_procedures": 0, "updated_procedures": 0, "superseded": 0}
