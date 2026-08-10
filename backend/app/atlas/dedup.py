"""Retrieval-backed deduplication for consolidation output.

The extractor is shown a recency-ordered slice of existing facts and told not to
duplicate them. That works until the corpus outgrows the slice, at which point
the fact one position past the limit becomes invisible: it cannot be
deduplicated against and it cannot be superseded. Measured on the seeded corpus,
that produced 28 near-duplicate pairs across 197 live facts, including
byte-identical copies.

A recency window also cannot catch the case that matters most. "The customer
prefers email" and "The customer asked us to stop emailing" contradict each
other while sharing almost no vocabulary. Neither ordering by age nor a lexical
scan will put them side by side.

So every candidate fact is additionally checked against its nearest existing
neighbours, retrieved with the same hybrid searcher the agent uses at recall
time. Nearest by meaning, not by age.

Three outcomes per candidate:

  DUPLICATE  the fact is already held. Drop it.
  UPDATE     it contradicts or replaces a neighbour. Keep it, and attach the
             supersedes_id the extractor failed to set.
  DISTINCT   genuinely new. Keep it.

Near-identical text short-circuits to DUPLICATE without an LLM call. Everything
else is decided by a single batched judgment covering all remaining candidates,
so the cost is one extra call per consolidation pass, not one per candidate.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from elasticsearch import Elasticsearch

from .memory.constants import (
    DEDUP_CERTAIN_SIMILARITY,
    DEDUP_NEIGHBOUR_K,
    LLM_INFERENCE_ID_FAST,
)
from .memory.operations import recall_memory
from .llm import complete_chat

logger = logging.getLogger(__name__)

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _similarity(a: str, b: str) -> float:
    """Token-set Jaccard. Cheap, and only used for the near-identical case."""
    ta = set(_TOKEN_RE.findall(a.lower()))
    tb = set(_TOKEN_RE.findall(b.lower()))
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def _neighbours(
    es: Elasticsearch,
    user_id: str,
    text: str,
    k: int = DEDUP_NEIGHBOUR_K,
) -> list[dict[str, Any]]:
    """Existing semantic facts nearest in meaning to a candidate.

    Uses the production recall path, so the comparison set is chosen by the same
    hybrid retrieval and reranking the agent gets. `update_stats` stays off:
    this is a write-path check and must not bump recall counters or perturb the
    decay signal.
    """
    try:
        return recall_memory(
            es,
            query=text,
            user_id=user_id,
            memory_types=["semantic"],
            k=k,
            update_stats=False,
        )
    except Exception:  # noqa: BLE001
        # Dedup is a safety net, not a precondition. Losing it degrades to the
        # previous recency-window behaviour; failing the pass would discard
        # every fact in it.
        logger.warning("dedup: neighbour lookup failed for %s", user_id, exc_info=True)
        return []


_JUDGE_PROMPT = """You are deduplicating facts for a customer memory system.

For each numbered candidate below you are shown the existing stored facts that are closest to it in
meaning. Decide what should happen to the candidate.

- "duplicate": an existing fact already says this. Wording may differ; judge meaning.
- "update": the candidate CONTRADICTS or REPLACES an existing fact. The customer moved, upgraded,
  changed their mind, or reversed a preference. The old fact was true and now is not.
- "distinct": genuinely new information that does not duplicate or contradict anything shown.

Be careful with two cases:
- A candidate that adds detail to an existing fact without contradicting it is "distinct".
- A candidate about the same topic but a different subject is "distinct". "The customer's hub is
  offline" and "The customer's doorbell is offline" are different facts.

Return STRICT JSON, no commentary, no markdown fence:
{"verdicts": [{"n": 1, "decision": "duplicate|update|distinct", "existing_id": "<id or null>"}]}

Set existing_id to the id of the fact being duplicated or replaced. Null for "distinct".

