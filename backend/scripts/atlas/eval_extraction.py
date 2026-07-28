"""Extraction-quality eval: does consolidation capture what was said?

`eval_recall.py` measures P(retrieved | written). It samples documents that are
already in the index, so a fact that was never extracted is never sampled and
never scored. This measures the other half, P(written | said), and the two
together are the system.

Design notes:

  * Extraction runs with `dry_run=True`, which returns candidates without
    writing anything. The corpus is never mutated by the measurement itself.
  * Setup does write (episodes, and pre-existing facts for the dedup and
    supersession scenarios), always under a dedicated user id that no demo path
    touches, always cleaned up in a `finally`.
  * Most assertions are deterministic. A judge is used only where the question
    is genuinely semantic. That keeps the eval cheap and free of judge variance
    on the cases that matter most.
  * Each scenario runs `--repeats` times, because LLM output is not
    deterministic and a single sample is not a measurement.

Usage:
  uv run python -m scripts.atlas.eval_extraction
  uv run python -m scripts.atlas.eval_extraction --repeats 5
  uv run python -m scripts.atlas.eval_extraction --only attribution_safety
  uv run python -m scripts.atlas.eval_extraction --comparable-only   # for A/B
"""

from __future__ import annotations

import argparse
import inspect
import json
import logging
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from app.atlas.consolidate import consolidate
from app.atlas.llm import complete_chat
from app.atlas.memory.constants import (
    INDEX_EPISODIC,
    INDEX_PROCEDURAL,
    INDEX_SEMANTIC,
    LLM_INFERENCE_ID_FAST,
)
from app.elasticsearch.client import get_es_client

from .extraction_scenarios import SCENARIOS, Scenario

logger = logging.getLogger(__name__)

# Dedicated and deliberately unlovely, so no demo path ever writes here and the
# retrieval benchmark's corpus is never perturbed by this one.
EVAL_USER = "__extraction_eval__"

REPORT_DIR = Path(__file__).resolve().parents[2] / "data" / "atlas_eval"

# Attribution safety gates at 100%: one leak is the memory-poisoning failure the
# design exists to prevent. The rest allow for LLM variance.
GATES = {
    "attribution": 1.00,
    "dedup": 0.80,
    "pending": 0.80,
    "dating": 0.80,
    "supersession": 0.80,
    "typing": 0.80,
    "recall": 0.70,
    "procedural": 0.60,
}


# ---------------------------------------------------------------------------
# judge
# ---------------------------------------------------------------------------

_JUDGE_PROMPT = """You are grading a memory system's fact extraction.

EXPECTED (the gist that should have been captured):
{gist}

EXTRACTED FACTS:
{facts}

Does any single extracted fact convey the expected gist? Wording will differ;
judge meaning, not phrasing. A fact that captures only part of the gist, or that
states something materially different, does NOT count.

Answer with exactly one word: YES or NO."""


def _judge(gist: str, facts: list[str]) -> bool:
    rendered = "\n".join(f"- {f}" for f in facts) or "(none)"
    try:
        out = complete_chat(
            inference_id=LLM_INFERENCE_ID_FAST,
            messages=[{"role": "user", "content": _JUDGE_PROMPT.format(gist=gist, facts=rendered)}],
            max_completion_tokens=8,
        )
    except Exception:  # noqa: BLE001
        logger.warning("judge call failed; scoring as miss", exc_info=True)
        return False
    return out.strip().upper().startswith("YES")


# ---------------------------------------------------------------------------
# fixture setup / teardown
# ---------------------------------------------------------------------------

def _wipe(es) -> None:
    for idx in (INDEX_EPISODIC, INDEX_SEMANTIC, INDEX_PROCEDURAL):
        try:
            es.delete_by_query(
                index=idx, body={"query": {"term": {"user_id": EVAL_USER}}},
                refresh=True, conflicts="proceed",
            )
        except Exception:  # noqa: BLE001
            logger.debug("wipe of %s failed", idx, exc_info=True)
    try:
        es.delete(index="atlas_memory_state", id=EVAL_USER, refresh=True)
    except Exception:  # noqa: BLE001
        pass


def _install(es, scenario: Scenario) -> None:
    """Write the scenario's episodes and any pre-existing facts.

    Episodes are indexed directly rather than through `write_memory` so their
    timestamps can be controlled and ordered. Setup is not the thing under test.
    """
    base = datetime.now(timezone.utc) - timedelta(minutes=10 * len(scenario.episodes))
    for i, text in enumerate(scenario.episodes):
        es.index(
            index=INDEX_EPISODIC,
            document={
                "user_id": EVAL_USER,
                "text": text,
                "role": "user",
                "event_type": "user_message",
                "timestamp": (base + timedelta(minutes=10 * i)).isoformat(),
                "metadata": {},
            },
            refresh=True,
        )
    now = datetime.now(timezone.utc).isoformat()
    for fact in scenario.existing_facts:
        es.index(
            index=INDEX_SEMANTIC,
            document={
                "user_id": EVAL_USER,
                "text": fact["text"],
                "fact_type": fact.get("fact_type", "identity"),
                "confidence": fact.get("confidence", 1.0),
                "created_at": now,
                "last_used_at": now,
                "use_count": 0,
                "source_episodes": [],
                "metadata": {},
                **({"pending_outcome": True} if fact.get("pending_outcome") else {}),
            },
            refresh=True,
        )


