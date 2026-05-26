"""Generate multi-month memory narratives for Atlas users via Claude (EIS).

Output: backend/data/atlas_seed/<user_id>.json with three lists of dicts
(episodic / semantic / procedural) ready for `bulk_seed.py` to index.

Cached on disk: a regenerate forces a re-run via `--force`. Otherwise an
existing file is reused so reseeds don't re-spend on EIS chat tokens.

Usage:
  uv run python -m scripts.atlas.deep_narratives                # all users
  uv run python -m scripts.atlas.deep_narratives --user sarah   # single user
  uv run python -m scripts.atlas.deep_narratives --force        # ignore cache
"""

from __future__ import annotations

import argparse
import json
import logging
import random
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.atlas.llm import complete_chat
from app.atlas.memory.constants import LLM_INFERENCE_ID_FAST

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "atlas_seed"

# Per-user generation budget: enough to cover ~12 months of weekly check-ins
# plus incidental events, without blowing up EIS spend. Generated in chunks
# so a single JSON syntax error from the model only loses one chunk, not
# the whole user.
EPISODIC_TARGET = 200
EPISODIC_CHUNK = 50            # ~6KB-8KB JSON output per call — well under any model limit
SEMANTIC_TARGET = 60
SEMANTIC_CHUNK = 30
PROCEDURAL_TARGET = 4
PROCEDURAL_CHUNK = 4

NOW = datetime.now(timezone.utc)


@dataclass
class Persona:
    user_id: str
    horizon_days: int          # how far back the narrative reaches
    seed: str                  # short identity blurb
    arc: str                   # multi-paragraph story arc the model expands

PERSONAS: dict[str, Persona] = {
    "sarah": Persona(
        user_id="sarah",
        horizon_days=540,
        seed=(
            "Sarah, mid-30s, lives in a Victorian flat in Bristol, UK with her partner and "
            "newborn son Theo. Border collie named Whiskey. Owns a Lumio Hub v2, several "
            "motion sensors, smart doorbell, smart bulbs. Heavy support engagement after "
            "the firmware 3.1.4 Zigbee regression in early 2026."
        ),
        arc=(
            "Cover roughly 18 months. Early period: install of Hub v2, gradual adoption, "
            "small everyday automations (porch light, kitchen scene). Mid period: pregnancy, "
            "moving the nursery, baby-related quiet hours, sleep-deprived support chats. "
            "Late period: firmware 3.1.4 regression, repeated Zigbee disconnects, factory "
            "resets, escalations, anticipation of 3.2.0. Tone shifts from playful to tired."
        ),
    ),
    "james": Persona(
        user_id="james",
        horizon_days=720,
        seed=(
            "James, 50s, Dutch, lives on a converted Dutch barge moored at Sixhaven in "
            "Amsterdam-Noord. Daughter Anouk (early 20s) visits weekends. Hub v1 owner, "
            "considering an upgrade. Power is shore-supply with brownouts. Casual user."
        ),
        arc=(
            "Cover roughly 24 months. Steady, slow-paced narrative — fewer incidents, more "
            "seasonal patterns (winter heating scenes, summer canal activity, spring tulip "
            "blinds). Mention shore-power cuts, the difficulty of getting an electrician "
            "to the moorings, language preference quirks, occasional 'is the Hub v2 worth "
            "it?' wavering."
        ),
    ),
    "priya": Persona(
        user_id="priya",
        horizon_days=900,
        seed=(
            "Priya, late 30s, residential architect in Bengaluru, India. Lives in a "
            "duplex in Indiranagar with her partner and indie dog Clio. Power user — "
            "uses the Lumio developer API, integrates with Revit BIM, has scenes for "
            "everything. Cares for her elderly mother across town."
        ),
        arc=(
            "Cover roughly 30 months. Power-user journey: early API experiments, scene "
            "sprawl, monsoon humidity quirks, monsoon power cuts handled by inverter, "
            "adding fall-detection at her mother's flat, conference talks where she "
            "mentions Lumio. Mention specific work projects (a residential bungalow, "
            "a co-living retrofit) without being too detailed."
        ),
    ),
}


