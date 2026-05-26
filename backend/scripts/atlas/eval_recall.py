"""Retrieval-quality eval for Atlas memory — QA-style passage retrieval.

For each persona, samples a fixed set of memory docs across the three
indices (episodic / semantic / procedural). For each sampled doc, an LLM
generates two natural questions a user might ask whose answer is that doc.
The eval then runs every question through `recall_memory` against the
owning persona's user_id and checks whether the source doc surfaces in the
top-k results — matched on the doc's Elasticsearch `_id`. Computes:

    Recall@1 / Recall@5 / Recall@10
    MRR (mean reciprocal rank, capped at k=10)

This is the methodology MS MARCO synthetic, BEIR passage retrieval, RAGAS,
and most production RAG eval reports use. Questions are aligned with the
target passage by construction but not token-for-token — the LLM
paraphrases naturally, the way a user would speak.

Question generation is cached on disk (qa_questions_cache.json) so re-runs
are deterministic against a fixed question set. Delete the cache to force
regeneration.

Also runs a tenant-isolation sweep: for a sample of QA pairs owned by user
A, issues the same question as user B and asserts no hit.

Output:
    backend/data/atlas_eval/qa_report-<ts>.md  (human-readable summary)
    backend/data/atlas_eval/qa_report-<ts>.json (raw per-query results)

Usage:
  uv run python -m scripts.atlas.eval_recall
  uv run python -m scripts.atlas.eval_recall --k 10 --user sarah
  uv run python -m scripts.atlas.eval_recall --regenerate-questions
"""

from __future__ import annotations

import argparse
import json
import logging
import random
import re
import sys
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.atlas.llm import complete_chat
from app.atlas.memory.constants import (
    INDEX_EPISODIC,
    INDEX_PROCEDURAL,
    INDEX_SEMANTIC,
    LLM_INFERENCE_ID_FAST,
)
from app.atlas.memory.operations import recall_memory
from app.elasticsearch.client import get_es_client

from .deep_narratives import PERSONAS

logger = logging.getLogger(__name__)

REPORT_DIR = Path(__file__).resolve().parents[2] / "data" / "atlas_eval"
CACHE_PATH = REPORT_DIR / "qa_questions_cache.json"

# Pass criteria. QA-style queries are aligned with passages by construction,
# so the bar is higher than for the previous paraphrase-needle methodology.
# These gates leave margin against future regressions (corpus reindex, model
# swap, reranker change), not against run-to-run noise. Measured baseline
# is R@10 = 0.89, gated 4 points below.
TARGET_RECALL_AT_10 = 0.85
TARGET_RECALL_AT_5 = 0.75

# Per-persona, per-memory-type sample sizes. Capped so question generation
# stays cheap (~$0.05 of EIS spend) and the eval finishes in ~3 min.
SAMPLE_SIZES = {
    "semantic": 15,
    "episodic": 10,
    "procedural": 3,
}
QUESTIONS_PER_DOC = 2

# Seed for deterministic doc sampling. Question generation itself uses
# whatever non-determinism the LLM has, but the cache pins the output.
SAMPLE_SEED = 42


@dataclass
class QAPair:
    user_id: str
    doc_id: str
    memory_type: str
    doc_text: str
    questions: list[str] = field(default_factory=list)


@dataclass
class QueryResult:
    user_id: str
    doc_id: str
    memory_type: str
    question: str
    rank: int | None  # 1-indexed rank of the doc, or None if missed
    top_hit_doc_id: str | None
    top_hit_text: str | None


# ---------------------------------------------------------------------------
# Doc sampling
# ---------------------------------------------------------------------------

def _doc_text(memory_type: str, source: dict[str, Any]) -> str:
    """Render a doc's primary text for the LLM prompt."""
    if memory_type == "procedural":
        parts = [
            source.get("name") or "",
            source.get("description") or "",
            source.get("trigger_text") or "",
        ]
        steps = source.get("steps") or []
        if steps:
            step_texts = []
            for s in steps:
                if isinstance(s, dict):
                    step_texts.append(s.get("text") or s.get("description") or "")
                else:
                    step_texts.append(str(s))
            if step_texts:
                parts.append("Steps: " + "; ".join(t for t in step_texts if t))
        return "\n".join(p for p in parts if p).strip()
    return (source.get("text") or "").strip()


