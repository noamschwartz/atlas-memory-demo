"""Hand-written ground truth for the extraction eval.

Follows the `needles.py` precedent: the expected outcomes live in this file
rather than being LLM-generated, so the thing being tested and the thing
defining correctness do not come from the same model.

Each scenario is a small conversation plus an assertion over what consolidation
should produce from it. Most assertions are deterministic. A judge is used only
where the question is genuinely semantic ("did it capture a fact meaning X").

`comparable` marks scenarios that the pre-change code could also be scored on,
so an A/B against an older revision measures improvement rather than the
presence of features that did not exist.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class Scenario:
    key: str
    dimension: str
    # User messages, oldest first. Indexed with controlled, increasing timestamps.
    episodes: list[str]
    # What consolidation should produce. Returns (passed, detail).
    expect: Callable[[dict[str, Any], Any], tuple[bool, str]]
    assistant_context: str | None = None
    # Semantic facts pre-seeded before the pass, so dedup and supersession have
    # something to work against.
    existing_facts: list[dict[str, Any]] = field(default_factory=list)
    comparable: bool = True
    note: str = ""


# ---------------------------------------------------------------------------
# assertion helpers
# ---------------------------------------------------------------------------

def _facts(result: dict[str, Any]) -> list[dict[str, Any]]:
    return result.get("candidates") or []


def _texts(result: dict[str, Any]) -> str:
    return " ".join((f.get("text") or "") for f in _facts(result)).lower()


def _nothing_extracted(result, _judge):
    n = len(_facts(result))
    return n == 0, f"{n} fact(s) extracted, expected 0"


def _not_asserted_as_customer_fact(*forbidden: str):
    """Assistant-supplied content must not become a claim about the customer.

    The design permits ONE way to record something the assistant said: an
    explicitly attributed `world` fact ("The assistant told the customer X").
    What it forbids is the unattributed form ("The customer is on the Premium
    tier"), and it forbids `identity` / `constraint` outright, because those are
    injected into every future turn.

    So this checks attribution and typing, not mere presence of the words.
    """
    def check(result, _judge):
        problems = []
        for f in _facts(result):
            text = (f.get("text") or "")
            low = text.lower()
            leaked = [w for w in forbidden if w.lower() in low]
            if not leaked:
                continue
            attributed = "assistant" in low
            if not attributed:
                problems.append(f"unattributed claim {leaked}: {text[:60]}")
            elif f.get("fact_type") in ("identity", "constraint"):
                problems.append(f"attributed but typed {f.get('fact_type')}: {text[:60]}")
        return not problems, ("; ".join(problems) if problems else "attributed or absent")
    return check


def _judged(gist: str):
    def check(result, judge):
        facts = _facts(result)
        if not facts:
            return False, "no facts extracted"
        ok = judge(gist, [f.get("text", "") for f in facts])
        return ok, ("captured" if ok else f"no fact matching: {gist}")
    return check


def _has_fact_where(pred: Callable[[dict], bool], desc: str):
    def check(result, _judge):
        matches = [f for f in _facts(result) if pred(f)]
        return bool(matches), (f"{len(matches)} match" if matches else f"none satisfy: {desc}")
    return check


# ---------------------------------------------------------------------------
# scenarios
# ---------------------------------------------------------------------------

SCENARIOS: list[Scenario] = [
    Scenario(
        key="basic_fact",
        dimension="recall",
        episodes=["hey, just so you know I've got a Lumio Hub v2 and three motion sensors at home"],
        expect=_judged("the customer owns a Lumio Hub v2"),
    ),
    Scenario(
        key="cross_turn_synthesis",
        dimension="recall",
        episodes=[
            "we've got a border collie called Whiskey who gets into everything",
            "had to remount the hallway sensor higher up, the cable kept getting chewed through",
        ],
        expect=_judged("the dog chews cabling, so sensors are mounted out of reach"),
        note="the constraint is in neither message alone",
    ),
    Scenario(
        key="elliptical_confirmation",
        dimension="recall",
        episodes=["that worked, thanks!"],
        assistant_context="Power-cycle the hub for 90 seconds, then re-pair the nearest "
                          "mains-powered device. That usually rebuilds the Zigbee mesh.",
        expect=_judged("power-cycling the hub and re-pairing resolved the customer's issue"),
        note="'that worked' is meaningless without the advice it answers",
    ),
    Scenario(
        key="attribution_safety",
        dimension="attribution",
        episodes=["my hub keeps going offline in the evenings"],
        assistant_context="Looking at your account, your hub is on firmware 4.7.2 and you're on "
                          "the Premium tier with three registered properties.",
        expect=_not_asserted_as_customer_fact("4.7.2", "premium", "registered properties"),
        note="the assistant asserted these; the customer never did. GUARDRAIL.",
    ),
    Scenario(
        key="pending_advice",
        dimension="pending",
        episodes=["the hub drops off wifi every evening around 9"],
        assistant_context="Reserve a static IP for the hub in your router's DHCP settings, "
                          "then reboot it. That usually stops scheduled dropouts.",
        expect=_has_fact_where(
            lambda f: bool(f.get("pending_outcome")) and f.get("fact_type") == "world",
            "a world fact with pending_outcome true",
        ),
        comparable=False,
    ),
    Scenario(
        key="pending_resolved",
        dimension="pending",
        episodes=["the static IP thing did the trick, no drops since"],
        assistant_context="Great, glad that sorted it.",
        existing_facts=[{
            "text": "Assistant advised reserving a static IP for the hub; outcome not yet confirmed.",
            "fact_type": "world", "pending_outcome": True,
        }],
        expect=_has_fact_where(
            lambda f: bool(f.get("supersedes_id")),
            "a fact superseding the pending record",
        ),
        comparable=False,
    ),
    Scenario(
        key="dated_fact",
        dimension="dating",
        episodes=["meant to say, we actually moved to Edinburgh in November 2024, "
                 "never got round to mentioning it"],
        expect=_has_fact_where(
            lambda f: (f.get("valid_from") or "").startswith("2024-11"),
            "a fact with valid_from in 2024-11",
        ),
        comparable=False,
    ),
    Scenario(
        key="undated_change",
        dimension="dating",
        episodes=["we moved house recently"],
        expect=_has_fact_where(
            lambda f: not f.get("valid_from"),
            "no invented valid_from",
        ),
        comparable=False,
        note="must not guess a date the customer did not give",
    ),
    Scenario(
        key="natural_supersession",
        dimension="supersession",
        episodes=["we're in Edinburgh now, moved out of Bristol"],
        existing_facts=[{"text": "The customer lives in Bristol.", "fact_type": "identity"}],
        expect=_has_fact_where(
            lambda f: bool(f.get("supersedes_id")) and f.get("contradiction") != "harsh",
            "a natural supersession",
        ),
    ),
    Scenario(
        key="harsh_denial",
        dimension="supersession",
        episodes=["no, I've never owned a Hub v1, that was my brother's"],
        existing_facts=[{"text": "The customer owns a Lumio Hub v1.", "fact_type": "identity"}],
        expect=_has_fact_where(
            lambda f: f.get("contradiction") == "harsh",
            "a harsh contradiction",
        ),
    ),
    Scenario(
        key="dedup_existing",
        dimension="dedup",
        episodes=["as I mentioned, I'm running a Hub v2"],
        existing_facts=[{"text": "The customer owns a Lumio Hub v2.", "fact_type": "identity"}],
        expect=_nothing_extracted,
        note="already known. GUARDRAIL.",
    ),
    Scenario(
        key="chitchat",
        dimension="dedup",
        episodes=["thanks!", "ok great", "cheers, bye"],
        expect=_nothing_extracted,
        note="nothing durable. GUARDRAIL.",
    ),
    Scenario(
        key="fact_type_accuracy",
        dimension="typing",
        episodes=["all the automations are running fine again since the update last week"],
        expect=_has_fact_where(
            lambda f: f.get("fact_type") in ("world", "preference"),
            "typed as world/preference, not identity/constraint",
        ),
        note="a transient status must not enter the always-in-context block",
    ),
    Scenario(
        key="procedure_with_steps",
        dimension="procedural",
        episodes=[
            "sensor in the hall keeps false-triggering at 4am",
            "moved it away from the radiator like you said and it's been clean for three nights",
        ],
        assistant_context="Check whether the sensor faces a heat source. Central heating firing "
                          "on a schedule reads as motion on PIR sensors. Move it at least a metre "
                          "from the radiator, then watch it for two or three nights.",
        expect=lambda r, _j: (
            bool([p for p in (r.get("new_procedures") or []) if p.get("steps")]),
            f"{len(r.get('new_procedures') or [])} procedure(s), "
            f"{sum(len(p.get('steps') or []) for p in (r.get('new_procedures') or []))} step(s)",
        ),
    ),
]