EPISODIC_PROMPT = """<role>
You are populating a synthetic-but-realistic episodic memory store for a customer of Lumio, a smart-home company.
</role>

<output_format>
Output a STRICT JSON ARRAY only — no commentary, no markdown fence, no surrounding object:
[
  {"text": "...", "role": "user"|"assistant"|"system", "event_type": "user_message"|"agent_message"|"observation", "days_ago": <int>}
]
Every "text" value must be on a SINGLE LINE using straight ASCII quotes. No raw newlines or curly quotes inside strings.
</output_format>

<persona>
%(seed)s
</persona>

<story_arc>
%(arc)s
</story_arc>

<requirements>
- Produce exactly %(count)d episodic events.
- This is chunk %(chunk_index)d of %(chunks_total)d. Cover the time window roughly %(window_lo)d to %(window_hi)d days ago.
- 60-70%% should be customer messages ("role":"user"), rest agent replies or system observations.
- Text must sound like real chat snippets — short, natural, occasional typos. NO robotic phrasing.
- Cover a wide range of topics: device setup, daily routines, family, travel, weather, billing, app bugs, edge cases, hobbies, food, weekends.
- DO NOT mention firmware version 3.1.4, 3.2.0, or specific calendar dates — focus on lived experience.
</requirements>

Now produce the JSON array."""

SEMANTIC_PROMPT = """<role>
You are populating a semantic memory store with durable facts about a Lumio customer.
</role>

<output_format>
Output a STRICT JSON ARRAY only — no commentary, no markdown fence:
[
  {"text": "...", "fact_type": "preference"|"identity"|"constraint"|"world", "confidence": 0.6-1.0, "days_ago": <int>}
]
Every "text" value must be on a SINGLE LINE using straight ASCII quotes.
</output_format>

<persona>
%(seed)s
</persona>

<story_arc>
%(arc)s
</story_arc>

<requirements>
- Produce exactly %(count)d semantic facts (no duplicates, no paraphrases).
- Write in third-person.
- Mix all four fact_type values.
- DO NOT mention firmware version 3.1.4, 3.2.0, or specific calendar dates.
</requirements>

Now produce the JSON array."""

PROCEDURAL_PROMPT = """<role>
You are populating a procedural memory store with support playbooks tailored to a specific Lumio customer.
</role>

<output_format>
Output a STRICT JSON ARRAY only — no commentary, no markdown fence:
[
  {"name": "snake_case_id", "trigger_text": "...", "description": "...", "steps": [{"order": 1, "instruction": "...", "tool": "ask_user"|"recall_memory"|"escalate"}], "days_ago": <int>}
]
Every string must be on a single line using straight ASCII quotes.
</output_format>

<persona>
%(seed)s
</persona>

<requirements>
- Produce exactly %(count)d procedural playbooks tailored to THIS persona.
- 3-6 steps each.
</requirements>

Now produce the JSON array."""


def _call(prompt: str, max_tokens: int = 4500) -> str:
    return complete_chat(
        inference_id=LLM_INFERENCE_ID_FAST,
        messages=[{"role": "user", "content": prompt}],
        max_completion_tokens=max_tokens,
    )


def _generate_episodic(persona: Persona) -> list[dict]:
    chunks_total = (EPISODIC_TARGET + EPISODIC_CHUNK - 1) // EPISODIC_CHUNK
    out: list[dict] = []
    # Tile the time window across chunks so each chunk owns a slice of history.
    slice_size = persona.horizon_days // chunks_total
    for i in range(chunks_total):
        window_hi = persona.horizon_days - i * slice_size
        window_lo = max(0, window_hi - slice_size)
        prompt = EPISODIC_PROMPT % {
            "seed": persona.seed,
            "arc": persona.arc,
            "count": EPISODIC_CHUNK,
            "chunk_index": i + 1,
            "chunks_total": chunks_total,
            "window_lo": window_lo,
            "window_hi": window_hi,
        }
        try:
            arr = _parse_array(_call(prompt))
        except Exception as exc:
            print(f"    chunk {i+1}/{chunks_total} parse failure: {exc}; skipping")
            continue
        out.extend(arr)
    return out


