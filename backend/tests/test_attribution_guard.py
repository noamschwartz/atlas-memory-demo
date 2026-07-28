"""The code-level guard against assistant content becoming customer facts.

The prompt forbids this, but the extraction eval measured the instruction alone
holding roughly a third of the time. This is the one rule where a probabilistic
guarantee is not good enough: a laundered claim is recalled back to the customer
as something they said, and hardens every time it is retrieved.
"""

from __future__ import annotations

import pytest

from app.atlas.consolidate import _distinctive, _drop_ungrounded


def _eps(*texts):
    return [{"id": f"e{i}", "source": {"text": t}} for i, t in enumerate(texts)]


def _fact(text, **kw):
    return {"text": text, **kw}


# ---------------------------------------------------------------------------
# tokenisation
# ---------------------------------------------------------------------------

def test_distinctive_keeps_version_like_tokens_at_any_length():
    assert "4.7.2" in _distinctive("running firmware 4.7.2")


def test_distinctive_strips_trailing_punctuation():
    """'nights.' and 'nights' must be the same token, or a sentence-final word
    reads as content the customer never used."""
    assert _distinctive("for three nights.") == _distinctive("for three nights")


def test_distinctive_skips_short_glue_words():
    toks = _distinctive("the hub is on a tier")
    assert "the" not in toks and "is" not in toks


# ---------------------------------------------------------------------------
# the guard
# ---------------------------------------------------------------------------

def test_drops_a_claim_sourced_only_from_the_assistant():
    kept, dropped = _drop_ungrounded(
        [_fact("The customer is on the Premium tier with three registered properties.")],
        _eps("my hub keeps going offline in the evenings"),
        "Looking at your account, you're on the Premium tier with three registered properties.",
    )
    assert kept == []
    assert len(dropped) == 1


def test_drops_on_a_single_version_token():
    """A version string the customer never uttered is a strong signal on its own."""
    kept, dropped = _drop_ungrounded(
        [_fact("The customer's hub runs firmware 4.7.2.")],
        _eps("my hub keeps going offline"),
        "Your hub is on firmware 4.7.2.",
    )
    assert kept == [] and len(dropped) == 1


def test_keeps_a_fact_grounded_in_the_customer_message():
    kept, dropped = _drop_ungrounded(
        [_fact("The customer's hub goes offline in the evenings.")],
        _eps("my hub keeps going offline in the evenings"),
        "Try reserving a static IP address for it.",
    )
    assert len(kept) == 1 and dropped == []


def test_one_shared_ordinary_word_is_not_enough_to_drop():
    """Regression: the guard once killed a legitimate fact because the assistant
    happened to say 'watch it for three nights'."""
    kept, dropped = _drop_ungrounded(
        [_fact("The customer's hall sensor was false-triggering at 4am for several nights.")],
        _eps("sensor in the hall keeps false-triggering at 4am"),
        "Move it away from the radiator, then watch it for two or three nights.",
    )
    assert len(kept) == 1, f"false positive: {dropped}"


def test_keeps_explicitly_attributed_records():
    """The permitted way to record what the assistant said."""
    kept, dropped = _drop_ungrounded(
        [_fact("The assistant told the customer their hub is on firmware 4.7.2.")],
        _eps("my hub keeps going offline"),
        "Your hub is on firmware 4.7.2.",
    )
    assert len(kept) == 1 and dropped == []


def test_records_why_a_fact_was_dropped():
    _, dropped = _drop_ungrounded(
        [_fact("The customer is on the Premium tier with registered properties.")],
        _eps("hub offline"),
        "You're on the Premium tier with three registered properties.",
    )
    assert dropped[0]["_dropped_because"], "drops must be auditable"


# ---------------------------------------------------------------------------
# no-op cases
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("ctx", [None, "", "   "])
def test_no_assistant_context_means_no_filtering(ctx):
    facts = [_fact("The customer owns a Hub v2.")]
    kept, dropped = _drop_ungrounded(facts, _eps("I own a Hub v2"), ctx)
    assert kept == facts and dropped == []


def test_no_candidates_is_handled():
    assert _drop_ungrounded([], _eps("anything"), "some context") == ([], [])