def _sample_docs(es, user_id: str, memory_type: str, index: str, n: int) -> list[dict[str, Any]]:
    """Pull up to `n` docs for a user/index, deterministically.

    Filters out superseded semantic facts (recall would never return them
    anyway, so they'd be guaranteed misses and skew the eval).
    """
    must_not: list[dict[str, Any]] = []
    if memory_type == "semantic":
        must_not.append({"exists": {"field": "superseded_by"}})

    body: dict[str, Any] = {
        "size": 1000,  # over-fetch; we sample client-side for determinism
        "_source": {"excludes": ["semantic_content"]},
        "query": {
            "bool": {
                "filter": [{"term": {"user_id": user_id}}],
                **({"must_not": must_not} if must_not else {}),
            }
        },
    }
    resp = es.search(index=index, body=body, ignore_unavailable=True)
    hits = resp["hits"]["hits"]
    docs = []
    for h in hits:
        text = _doc_text(memory_type, h.get("_source", {}))
        if not text or len(text) < 20:
            continue  # skip docs too thin to derive a sensible question
        docs.append({"id": h["_id"], "source": h["_source"], "text": text})
    # Sort client-side by id for deterministic sampling (ES disallows _id field sort).
    docs.sort(key=lambda d: d["id"])
    if len(docs) <= n:
        return docs
    rng = random.Random(SAMPLE_SEED + hash(user_id + memory_type) % (2**32))
    return rng.sample(docs, n)


# ---------------------------------------------------------------------------
# Question generation (cached)
# ---------------------------------------------------------------------------

QUESTION_PROMPT = """You are generating evaluation queries for a personal-assistant memory system.

Below is a piece of memory the assistant has stored about a user named {first_name}. Generate exactly {n} natural questions {first_name} (or someone speaking on {first_name}'s behalf) might plausibly ask their assistant whose answer relies on this memory.

Rules:
- Ask the question naturally — the way a person speaks to an assistant. No "according to the memory" framing.
- Paraphrase. Do NOT quote phrases from the memory verbatim. Use different vocabulary where possible.
- Each question must have a SPECIFIC answer that requires this memory. Avoid generic questions like "what do you know about me?".
- Make the questions varied — different angles, not two phrasings of the same query.
- Output ONLY a JSON array of {n} strings. No commentary, no markdown fences.

Memory ({memory_type}):
{doc_text}

JSON array of {n} questions:"""


def _generate_questions(memory_type: str, doc_text: str, first_name: str, n: int) -> list[str]:
    """Call the LLM to produce n natural questions for one doc."""
    prompt = QUESTION_PROMPT.format(
        first_name=first_name,
        n=n,
        memory_type=memory_type,
        doc_text=doc_text,
    )
    raw = complete_chat(
        inference_id=LLM_INFERENCE_ID_FAST,
        messages=[{"role": "user", "content": prompt}],
        max_completion_tokens=512,
    )
    # Strip code fences if the model added them.
    cleaned = raw.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        questions = json.loads(cleaned)
    except json.JSONDecodeError:
        # Fallback: extract a JSON array via regex.
        m = re.search(r"\[(?:[^\[\]]|\[[^\]]*\])*\]", cleaned, re.DOTALL)
        if not m:
            logger.warning("could not parse questions from LLM output: %r", raw[:200])
            return []
        try:
            questions = json.loads(m.group(0))
        except json.JSONDecodeError:
            logger.warning("could not parse questions from LLM output: %r", raw[:200])
            return []
    if not isinstance(questions, list):
        return []
    return [str(q).strip() for q in questions if str(q).strip()][:n]


def _first_name(persona_key: str) -> str:
    """Capitalize the persona key (sarah → Sarah, james → James, priya → Priya)."""
    return persona_key.capitalize()


