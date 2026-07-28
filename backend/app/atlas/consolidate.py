"""Atlas memory consolidation.

Distills recent episodic events into durable semantic facts. Lets the LLM
both extract candidate facts AND dedupe against existing semantic memory in
a single call — that one-shot dedup avoids per-fact embedding-similarity
checks while still tracing each new fact back to its source episodes.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from elasticsearch import Elasticsearch

from .memory.constants import (
    CONSOLIDATION_EXISTING_FACTS_LIMIT,
    CONSOLIDATION_MAX_TOKENS,
    LLM_INFERENCE_ID_FAST,
)
from .memory.operations import list_memories, update_procedural, write_memory
from .memory.state import ensure_watermark, episodes_since, set_watermark
from .llm import complete_chat

logger = logging.getLogger(__name__)

CONSOLIDATION_PROMPT = """<role>
You are the consolidation loop for Atlas, a memory layer. Your job is to examine recent episodic events about a user and extract NEW durable facts worth promoting to semantic memory.
</role>

<output_format>
Return STRICT JSON (no commentary, no markdown fence):
{
  "new_facts": [
    {
      "text": "Short sentence stating the fact, written in third person.",
      "fact_type": "preference" | "identity" | "constraint" | "world",
      "confidence": 0.0-1.0,
      "supporting_episode_ids": ["<episode-id>", ...],
      "supersedes_id": "<id-of-existing-fact-this-replaces-or-null>",
      "contradiction": "natural" | "harsh"
    }
  ],
  "new_procedures": [
    {
      "name": "snake_case_id",
      "trigger_text": "One sentence describing when to apply this procedure.",
      "description": "Brief description of what this procedure achieves.",
      "steps": [{"order": 1, "instruction": "...", "tool": "ask_user|recall_memory|escalate"}],
      "supporting_episode_ids": ["<episode-id>", ...],
      "confidence": 0.0-1.0
    }
  ],
  "procedural_updates": [
    {
      "id": "<existing-procedure-id>",
      "outcome": "success" | "failure",
      "supporting_episode_ids": ["<episode-id>", ...],
      "refined_steps": []
    }
  ]
}
</output_format>

<rules>
USING <assistant_reply_context>:
- It holds the last few things the assistant said to the customer, oldest first, separated by `--- next assistant turn ---`. It is NOT part of the customer's record and is NOT evidence.
- It spans several turns on purpose. A customer confirms a fix one turn AFTER receiving it, so when an event says "it worked", the steps being confirmed are in an EARLIER assistant turn, not the latest one. Look back through the block to find what is actually being confirmed.
- Use it for two things only: (1) to interpret an elliptical customer message, since "yes", "that worked" and "still broken" are meaningless without knowing what was asked or advised; and (2) to ground the `steps` of a procedure, since the steps were described on the assistant's side.
- NEVER extract a fact from it. Anything the assistant asserted is unverified model output. If the assistant claimed the customer owns a Hub v2 and the customer never said so, that is not a fact. The customer must have said or confirmed it in <recent_events>.
- A commitment the assistant made ("I've flagged your account, billing will email within 2 working days") may be recorded, but as fact_type "world" and only when the customer's own messages show they were told. Never as identity or constraint.
- supporting_episode_ids must always cite ids from <recent_events>. The assistant context has no ids and can never be cited.

FACTS:
- DO NOT duplicate any existing fact — even paraphrases.
- Only extract DURABLE facts (preferences, identity, constraints), NOT one-off questions or transient mentions.
- Pick fact_type carefully. `identity` and `constraint` are NOT just labels: every fact carrying one is injected into the assistant's context on EVERY future turn, whether or not it is relevant to what was asked. Mistyping a transient observation as one of them permanently pollutes that context.
    - `identity`  — stable facts about WHO the customer is and what they own. True for months or years. "Lives in Bristol." "Owns a Hub v2." "Has a newborn son, Theo."
    - `constraint` — a HARD LIMIT the assistant must always respect. An allergy, an accessibility need, a quiet-hours rule, a physical limitation of their home. If violating it would produce a harmful or unusable answer, it is a constraint.
    - `preference` — likes, dislikes, chosen settings. Real, but not always-relevant.
    - `world`      — situational or time-bound context: what happened, what was resolved, current status. Anything phrased as an event, an outcome, or a "currently"/"no longer"/"recently" statement belongs here.
  Test before using identity or constraint: "would this still matter, unprompted, in an unrelated conversation six months from now?" If not, it is `world` or `preference`.
  "The Zigbee regression was resolved in February" is `world`, not `constraint`. "Automations are working again" is `world`, not `constraint`.