%(blocks)s"""


def _render(candidate: dict[str, Any], neighbours: list[dict[str, Any]], n: int) -> str:
    lines = [f"CANDIDATE {n}: {candidate.get('text', '')}", "CLOSEST EXISTING FACTS:"]
    if not neighbours:
        lines.append("  (none)")
    for hit in neighbours:
        src = hit.get("source") or {}
        lines.append(f"  id={hit['id']} [{src.get('fact_type', 'fact')}] {src.get('text', '')}")
    return "\n".join(lines)


def _judge(
    pairs: list[tuple[int, dict[str, Any], list[dict[str, Any]]]],
    inference_id: str,
) -> dict[int, dict[str, Any]]:
    """One batched call covering every ambiguous candidate."""
    blocks = "\n\n".join(_render(c, nb, n) for n, c, nb in pairs)
    try:
        raw = complete_chat(
            inference_id=inference_id,
            messages=[{"role": "user", "content": _JUDGE_PROMPT % {"blocks": blocks}}],
            max_completion_tokens=1024,
        )
        text = raw.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?", "", text, count=1).strip()
            text = re.sub(r"```$", "", text, count=1).strip()
        parsed = json.loads(text)
    except Exception:  # noqa: BLE001
        # Undecided means keep. A missed duplicate is recoverable; discarding a
        # genuine fact because a judge call failed is not.
        logger.warning("dedup: judge call failed, keeping all candidates", exc_info=True)
        return {}
    out: dict[int, dict[str, Any]] = {}
    for v in parsed.get("verdicts") or []:
        try:
            out[int(v["n"])] = v
        except (KeyError, TypeError, ValueError):
            continue
    return out


def deduplicate(
    es: Elasticsearch,
    *,
    user_id: str,
    candidates: list[dict[str, Any]],
    inference_id: str = LLM_INFERENCE_ID_FAST,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Resolve candidates against their nearest existing facts.

    Returns (kept, dropped, linked). `linked` are candidates that were kept but
    had a supersedes_id attached because they contradict an existing fact the
    extractor did not notice.
    """
    if not candidates:
        return [], [], []

    kept: list[dict[str, Any]] = []
    dropped: list[dict[str, Any]] = []
    linked: list[dict[str, Any]] = []
    ambiguous: list[tuple[int, dict[str, Any], list[dict[str, Any]]]] = []

    for fact in candidates:
        text = (fact.get("text") or "").strip()
        if not text:
            continue

        neighbours = _neighbours(es, user_id, text)
        if not neighbours:
            kept.append(fact)
            continue

        # Near-identical text needs no judgment.
        twin = next(
            (h for h in neighbours
             if _similarity(text, (h.get("source") or {}).get("text") or "")
             >= DEDUP_CERTAIN_SIMILARITY),
            None,
        )
        if twin is not None:
            dropped.append({**fact, "_duplicate_of": twin["id"], "_reason": "near-identical"})
            continue

        ambiguous.append((len(ambiguous) + 1, fact, neighbours))

    if ambiguous:
        verdicts = _judge(ambiguous, inference_id)
        for n, fact, neighbours in ambiguous:
            verdict = verdicts.get(n) or {}
            decision = str(verdict.get("decision") or "distinct").lower()
            existing_id = verdict.get("existing_id")
            valid_ids = {h["id"] for h in neighbours}

            if decision == "duplicate" and existing_id in valid_ids:
                dropped.append({**fact, "_duplicate_of": existing_id, "_reason": "judged duplicate"})
                continue

            # Only attach a supersession the extractor missed, and only to a
            # neighbour we actually retrieved. A hallucinated id would silently
            # hide an unrelated fact from every future recall.
            if (
                decision == "update"
                and existing_id in valid_ids
                and not fact.get("supersedes_id")
            ):
                fact = {**fact, "supersedes_id": existing_id, "contradiction": "natural"}
                linked.append(fact)

            kept.append(fact)

    return kept, dropped, linked


__all__ = ["deduplicate"]