def _generate_semantic(persona: Persona) -> list[dict]:
    chunks_total = (SEMANTIC_TARGET + SEMANTIC_CHUNK - 1) // SEMANTIC_CHUNK
    out: list[dict] = []
    for i in range(chunks_total):
        prompt = SEMANTIC_PROMPT % {
            "seed": persona.seed,
            "arc": persona.arc,
            "count": SEMANTIC_CHUNK,
        }
        try:
            arr = _parse_array(_call(prompt))
        except Exception as exc:
            print(f"    semantic chunk {i+1} parse failure: {exc}; skipping")
            continue
        out.extend(arr)
    return out


def _generate_procedural(persona: Persona) -> list[dict]:
    prompt = PROCEDURAL_PROMPT % {"seed": persona.seed, "count": PROCEDURAL_TARGET}
    try:
        return _parse_array(_call(prompt, max_tokens=3000))
    except Exception as exc:
        print(f"    procedural parse failure: {exc}; skipping")
        return []


def generate_for(persona: Persona, *, force: bool = False) -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    target = DATA_DIR / f"{persona.user_id}.json"
    if target.exists() and not force:
        print(f"  cached  {target.relative_to(DATA_DIR.parent.parent)}")
        return target

    print(f"  generating {persona.user_id}...")
    episodic = _generate_episodic(persona)
    print(f"    episodic: {len(episodic)}")
    semantic = _generate_semantic(persona)
    print(f"    semantic: {len(semantic)}")
    procedural = _generate_procedural(persona)
    print(f"    procedural: {len(procedural)}")

    payload = {
        "user_id": persona.user_id,
        "episodic": episodic,
        "semantic": semantic,
        "procedural": procedural,
    }
    target.write_text(json.dumps(payload, indent=2))
    print(f"  wrote   {target.relative_to(DATA_DIR.parent.parent)}")
    return target


def _parse_array(text: str) -> list[dict]:
    """Extract a JSON array from the model's response, recovering from common syntax slips."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text
        text = text.rsplit("```", 1)[0].strip()
        if text.startswith("json"):
            text = text[4:].strip()
    start = text.find("[")
    end = text.rfind("]")
    if start == -1 or end == -1:
        raise ValueError(f"no JSON array found: {text[:200]!r}")
    body = text[start:end + 1]
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        # Salvage: parse element-by-element, dropping anything malformed.
        data = _salvage_array(body)
    if not isinstance(data, list):
        raise ValueError("expected JSON array")
    return [d for d in data if isinstance(d, dict)]


def _salvage_array(body: str) -> list[dict]:
    """Best-effort element-wise parse for arrays of objects."""
    out: list[dict] = []
    depth = 0
    obj_start: int | None = None
    in_str = False
    escape = False
    for i, ch in enumerate(body):
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if ch == '"' and not escape:
            in_str = not in_str
            continue
        if in_str:
            continue
        if ch == "{":
            if depth == 0:
                obj_start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and obj_start is not None:
                snippet = body[obj_start:i + 1]
                try:
                    out.append(json.loads(snippet))
                except json.JSONDecodeError:
                    pass  # drop malformed object
                obj_start = None
    return out


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    p = argparse.ArgumentParser()
    p.add_argument("--user", choices=list(PERSONAS.keys()), help="generate one user only")
    p.add_argument("--force", action="store_true", help="ignore cache and regenerate")
    args = p.parse_args()

    targets = [PERSONAS[args.user]] if args.user else list(PERSONAS.values())

    print(f"Generating narratives for {len(targets)} user(s) -> {DATA_DIR}")
    random.seed(0xA71A5)  # for any future randomized post-processing
    for persona in targets:
        generate_for(persona, force=args.force)
    print("\nDone.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
