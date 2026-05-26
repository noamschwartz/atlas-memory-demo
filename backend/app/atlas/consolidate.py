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

from .memory.constants import LLM_INFERENCE_ID_FAST
from .memory.operations import list_memories, update_procedural, write_memory
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
      "supersedes_id": "<id-of-existing-fact-this-replaces-or-null>"
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
FACTS:
- DO NOT duplicate any existing fact — even paraphrases.
- Only extract DURABLE facts (preferences, identity, constraints), NOT one-off questions or transient mentions.
- Pick fact_type carefully: preference (likes/dislikes), identity (who they are/where they live), constraint (allergies, hard limits), world (factual context they shared).
- Tie each fact to the supporting_episode_ids it came from.
- If a recent event SUPERSEDES an existing fact (new location replaces old, device upgraded, preference reversed), set supersedes_id to the id of the existing fact being replaced.
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
) -> dict[str, Any]:
    """Run one consolidation pass for a user.

    Returns: {"candidates": [...], "created": [...], "dry_run": bool}
    """
    episodes = list_memories(es, user_id=user_id, memory_type="episodic", limit=lookback)
    existing = list_memories(es, user_id=user_id, memory_type="semantic", limit=50)
    procedurals = list_memories(es, user_id=user_id, memory_type="procedural", limit=20)

    if not episodes:
        return {"candidates": [], "created": [], "dry_run": dry_run, "reason": "no_episodes"}

    prompt = CONSOLIDATION_PROMPT % {
        "existing": _summarize_existing(existing),
        "procedures": _summarize_procedurals(procedurals),
        "events": _summarize_events(episodes),
    }

    raw = complete_chat(
        inference_id=inference_id,
        messages=[{"role": "user", "content": prompt}],
        max_completion_tokens=2048,
    )

    try:
        parsed = _extract_json(raw)
    except json.JSONDecodeError as exc:
        logger.warning("consolidate: bad JSON from LLM: %s\nraw=%r", exc, raw)
        return {"candidates": [], "created": [], "dry_run": dry_run, "error": "bad_json"}

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
        result = write_memory(
            es,
            user_id=user_id,
            memory_type="semantic",
            text=text,
            fact_type=fact.get("fact_type") or "preference",
            confidence=float(fact.get("confidence") or 0.7),
            source_episodes=list(fact.get("supporting_episode_ids") or []),
            supersedes_id=old_id,
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

    return {
        "candidates": candidates,
        "created": created,
        "superseded": superseded,
        "created_procedures": created_procedures,
        "updated_procedures": updated_procedures,
        "dry_run": False,
    }