def _build_qa_pairs(es, personas: list[str], regenerate: bool) -> list[QAPair]:
    """Build (or reload) QA pairs across all personas. Caches to CACHE_PATH."""
    cache: dict[str, Any] = {}
    if CACHE_PATH.exists() and not regenerate:
        try:
            cache = json.loads(CACHE_PATH.read_text())
        except json.JSONDecodeError:
            logger.warning("question cache %s is corrupt — regenerating", CACHE_PATH)
            cache = {}

    pairs: list[QAPair] = []
    cache_dirty = False

    for persona in personas:
        first_name = _first_name(persona)
        persona_cache = cache.setdefault(persona, {})

        for memory_type, index in [
            ("semantic", INDEX_SEMANTIC),
            ("episodic", INDEX_EPISODIC),
            ("procedural", INDEX_PROCEDURAL),
        ]:
            n_docs = SAMPLE_SIZES[memory_type]
            sampled = _sample_docs(es, persona, memory_type, index, n_docs)
            for doc in sampled:
                doc_id = doc["id"]
                cached = persona_cache.get(doc_id)
                if cached and cached.get("questions"):
                    questions = cached["questions"]
                else:
                    questions = _generate_questions(
                        memory_type=memory_type,
                        doc_text=doc["text"],
                        first_name=first_name,
                        n=QUESTIONS_PER_DOC,
                    )
                    if not questions:
                        continue
                    persona_cache[doc_id] = {
                        "memory_type": memory_type,
                        "doc_text": doc["text"],
                        "questions": questions,
                    }
                    cache_dirty = True
                    print(f"  generated {len(questions)} questions for {persona}/{doc_id[:8]} ({memory_type})")
                pairs.append(
                    QAPair(
                        user_id=persona,
                        doc_id=doc_id,
                        memory_type=memory_type,
                        doc_text=doc["text"],
                        questions=questions,
                    )
                )

    if cache_dirty:
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        CACHE_PATH.write_text(json.dumps(cache, indent=2))
        print(f"  cached question set written to {CACHE_PATH}")

    return pairs


# ---------------------------------------------------------------------------
# Eval phase
# ---------------------------------------------------------------------------

def _hit_rank(hits: list[dict[str, Any]], doc_id: str) -> int | None:
    for i, h in enumerate(hits, start=1):
        if h.get("id") == doc_id:
            return i
    return None


def _eval_pairs(
    es, pairs: list[QAPair], k: int,
    text_leg: bool = True, semantic_leg: bool = True, rerank: bool = True,
) -> list[QueryResult]:
    out: list[QueryResult] = []
    for pair in pairs:
        for question in pair.questions:
            hits = recall_memory(
                es,
                query=question,
                user_id=pair.user_id,
                memory_types=None,  # search all three indices
                k=k,
                include_catalog=False,
                text_leg=text_leg,
                semantic_leg=semantic_leg,
                rerank=rerank,
            )
            rank = _hit_rank(hits, pair.doc_id)
            top = hits[0] if hits else None
            top_source = (top.get("source") or {}) if top else {}
            top_text = (
                top_source.get("text")
                or top_source.get("trigger_text")
                or top_source.get("name")
                or top_source.get("description")
                or ""
            )
            out.append(
                QueryResult(
                    user_id=pair.user_id,
                    doc_id=pair.doc_id,
                    memory_type=pair.memory_type,
                    question=question,
                    rank=rank,
                    top_hit_doc_id=top.get("id") if top else None,
                    top_hit_text=top_text,
                )
            )
    return out


def _isolation_sweep(
    es, pairs: list[QAPair], k: int,
    text_leg: bool = True, semantic_leg: bool = True, rerank: bool = True,
) -> dict[str, Any]:
    """For each QA pair, run its first question as a DIFFERENT user. Any hit is a leak."""
    user_ids = list(PERSONAS.keys())
    leaks: list[dict[str, Any]] = []
    checked = 0
    # Sample one question per (owner, memory_type) to keep the sweep cheap.
    seen_keys = set()
    sampled_pairs: list[QAPair] = []
    for p in pairs:
        key = (p.user_id, p.memory_type)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        sampled_pairs.append(p)

    for pair in sampled_pairs:
        if not pair.questions:
            continue
        question = pair.questions[0]
        for uid in user_ids:
            if uid == pair.user_id:
                continue
            checked += 1
            hits = recall_memory(
                es, query=question, user_id=uid, k=k, include_catalog=False,
                text_leg=text_leg, semantic_leg=semantic_leg, rerank=rerank,
            )
            rank = _hit_rank(hits, pair.doc_id)
            if rank is not None:
                leaks.append({
                    "doc_id": pair.doc_id,
                    "owner": pair.user_id,
                    "queried_as": uid,
                    "rank": rank,
                    "question": question,
                })
    return {"checked": checked, "leaks": leaks}


