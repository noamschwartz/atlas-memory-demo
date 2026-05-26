"""Ground-truth needle memories + paraphrased queries for retrieval eval.

Each needle is a memory document the eval expects to find via hybrid recall.
The `queries` list contains paraphrases that should retrieve the needle —
none of them quote the needle's distinctive terms verbatim, so passing the
eval requires the embedding leg of RRF to actually be earning its keep.

The needles live in this file (not in the LLM-generated narrative) so the
ground truth is stable across regenerations. They get bulk-indexed alongside
the generated story and surfaced with a `metadata.needle_id` tag so the eval
can match on it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


MemoryType = Literal["episodic", "semantic", "procedural"]


@dataclass
class Needle:
    needle_id: str
    user_id: str
    memory_type: MemoryType
    text: str
    queries: list[str]
    fact_type: str | None = None
    confidence: float = 0.95
    name: str | None = None
    description: str | None = None
    steps: list[dict] = field(default_factory=list)
    # Approximate age in days from "now" — used to spread timestamps across
    # the user's history so old needles must be retrieved over fresh noise.
    age_days: int = 90


SARAH_NEEDLES: list[Needle] = [
    Needle(
        needle_id="sarah-dog-whiskey",
        user_id="sarah",
        memory_type="semantic",
        fact_type="constraint",
        text="Sarah mounts all motion sensors at 2.1 metres because her border collie Whiskey chews any cabling within reach.",
        queries=[
            "Why are her sensors mounted so high?",
            "Anything about a pet at home that affects the install?",
            "Has she had cable damage issues?",
            "Is there a reason she avoids ground-level installs?",
        ],
        age_days=210,
    ),
    Needle(
        needle_id="sarah-newborn-may",
        user_id="sarah",
        memory_type="episodic",
        text="Sarah told the agent she had a baby boy in May 2025 named Theo, and asked about disabling the doorbell chime during nap windows from 12:30 to 14:00.",
        queries=[
            "Did she ever mention quiet hours during the day?",
            "Anything about a child or infant in the house?",
            "Why does she care about the doorbell chime schedule?",
        ],
        age_days=365,
    ),
    Needle(
        needle_id="sarah-vacation-rental",
        user_id="sarah",
        memory_type="episodic",
        text="In August 2025 Sarah set up a guest profile for her sister staying at her flat in Cornwall while Sarah was in Greece — the guest profile only had access to lights and the front-door lock.",
        queries=[
            "Has she used guest access before?",
            "What's her pattern when she's travelling?",
            "Anything about a relative being given limited home access?",
        ],
        age_days=275,
    ),
    Needle(
        needle_id="sarah-hub-3.1.4-regression",
        user_id="sarah",
        memory_type="semantic",
        fact_type="world",
        text="Sarah's Zigbee disconnects all started after the firmware 3.1.4 auto-update on 14 January 2026; rolling back wasn't possible because Lumio disabled downgrades.",
        queries=[
            "When exactly did her connectivity issues start?",
            "Was a software update involved in her current trouble?",
            "Could she go back to an older firmware?",
        ],
        age_days=110,
    ),
    Needle(
        needle_id="sarah-allergic-pvc",
        user_id="sarah",
        memory_type="semantic",
        fact_type="constraint",
        text="Sarah has a contact allergy to PVC and asks for nylon-jacketed cables on every install.",
        queries=[
            "Is there a material she can't have in the house?",
            "Anything about cable jacket preferences?",
            "Any sensitivities or allergies to remember?",
        ],
        age_days=540,
    ),
    Needle(
        needle_id="sarah-payment-gocardless",
        user_id="sarah",
        memory_type="semantic",
        fact_type="preference",
        text="Sarah pays her Lumio Pro subscription via GoCardless direct debit and once asked support not to switch her to card-on-file.",
        queries=[
            "How does she pay for the service?",
            "Has she expressed a preference about billing method?",
        ],
        age_days=300,
    ),
    Needle(
        needle_id="sarah-bedroom-sensor-spring",
        user_id="sarah",
        memory_type="episodic",
        text="In April 2025 the bedroom motion sensor was reading false-positive triggers every night around 3am; the issue turned out to be sunrise reflecting off her wardrobe mirror, fixed by repositioning.",
        queries=[
            "Remember the bedroom sensor issue from last spring?",
            "Was there ever a problem with night-time false alarms?",
            "Any ghost detections she's complained about?",
        ],
        age_days=400,
    ),
    Needle(
        needle_id="sarah-procedural-reflection",
        user_id="sarah",
        memory_type="procedural",
        name="diagnose_false_positive_motion",
        text="Procedure for diagnosing a motion sensor that triggers without a real cause.",
        description="Run when a customer reports phantom motion alerts on a Lumio sensor.",
        steps=[
            {"order": 1, "instruction": "Ask whether the trigger is at a consistent time of day — points at sunlight or HVAC cycles", "tool": "ask_user"},
            {"order": 2, "instruction": "Check for reflective surfaces (mirrors, glass, polished floors) within sensor cone", "tool": "ask_user"},
            {"order": 3, "instruction": "Lower sensitivity from default 80 to 60 in the app", "tool": "ask_user"},
            {"order": 4, "instruction": "If still triggering, swap to PIR-only mode (no microwave Doppler) in advanced settings", "tool": "ask_user"},
        ],
        queries=[
            "Is there a known playbook for ghost motion alerts?",
            "How do we troubleshoot phantom triggers?",
        ],
        age_days=395,
    ),
]


JAMES_NEEDLES: list[Needle] = [
    Needle(
        needle_id="james-tulip-allergy",
        user_id="james",
        memory_type="semantic",
        fact_type="constraint",
        text="James is allergic to tulip pollen, so his smart blinds in the conservatory are scheduled to close every weekday morning during March and April.",
        queries=[
            "Why are his blinds on a seasonal schedule?",
            "Any pollen-related automations?",
            "What allergies does he manage with the system?",
        ],
        age_days=420,
    ),
    Needle(
        needle_id="james-houseboat",
        user_id="james",
        memory_type="semantic",
        fact_type="identity",
        text="James lives on a converted Dutch barge moored at Sixhaven in Amsterdam-Noord — power is via shore-supply with frequent brownouts.",
        queries=[
            "Where exactly does he live?",
            "Anything unusual about his electrical supply?",
            "Why might his hub be losing power?",
        ],
        age_days=600,
    ),
    Needle(
        needle_id="james-color-bulb-disappointment",
        user_id="james",
        memory_type="episodic",
        text="James was disappointed that the colour bulbs he bought as a birthday gift for his daughter Anouk only worked in white on his Hub v1.",
        queries=[
            "Did anyone in his family receive a Lumio gift?",
            "Has he had a frustrating purchase experience?",
            "What's the story behind his interest in upgrading the hub?",
        ],
        age_days=180,
    ),
    Needle(
        needle_id="james-dutch-language",
        user_id="james",
        memory_type="semantic",
        fact_type="preference",
        text="James prefers the Lumio app in Dutch (nl-NL) but receives email notifications in English because of a known l10n bug on his account.",
        queries=[
            "What language does he use the app in?",
            "Anything about his locale preferences?",
            "Are his notifications in the wrong language?",
        ],
        age_days=500,
    ),
    Needle(
        needle_id="james-shore-power-outage",
        user_id="james",
        memory_type="episodic",
        text="In November 2025 the Sixhaven harbour had a 6-hour shore-power outage and James asked how to add a UPS to keep the hub online during winter cuts.",
        queries=[
            "Has he asked about backup power?",
            "Did he ever lose power for an extended period?",
            "Is he prepared for blackouts?",
        ],
        age_days=180,
    ),
    Needle(
        needle_id="james-procedural-marine",
        user_id="james",
        memory_type="procedural",
        name="marine_environment_install_check",
        text="Procedure for installing Lumio devices in marine or salt-air environments.",
        description="Apply this checklist when the customer's home is on water, near coast, or in a humid environment.",
        steps=[
            {"order": 1, "instruction": "Confirm the hub is mounted at least 1m above floor and away from condensation paths", "tool": "ask_user"},
            {"order": 2, "instruction": "Recommend silicone-sealed wall sensors (model -M variant) instead of standard", "tool": "recall_memory"},
            {"order": 3, "instruction": "Set firmware update window to 03:00 local to avoid shore-power peak loss windows", "tool": "ask_user"},
        ],
        queries=[
            "Is there special guidance for boats or coastal homes?",
            "What should we check for marine installs?",
        ],
        age_days=365,
    ),
]


PRIYA_NEEDLES: list[Needle] = [
    Needle(
        needle_id="priya-architect",
        user_id="priya",
        memory_type="semantic",
        fact_type="identity",
        text="Priya is a residential architect in Bengaluru and uses Lumio's developer API to integrate rooms with her clients' BIM models in Revit.",
        queries=[
            "What does she do for a living?",
            "Does she use any advanced integrations?",
            "Has she touched the developer API?",
        ],
        age_days=720,
    ),
    Needle(
        needle_id="priya-tea-routine",
        user_id="priya",
        memory_type="semantic",
        fact_type="preference",
        text="Priya has a 'morning tea' scene that warms the kitchen lights to 2700K, raises the blinds 40%, and starts the kettle via a Matter bridge at 06:15 on weekdays.",
        queries=[
            "What does her morning routine look like?",
            "Any scenes tied to a specific time of day?",
            "Is there a kettle automation in her setup?",
        ],
        age_days=300,
    ),
    Needle(
        needle_id="priya-elderly-mother",
        user_id="priya",
        memory_type="episodic",
        text="In June 2025 Priya added fall-detection sensors to her mother's flat across town and asked if Lumio's geofence could trigger an alert to her own phone if her mother left after sunset.",
        queries=[
            "Has she set up monitoring for a family member?",
            "Anything about elder care in her account?",
            "Did she ever ask about geofence-triggered alerts?",
        ],
        age_days=330,
    ),
    Needle(
        needle_id="priya-monsoon-humidity",
        user_id="priya",
        memory_type="semantic",
        fact_type="constraint",
        text="During Bengaluru's monsoon (June-September) Priya's Hub v2 humidity sensor reads 80–95% RH; she's asked support not to flag this as a fault.",
        queries=[
            "What's the deal with her high humidity readings?",
            "Has she pushed back on a sensor warning?",
            "Any seasonal weirdness in her telemetry?",
        ],
        age_days=240,
    ),
    Needle(
        needle_id="priya-clio-dog",
        user_id="priya",
        memory_type="episodic",
        text="Priya's indie dog Clio sets off the kitchen motion sensor whenever she jumps on the counter chasing crows — Priya disabled the kitchen sensor's daytime triggers.",
        queries=[
            "Does she have pets?",
            "Why is the kitchen sensor only active at night?",
            "Any crow-related stories in her memory?",
        ],
        age_days=150,
    ),
    Needle(
        needle_id="priya-power-cut-inverter",
        user_id="priya",
        memory_type="semantic",
        fact_type="world",
        text="Priya's house has a 5kVA Su-Kam inverter that kicks in within 200ms during BESCOM outages; the hub has never lost power even during 4-hour cuts.",
        queries=[
            "How does her place handle power cuts?",
            "Is her hub on backup power?",
            "Anything about an inverter on her circuit?",
        ],
        age_days=550,
    ),
    Needle(
        needle_id="priya-procedural-revit",
        user_id="priya",
        memory_type="procedural",
        name="export_room_topology_to_revit",
        text="Procedure for exporting Lumio room topology to a Revit BIM model.",
        description="Triggered when a customer (typically architect/designer) asks to import the home graph into design software.",
        steps=[
            {"order": 1, "instruction": "Generate a developer API token with rooms:read scope", "tool": "ask_user"},
            {"order": 2, "instruction": "Call /v3/topology?format=ifc to fetch the IFC export", "tool": "ask_user"},
            {"order": 3, "instruction": "In Revit, use the Lumio plug-in (≥ 2024.2) to import the IFC under a linked file", "tool": "ask_user"},
        ],
        queries=[
            "Is there a workflow for getting the home into BIM tools?",
            "How do architects pull data out of Lumio?",
        ],
        age_days=480,
    ),
]


ALL_NEEDLES: list[Needle] = SARAH_NEEDLES + JAMES_NEEDLES + PRIYA_NEEDLES


def needles_for(user_id: str) -> list[Needle]:
    return [n for n in ALL_NEEDLES if n.user_id == user_id]


__all__ = [
    "ALL_NEEDLES",
    "JAMES_NEEDLES",
    "Needle",
    "PRIYA_NEEDLES",
    "SARAH_NEEDLES",
    "needles_for",
]