- Tie each fact to the supporting_episode_ids it came from.
- If a recent event SUPERSEDES an existing fact (new location replaces old, device upgraded, preference reversed), set supersedes_id to the id of the existing fact being replaced.
- When you set supersedes_id, ALSO set contradiction:
    - "natural" (default) if the old fact WAS true and has simply stopped being true — the customer moved, upgraded, changed their mind. The old fact stays on record as legitimate prior state.
    - "harsh" if the old fact was NEVER true — the customer denied it outright ("I never had one", "that was my sister, not me"). The old fact is marked retracted so it is never recounted back to them as something they did.
  This distinction cannot be recovered later, so make it here.
- Events are listed OLDEST FIRST. When two events conflict, the LATER one wins.
- If nothing durable is new, use an empty array for new_facts.

PROCEDURES:
- Create a new procedure (new_procedures) ONLY when episodes show a complete multi-step resolution that does NOT match any existing procedure's trigger_text. Confidence must be >= 0.8 to create.
- Record a procedural_update when episodes show an existing procedure was followed:
    - Set outcome="success" if the customer confirmed the issue was resolved ("that worked", "all good", "fixed").
    - Set outcome="failure" if the customer reported the steps did not help.
- Include refined_steps ONLY when episodes contain explicit evidence that a specific step was wrong or a better step was discovered. Omit refined_steps entirely otherwise.
- Every procedural_update and new_procedure must cite supporting_episode_ids.
- If no procedural changes are warranted, use empty arrays for new_procedures and procedural_updates.
</rules>

<existing_facts>
%(existing)s
</existing_facts>

<existing_procedures>
%(procedures)s
</existing_procedures>

<recent_events>
%(events)s
</recent_events>