def _consolidate(es, scenario: Scenario) -> dict[str, Any]:
    """Call consolidation, adapting to whichever signature this revision has.

    The A/B against an older revision is the point of this indirection: earlier
    code has no `assistant_context` parameter, and passing it would raise rather
    than score.
    """
    kwargs: dict[str, Any] = {"user_id": EVAL_USER, "dry_run": True}
    params = inspect.signature(consolidate).parameters
    if scenario.assistant_context and "assistant_context" in params:
        kwargs["assistant_context"] = scenario.assistant_context
    return consolidate(es, **kwargs)


# ---------------------------------------------------------------------------
# run
# ---------------------------------------------------------------------------

def run(es, scenarios: list[Scenario], repeats: int) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for scenario in scenarios:
        passes, details = 0, []
        for attempt in range(repeats):
            _wipe(es)
            try:
                _install(es, scenario)
                out = _consolidate(es, scenario)
                ok, detail = scenario.expect(out, _judge)
            except Exception as exc:  # noqa: BLE001
                ok, detail = False, f"error: {type(exc).__name__}: {exc}"
                logger.debug("scenario %s attempt %d raised", scenario.key, attempt, exc_info=True)
            passes += int(ok)
            details.append(detail)
        rate = passes / repeats
        results.append({
            "key": scenario.key,
            "dimension": scenario.dimension,
            "comparable": scenario.comparable,
            "passes": passes,
            "repeats": repeats,
            "rate": rate,
            "details": details,
            "note": scenario.note,
        })
        mark = "PASS" if rate >= GATES.get(scenario.dimension, 0.8) else "FAIL"
        print(f"  {mark}  {scenario.key:24s} {passes}/{repeats}  [{scenario.dimension}]  {details[-1][:60]}")
    return results


def summarise(results: list[dict[str, Any]]) -> dict[str, Any]:
    by_dim: dict[str, list[float]] = defaultdict(list)
    for r in results:
        by_dim[r["dimension"]].append(r["rate"])
    dims = {d: round(sum(v) / len(v), 3) for d, v in by_dim.items()}
    overall = round(sum(r["rate"] for r in results) / len(results), 3) if results else 0.0
    return {"overall": overall, "by_dimension": dims}


def main() -> int:
    logging.basicConfig(level=logging.WARNING, format="%(message)s")
    p = argparse.ArgumentParser()
    p.add_argument("--repeats", type=int, default=3)
    p.add_argument("--only", help="run a single scenario by key")
    p.add_argument("--comparable-only", action="store_true",
                   help="only scenarios an older revision can also be scored on")
    p.add_argument("--label", default="", help="tag for the report filename")
    args = p.parse_args()

    scenarios = list(SCENARIOS)
    if args.only:
        scenarios = [s for s in scenarios if s.key == args.only]
    if args.comparable_only:
        scenarios = [s for s in scenarios if s.comparable]
    if not scenarios:
        print("no scenarios selected", file=sys.stderr)
        return 1

    es = get_es_client()
    print(f"Extraction eval: {len(scenarios)} scenarios x {args.repeats} repeats\n")
    try:
        results = run(es, scenarios, args.repeats)
    finally:
        _wipe(es)

    summary = summarise(results)
    print("\n=== by dimension ===")
    failed_gates = []
    for dim, rate in sorted(summary["by_dimension"].items()):
        gate = GATES.get(dim, 0.8)
        ok = rate >= gate
        if not ok:
            failed_gates.append((dim, rate, gate))
        print(f"  {'ok  ' if ok else 'FAIL'} {dim:14s} {rate:.2f}  (gate {gate:.2f})")
    print(f"\noverall: {summary['overall']:.3f}")

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    tag = f"-{args.label}" if args.label else ""
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORT_DIR / f"extraction_report-{ts}{tag}.json"
    path.write_text(json.dumps({"summary": summary, "results": results}, indent=2))
    print(f"report: {path}")

    if failed_gates:
        print("\nFAIL: " + ", ".join(f"{d}={r:.2f} < {g:.2f}" for d, r, g in failed_gates))
        return 2
    print("\nPASS: all dimension gates met")
    return 0


if __name__ == "__main__":
    sys.exit(main())
