"""Seed the shared `atlas_catalog` index with the Lumio knowledge base.

11 documents: product overviews, firmware notes, known issues, troubleshooting
guides, policies, and the Range Extender product.

Usage: uv run python -m scripts.atlas.seed_catalog
"""

from __future__ import annotations

import sys

from app.elasticsearch.client import get_es_client
from app.atlas.memory.constants import INDEX_CATALOG

CATALOG = [
    {
        "title": "Lumio Hub v2 — Product Overview",
        "text": (
            "The Lumio Hub v2 is the central controller for your Lumio smart home. "
            "It connects via WiFi (2.4GHz/5GHz) and supports Zigbee 3.0 for up to 128 devices. "
            "Requires iOS 14+ or Android 9+. Measures 110x110x40mm. Power via USB-C."
        ),
        "category": "product",
        "tags": ["hub-v2", "zigbee", "setup"],
    },
    {
        "title": "Lumio Hub v1 — Legacy Product",
        "text": (
            "The Lumio Hub v1 uses WiFi-only connectivity and supports up to 64 devices. "
            "Hub v1 is no longer receiving firmware updates as of January 2026. "
            "Customers are encouraged to upgrade to Hub v2 for continued support and new device compatibility."
        ),
        "category": "product",
        "tags": ["hub-v1", "legacy", "discontinued"],
    },
    {
        "title": "Lumio Motion Sensor Pro — Setup Guide",
        "text": (
            "The Motion Sensor Pro uses Zigbee 3.0 and is compatible with both Hub v1 and Hub v2. "
            "Range: 10 meters, 120 degree field of view. "
            "Pair by holding the button for 3 seconds with Hub in pairing mode. "
            "Battery life: 2 years (CR2 battery)."
        ),
        "category": "product",
        "tags": ["motion-sensor", "zigbee", "setup"],
    },
    {
        "title": "Lumio Smart Bulb (E27) — Compatibility",
        "text": (
            "Lumio Smart Bulbs support full 16 million color range only on Hub v2 running firmware 3.2.0 or later. "
            "On Hub v1 or older Hub v2 firmware, bulbs are limited to warm white and cool white only. "
            "No hub is required for white-only mode via Bluetooth (10m range)."
        ),
        "category": "product",
        "tags": ["smart-bulb", "color", "compatibility", "hub-v2"],
    },
    {
        "title": "Firmware 3.1.4 — Release Notes and Known Issue",
        "text": (
            "Released March 2026. Fixes: improved Zigbee pairing speed, reduced app startup time. "
            "Known regression: intermittent Zigbee disconnects for devices located more than 15 meters from the Hub v2. "
            "Workaround: move Hub v2 to a central location or add a Lumio Range Extender. "
            "Customers experiencing this issue are advised to update to 3.2.0 as soon as possible."
        ),
        "category": "firmware",
        "tags": ["firmware", "zigbee", "connectivity", "known-issue", "3.1.4"],
    },
    {
        "title": "Firmware 3.2.0 — Release Notes",
        "text": (
            "Released April 2026. Fixes the Zigbee connectivity regression introduced in 3.1.4 — "
            "all devices should reconnect reliably regardless of placement. "
            "New: full color support for Lumio Smart Bulbs. "
            "New: improved energy monitoring dashboard. "
            "To update: open the Lumio app then Settings then Hub then Firmware then Check for updates. "
            "Auto-update is available and recommended."
        ),
        "category": "firmware",
        "tags": ["firmware", "zigbee", "color", "3.2.0", "fix"],
    },
    {
        "title": "Known Issue — iOS App Login Loop (v2.3.0)",
        "text": (
            "Users on iOS 17.4 running Lumio app v2.3.0 may experience an infinite login loop. "
            "Workaround: force-close the app completely and reopen. "
            "If the issue persists, delete and reinstall the app — your devices and automations are stored "
            "in the cloud and will sync back. "
            "A permanent fix is shipping in app v2.3.1."
        ),
        "category": "known-issue",
        "tags": ["ios", "login", "app-bug", "workaround"],
    },
    {
        "title": "Troubleshooting — Factory Reset Hub v2",
        "text": (
            "To factory reset the Hub v2: hold the recessed reset button (on the bottom) for 10 seconds "
            "until the LED flashes red, then release. The hub will reboot and all paired devices will be removed. "
            "Important: export your device list and automations from the app before resetting "
            "(Settings then Export). After reset, re-pair devices using the Lumio app."
        ),
        "category": "troubleshooting",
        "tags": ["factory-reset", "hub-v2", "pairing"],
    },
    {
        "title": "Warranty and Returns Policy",
        "text": (
            "Lumio Hub devices carry a 2-year limited warranty covering manufacturing defects. "
            "Motion sensors and smart bulbs carry a 1-year warranty. "
            "To initiate a warranty claim: contact support@lumio.io with your order number and a description. "
            "Returns are accepted within 90 days of purchase in original packaging for a full refund."
        ),
        "category": "policy",
        "tags": ["warranty", "returns", "support"],
    },
    {
        "title": "Upgrading from Hub v1 to Hub v2",
        "text": (
            "Hub v1 customers upgrading to Hub v2 can transfer their device list using the Lumio Migration Tool "
            "(Settings then Hub then Migrate to Hub v2). "
            "Zigbee devices will re-pair automatically during migration. "
            "WiFi-only devices must be manually re-added. "
            "The Hub v1 can remain active as a secondary controller during the 30-day transition period. "
            "Upgrade pricing: existing customers receive a 30% discount via the app."
        ),
        "category": "guide",
        "tags": ["upgrade", "hub-v1", "hub-v2", "migration"],
    },
    {
        "title": "Lumio Range Extender — Setup and Placement",
        "text": (
            "The Lumio Range Extender plugs into any standard outlet and extends Zigbee coverage by up to 20 meters. "
            "Pair it in the Lumio app under Devices then Add Device then Range Extender. "
            "Ideal placement: midway between the Hub v2 and devices experiencing connectivity drops. "
            "One Range Extender is typically sufficient for homes up to 200 square meters. "
            "Compatible with Hub v2 only; not supported on Hub v1."
        ),
        "category": "product",
        "tags": ["range-extender", "zigbee", "connectivity", "hub-v2"],
    },
]


def main() -> int:
    es = get_es_client()
    print(f"Re-seeding {INDEX_CATALOG}...")
    es.delete_by_query(
        index=INDEX_CATALOG,
        body={"query": {"match_all": {}}},
        refresh=True,
        conflicts="proceed",
    )
    for i, doc in enumerate(CATALOG):
        es.index(index=INDEX_CATALOG, id=f"cat-{i:03d}", document=doc)
    es.indices.refresh(index=INDEX_CATALOG)
    count = es.count(index=INDEX_CATALOG)["count"]
    print(f"  OK   indexed {count} catalog docs")
    return 0


if __name__ == "__main__":
    sys.exit(main())