<assistant_reply_context>
%(assistant_context)s
</assistant_reply_context>
"""


def _summarize_existing(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "(none)"
    out = []
    for r in rows:
        src = r["source"]
        out.append(
            f"- id={r['id']} [{src.get('fact_type', 'fact')}] {src.get('text', '')}"
        )
    return "\n".join(out)


def _summarize_procedurals(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "(none)"
    out = []
    for r in rows:
        src = r["source"]
        steps = src.get("steps") or []
        out.append(
            f"- id={r['id']} name={src.get('name', '?')} "
            f"trigger=\"{src.get('trigger_text', '')[:80]}\" "
            f"steps={len(steps)} "
            f"success={src.get('success_count', 0)} failure={src.get('failure_count', 0)}"
        )
    return "\n".join(out)


def _summarize_events(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "(none)"
    out = []
    for r in rows:
        src = r["source"]
        role = src.get("role") or src.get("event_type") or "event"
        ts = src.get("timestamp", "")
        out.append(f"- id={r['id']} role={role} ts={ts}\n  {src.get('text', '')}")
    return "\n".join(out)


_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


def _extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    # Strip markdown fences if present.
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text, count=1).strip()
        text = re.sub(r"```$", "", text, count=1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = _JSON_RE.search(text)
        if m:
            return json.loads(m.group(0))
        raise


def consolidate(
    es: Elasticsearch,
    *,
    user_id: str,
    lookback: int = 30,
    dry_run: bool = False,
    inference_id: str = LLM_INFERENCE_ID_FAST,
    assistant_context: str | None = None,
) -> dict[str, Any]:
    """Run one consolidation pass for a user.

    `assistant_context` is the prose the agent produced in the exchange that
    triggered this pass. It is shown to the extractor and then discarded: it is
    never indexed, never cited as a source, and never itself a fact.

    Extraction needs it because the customer's half of a dialogue is frequently
    elliptical. "Yes", "that worked", "still nothing" carry no information
    without the question or the advice they answer, and a procedure's steps are
    described on the agent's side, not the customer's. Reading both sides while
    attributing facts to only one is the same split Zep exposes as
    `ignore_roles`: the ignored role still contextualises, it just does not
    become memory.

    Optional, and callers that omit it get the previous behaviour exactly.

    Returns: {"candidates": [...], "created": [...], "dry_run": bool}
    """
    # Only look at episodes this user has not already had consolidated.
    #
    # Previously this read the `lookback` most recent episodes on every turn
    # with nothing recording what had already been distilled, so turn N+1
    # re-processed 29 of the 30 episodes turn N had just seen. That cost a full
    # LLM call per turn regardless of whether anything durable had happened,
    # and leaned entirely on a prose "do not duplicate" instruction to stop the
    # same fact being written twice.
    #
    # `ensure_watermark` returns None when the watermark store is unavailable
    # (typically: `atlas_memory_state` not provisioned yet, or the app key not
    # granted access). In that case fall back to the previous behaviour rather
    # than consolidating nothing — degrading to the old path is acceptable,
    # silently disabling consolidation is not.
    watermark = ensure_watermark(es, user_id)
    if watermark:
        episodes = episodes_since(es, user_id=user_id, since=watermark, limit=lookback)
    else:
        # Legacy path. list_memories returns newest-first; reverse it so the
        # model sees events in the order they happened (see below).
        episodes = list(reversed(
            list_memories(es, user_id=user_id, memory_type="episodic", limit=lookback)
        ))

    existing = list_memories(
        es,
        user_id=user_id,
        memory_type="semantic",
        limit=CONSOLIDATION_EXISTING_FACTS_LIMIT,
        # Archived facts are not candidates for duplication and must not be
        # re-superseded; excluding them also stops them consuming the window.
        include_superseded=False,
    )
    procedurals = list_memories(es, user_id=user_id, memory_type="procedural", limit=20)

    if not episodes:
        # With a watermark in place this is the common case, not an edge case:
        # a turn that produced nothing new costs zero LLM calls.
        return {"candidates": [], "created": [], "dry_run": dry_run, "reason": "no_episodes"}

    prompt = CONSOLIDATION_PROMPT % {
        "existing": _summarize_existing(existing),
        "procedures": _summarize_procedurals(procedurals),
        "events": _summarize_events(episodes),
        "assistant_context": (assistant_context or "").strip() or "(none)",
    }

    raw = complete_chat(
        inference_id=inference_id,
        messages=[{"role": "user", "content": prompt}],
        # 2048 was not enough: a backlog of episodes produces ten-plus facts
        # and multi-step procedures, and the response was being cut off
        # mid-object, so the whole pass was discarded as "bad_json" and every
        # fact in it was lost silently. With the watermark active a normal turn
        # yields a fraction of this, but the ceiling has to cover the catch-up
        # case and the legacy fallback path.
        max_completion_tokens=CONSOLIDATION_MAX_TOKENS,
    )

    try:
        parsed = _extract_json(raw)
    except json.JSONDecodeError as exc:
        # Distinguish a truncated response from genuinely malformed output;
        # they have completely different fixes and used to look identical.
        truncated = bool(raw) and not raw.rstrip().endswith(("}", "```"))
        logger.warning(
            "consolidate: %s from LLM (%s chars): %s",
            "TRUNCATED response — raise CONSOLIDATION_MAX_TOKENS" if truncated
            else "malformed JSON",
            len(raw),
            exc,
        )
        logger.debug("consolidate: raw output was %r", raw)
        return {
            "candidates": [], "created": [], "dry_run": dry_run,
            "error": "truncated" if truncated else "bad_json",
        }

    candidates: list[dict[str, Any]] = parsed.get("new_facts", []) or []
    new_procedures: list[dict[str, Any]] = parsed.get("new_procedures", []) or []
    procedural_updates: list[dict[str, Any]] = parsed.get("procedural_updates", []) or []

    if dry_run:
        return {
            "candidates": candidates,
            "created": [],
            "new_procedures": new_procedures,
            "procedural_updates": procedural_updates,
            "dry_run": True,
        }

    # --- semantic facts ---
    # Supersession is soft: write_memory marks the old doc with `superseded_by`
    # and `superseded_at`, and the recall filter hides it. The audit trail
    # stays in the index.
    created: list[dict[str, Any]] = []
    superseded: list[str] = []
    for fact in candidates:
        text = (fact.get("text") or "").strip()
        if not text:
            continue
        old_id = (fact.get("supersedes_id") or "").strip() or None
        # `contradiction` was never forwarded here, so the background path could
        # not express harsh supersession at all: every consolidation-driven
        # supersession looked "natural" regardless of what the customer said.
        # This matters most if consolidation is ever moved to a background
        # job, that would have silently dropped the distinction entirely.
        contradiction = (fact.get("contradiction") or "").strip().lower() or None
        if contradiction not in ("harsh", "natural", None):
            contradiction = None
        result = write_memory(
            es,
            user_id=user_id,
            memory_type="semantic",
            text=text,
            fact_type=fact.get("fact_type") or "preference",
            confidence=float(fact.get("confidence") or 0.7),
            source_episodes=list(fact.get("supporting_episode_ids") or []),
            supersedes_id=old_id,
            contradiction=contradiction,
            # Consolidation may lower confidence on a harsh contradiction, but
            # may not mark the old fact `retracted`. Retraction is a hard rule
            # ("never recount this to the customer"), and consolidation infers
            # the contradiction second-hand from stored episodes rather than
            # from the customer's words in context. A misread would permanently
            # flag a true memory as never-true. The in-turn agent path, where
            # the utterance is right there, keeps the capability.
            allow_retraction=False,
            refresh=True,
        )
        if old_id:
            superseded.append(old_id)
        created.append({**result, "fact": fact})

    # --- new procedural playbooks ---
    PROCEDURE_CONFIDENCE_THRESHOLD = 0.8
    created_procedures: list[dict[str, Any]] = []
    for proc in new_procedures:
        if float(proc.get("confidence") or 0) < PROCEDURE_CONFIDENCE_THRESHOLD:
            logger.info("consolidate: skipping low-confidence procedure %s", proc.get("name"))
            continue
        trigger = (proc.get("trigger_text") or "").strip()
        if not trigger:
            continue
        result = write_memory(
            es,
            user_id=user_id,
            memory_type="procedural",
            text=trigger,
            name=proc.get("name") or trigger[:60],
            description=proc.get("description") or "",
            steps=list(proc.get("steps") or []),
            refresh=True,
        )
        created_procedures.append({**result, "procedure": proc})

    # --- procedural updates (success/failure counters + step refinement) ---
    updated_procedures: list[dict[str, Any]] = []
    for upd in procedural_updates:
        proc_id = (upd.get("id") or "").strip()
        outcome = (upd.get("outcome") or "").strip()
        if not proc_id or outcome not in ("success", "failure"):
            continue
        refined = upd.get("refined_steps") or None
        result = update_procedural(
            es,
            memory_id=proc_id,
            user_id=user_id,
            outcome=outcome,
            refined_steps=refined if refined else None,
        )
        updated_procedures.append(result)

    # Advance the watermark only after the writes above have succeeded, and only
    # as far as the newest episode actually processed — not to "now". Stamping
    # `now` would swallow any episode written while this pass was running.
    # On the legacy path (no watermark store) this is a no-op.
    if watermark:
        newest = max(
            (e["source"].get("timestamp") for e in episodes if e["source"].get("timestamp")),
            default=None,
        )
        if newest:
            set_watermark(es, user_id, newest)

    return {
        "candidates": candidates,
        "created": created,
        "superseded": superseded,
        "created_procedures": created_procedures,
        "updated_procedures": updated_procedures,
        "dry_run": False,
        "episodes_considered": len(episodes),
        "watermark_active": bool(watermark),
    }