def _summarize(results: list[QueryResult], k: int) -> dict[str, Any]:
    by_user: dict[str, list[QueryResult]] = defaultdict(list)
    by_type: dict[str, list[QueryResult]] = defaultdict(list)
    for r in results:
        by_user[r.user_id].append(r)
        by_type[r.memory_type].append(r)

    def metrics(rs: list[QueryResult]) -> dict[str, float]:
        if not rs:
            return {"queries": 0}
        n = len(rs)
        r1 = sum(1 for r in rs if r.rank == 1) / n
        r5 = sum(1 for r in rs if r.rank is not None and r.rank <= 5) / n
        rk = sum(1 for r in rs if r.rank is not None and r.rank <= k) / n
        mrr = sum(1.0 / r.rank for r in rs if r.rank is not None) / n
        return {
            "queries": n,
            "recall@1": round(r1, 3),
            "recall@5": round(r5, 3),
            f"recall@{k}": round(rk, 3),
            "mrr": round(mrr, 3),
        }

    return {
        "overall": metrics(results),
        "by_user": {uid: metrics(rs) for uid, rs in by_user.items()},
        "by_memory_type": {mt: metrics(rs) for mt, rs in by_type.items()},
    }


def _metrics_table(m: dict[str, Any]) -> str:
    if not m or m.get("queries") == 0:
        return "_no queries_"
    keys = [k for k in m.keys() if k != "queries"]
    head = "| " + " | ".join(["queries"] + keys) + " |"
    sep = "|" + "|".join(["---"] * (len(keys) + 1)) + "|"
    row = "| " + " | ".join([str(m["queries"])] + [str(m[k]) for k in keys]) + " |"
    return "\n".join([head, sep, row])


