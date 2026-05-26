"""Seed sample memories for two Lumio support customers.

Idempotent: clears any prior `sarah` / `james` docs from the three indices
before re-seeding.

Usage: uv run python -m scripts.atlas.seed_memories
"""

from __future__ import annotations

import sys

from app.elasticsearch.client import get_es_client
from app.atlas.memory.constants import MEMORY_INDICES
from app.atlas.memory.operations import write_memory

SEED_USERS = ["sarah", "james"]

# Sarah: Hub v2 owner, recurring Zigbee drops. Events 1,3,4 cluster on connectivity.
SARAH_EPISODIC = [
    "Hi, I'm Sarah. My Lumio Hub v2 keeps disconnecting randomly — sensors go offline for a few minutes then reconnect.",
    "I have 3 Lumio Motion Sensor Pro units and the smart doorbell all paired to the hub.",
    "I moved the hub centrally like support suggested, but the Zigbee drops are still happening daily.",
    "My hub was factory reset in March 2026. The drops stopped for two weeks, then came right back — same issue.",
    "I just added 2 Lumio Smart Bulbs to the bedroom. They show up but only in warm white, not the colors the app shows.",
    "I'm on iOS 17.4 and keep getting stuck on the login screen — have to force-close the app every time.",
]
SARAH_SEMANTIC = [
    ("Sarah owns a Lumio Hub v2.", "identity", 1.0),
    ("Sarah experiences recurring Zigbee connectivity drops, primarily affecting the smart doorbell.", "constraint", 0.95),
    ("Sarah has 3 Lumio Motion Sensor Pro units and a smart doorbell paired to her Hub v2.", "identity", 1.0),
    ("Sarah's Hub v2 was factory reset in March 2026 as a connectivity troubleshooting step.", "identity", 0.9),
    ("Sarah recently added 2 Lumio Smart Bulbs to her bedroom and is not seeing full color.", "identity", 0.85),
    ("Sarah is on iOS 17.4 and experiences the app login loop issue.", "constraint", 0.9),
]
SARAH_PROCEDURAL = [
    {
        "name": "troubleshoot_zigbee_connectivity",
        "trigger": "Customer reports Zigbee device disconnects or hub going offline",
        "description": "Step-by-step Zigbee connectivity troubleshooting for Hub v2 customers.",
        "steps": [
            {"order": 1, "instruction": "Check Hub v2 firmware — recommend updating to 3.2.0 if on 3.1.4 (fixes Zigbee regression)", "tool": "recall_memory"},
            {"order": 2, "instruction": "Ask about hub placement — devices > 15m from hub are affected in 3.1.4", "tool": "ask_user"},
            {"order": 3, "instruction": "Check device count — Hub v2 max is 128 devices", "tool": "ask_user"},
            {"order": 4, "instruction": "Suggest factory reset only as last resort; remind to export config first", "tool": "ask_user"},
            {"order": 5, "instruction": "If issue persists post-3.2.0, escalate to tier-2 with device logs", "tool": "escalate"},
        ],
    },
]

# James: Hub v1 in Amsterdam, considering upgrade. Amsterdam makes isolation demo obvious.
JAMES_EPISODIC = [
    "Hey, I'm James. I'm based in Amsterdam. I've had my Lumio Hub v1 for about 3 years. Lately it drops offline for a few minutes — maybe twice a day.",
    "I haven't updated the firmware in a while, to be honest. Didn't even know there were updates.",
    "I just bought 3 Lumio Smart Bulbs for the living room but they only show white light, not the full color I expected.",
    "How much does it cost to upgrade to the Hub v2? Is it worth it for me?",
]
JAMES_SEMANTIC = [
    ("James is based in Amsterdam.", "identity", 1.0),
    ("James owns a Lumio Hub v1 (legacy, no longer receiving firmware updates).", "identity", 1.0),
    ("James's Hub v1 firmware is outdated — he has not updated it since purchase.", "constraint", 0.8),
    ("James purchased 3 Lumio Smart Bulbs expecting full color support, but Hub v1 limits them to white only.", "constraint", 0.95),
    ("James is actively considering upgrading from Hub v1 to Hub v2.", "preference", 0.9),
]
JAMES_PROCEDURAL: list[dict] = []


def _delete_seeds(es) -> None:
    for index in MEMORY_INDICES.values():
        try:
            es.delete_by_query(
                index=index,
                body={"query": {"terms": {"user_id": SEED_USERS}}},
                refresh=True,
                conflicts="proceed",
            )
        except Exception as exc:
            print(f"  WARN clearing {index}: {exc}")


def _seed_user(es, user_id: str, episodic, semantic, procedural) -> None:
    print(f"  user {user_id}:")
    for text in episodic:
        write_memory(es, user_id=user_id, memory_type="episodic", text=text)
    print(f"    {len(episodic)} episodic")
    for text, fact_type, confidence in semantic:
        write_memory(es, user_id=user_id, memory_type="semantic", text=text, fact_type=fact_type, confidence=confidence)
    print(f"    {len(semantic)} semantic")
    for proc in procedural:
        write_memory(es, user_id=user_id, memory_type="procedural", text=proc["trigger"],
                     name=proc["name"], description=proc["description"], steps=proc["steps"])
    print(f"    {len(procedural)} procedural")


def main() -> int:
    es = get_es_client()
    print("Clearing prior seeds...")
    _delete_seeds(es)
    print("Seeding...")
    _seed_user(es, "sarah", SARAH_EPISODIC, SARAH_SEMANTIC, SARAH_PROCEDURAL)
    _seed_user(es, "james", JAMES_EPISODIC, JAMES_SEMANTIC, JAMES_PROCEDURAL)
    for index in MEMORY_INDICES.values():
        es.indices.refresh(index=index)
    for user_id in SEED_USERS:
        for memory_type, index in MEMORY_INDICES.items():
            count = es.count(index=index, body={"query": {"term": {"user_id": user_id}}})["count"]
            print(f"  {user_id}.{memory_type:11} {count}")
    print("\nSeed complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