def _write_report(
    summary: dict[str, Any],
    isolation: dict[str, Any],
    results: list[QueryResult],
    k: int,
    ts: str,
) -> tuple[Path, Path]:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    md_path = REPORT_DIR / f"qa_report-{ts}.md"
    json_path = REPORT_DIR / f"qa_report-{ts}.json"

    json_path.write_text(json.dumps({
        "k": k,
        "summary": summary,
        "isolation": isolation,
        "results": [asdict(r) for r in results],
    }, indent=2))

    misses = [r for r in results if r.rank is None]

    lines: list[str] = []
    lines.append(f"# Atlas QA-Style Recall Eval — {ts}\n")
    lines.append(
        "Methodology: for each sampled memory doc, an LLM generated natural "
        "questions whose answer is that doc. The retriever has to surface "
        "the source doc in top-k against those questions. Aligned with the "
        "MS MARCO / BEIR / RAGAS convention.\n"
    )
    lines.append(f"k = {k}, total queries = {len(results)}\n")
    lines.append("\n## Overall\n")
    lines.append(_metrics_table(summary["overall"]))
    lines.append("\n## Per user\n")
    for uid, m in summary["by_user"].items():
        lines.append(f"\n### {uid}\n")
        lines.append(_metrics_table(m))
    lines.append("\n## Per memory type\n")
    for mt, m in summary["by_memory_type"].items():
        lines.append(f"\n### {mt}\n")
        lines.append(_metrics_table(m))

    lines.append("\n## Tenant isolation\n")
    lines.append(f"- cross-user queries checked: {isolation['checked']}")
    lines.append(f"- leaks detected: {len(isolation['leaks'])}")
    if isolation["leaks"]:
        lines.append("\n```json")
        lines.append(json.dumps(isolation["leaks"][:10], indent=2))
        lines.append("```")

    lines.append(f"\n## Misses ({len(misses)})\n")
    if not misses:
        lines.append("_None — every doc was retrieved within top-k._")
    else:
        for m in misses[:30]:
            top = (m.top_hit_text or "")[:120].replace("\n", " ")
            lines.append(
                f"- **{m.doc_id[:8]}** ({m.user_id}, {m.memory_type})\n"
                f"  - question: _{m.question}_\n"
                f"  - top hit: _{top}_"
            )
        if len(misses) > 30:
            lines.append(f"\n_(+{len(misses) - 30} more in JSON report)_")

    md_path.write_text("\n".join(lines) + "\n")
    return md_path, json_path


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    p = argparse.ArgumentParser()
    p.add_argument("--k", type=int, default=10)
    p.add_argument("--user", choices=list(PERSONAS.keys()))
    p.add_argument("--no-bm25", action="store_true",
                   help="Disable the BM25 (text) leg of the hybrid retriever (ablation)")
    p.add_argument("--no-semantic", action="store_true",
                   help="Disable the Jina v5 semantic leg of the hybrid retriever (ablation)")
    p.add_argument("--no-rerank", action="store_true",
                   help="Disable the cross-encoder reranker (ablation)")
    p.add_argument("--regenerate-questions", action="store_true",
                   help="Force regenerate the QA question cache (otherwise reused from disk)")
    args = p.parse_args()

    text_leg = not args.no_bm25
    semantic_leg = not args.no_semantic
    rerank = not args.no_rerank
    if not (text_leg or semantic_leg):
        print("ERROR: cannot disable both legs", file=sys.stderr)
        return 1

    es = get_es_client()
    personas = [args.user] if args.user else list(PERSONAS.keys())

    print(f"Building QA pairs for personas: {', '.join(personas)}")
    pairs = _build_qa_pairs(es, personas, regenerate=args.regenerate_questions)
    total_queries = sum(len(p.questions) for p in pairs)

    legs_label = f"text={text_leg} semantic={semantic_leg} rerank={rerank}"
    print(f"Evaluating {len(pairs)} docs across {total_queries} questions (k={args.k}, {legs_label})...")
    results = _eval_pairs(es, pairs, k=args.k, text_leg=text_leg, semantic_leg=semantic_leg, rerank=rerank)
    summary = _summarize(results, k=args.k)

    print("Running tenant-isolation sweep...")
    isolation = _isolation_sweep(es, pairs, k=args.k, text_leg=text_leg, semantic_leg=semantic_leg, rerank=rerank)

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    if not text_leg:
        ts = f"{ts}-nobm25"
    elif not semantic_leg:
        ts = f"{ts}-nosemantic"
    elif not rerank:
        ts = f"{ts}-norerank"
    md_path, json_path = _write_report(summary, isolation, results, k=args.k, ts=ts)

    print("\n=== Summary ===")
    print(json.dumps(summary, indent=2))
    print(f"\nIsolation: checked={isolation['checked']} leaks={len(isolation['leaks'])}")
    print(f"\nReport: {md_path}")
    print(f"Raw:    {json_path}")

    if isolation["leaks"]:
        print(f"\nFAIL: tenant isolation leaks detected ({len(isolation['leaks'])})")
        return 2
    overall = summary["overall"]
    r_at_10 = overall.get("recall@10") or overall.get(f"recall@{args.k}", 0)
    r_at_5 = overall.get("recall@5", 0)
    if r_at_10 < TARGET_RECALL_AT_10:
        print(f"\nFAIL: recall@10={r_at_10:.3f} < target {TARGET_RECALL_AT_10}")
        return 3
    if r_at_5 < TARGET_RECALL_AT_5:
        print(f"\nFAIL: recall@5={r_at_5:.3f} < target {TARGET_RECALL_AT_5}")
        return 4
    print(f"\nPASS: recall@10={r_at_10:.3f} >= {TARGET_RECALL_AT_10}, "
          f"recall@5={r_at_5:.3f} >= {TARGET_RECALL_AT_5}, "
          f"isolation leaks=0")
    return 0


if __name__ == "__main__":
    sys.exit(main())
