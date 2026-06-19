"""Tests for pure dream assembly and artifact memory."""

from collections import namedtuple

from slime.dreams import (
    ARTIFACTS,
    add_artifact,
    artifact_name,
    dream_context,
    generate,
    has_artifact,
    should_dream,
)

# Stand-in for slime.oracle.Oracle's fields used by dream_context.
Ora = namedtuple(
    "Ora", "weather_tag moon_phase coding_rhythm cal_known day_load mail_known inbox_load"
)


def first(seq):
    return seq[0]


def test_should_dream_only_after_long_sleep():
    assert should_dream(slept=True, sleep_seconds=1200.0) is True
    assert should_dream(slept=True, sleep_seconds=10.0) is False
    assert should_dream(slept=False, sleep_seconds=9999.0) is False


def test_generate_is_deterministic_with_injected_choice():
    line1, art1 = generate(tier=0, artifacts_mask=0, choice=first)
    line2, art2 = generate(tier=0, artifacts_mask=0, choice=first)
    assert line1 == line2 and art1 == art2
    assert isinstance(line1, str) and line1.endswith(".")


def test_personal_reference_only_at_tier_2_plus():
    line_low, _ = generate(tier=1, artifacts_mask=0, choice=first)
    line_high, _ = generate(tier=2, artifacts_mask=0, choice=first)
    assert len(line_high) > len(line_low)


def test_generate_can_find_an_uncollected_artifact():
    _, art = generate(tier=0, artifacts_mask=0, choice=first)
    assert art == 0  # first uncollected artifact


def test_artifact_bitmask_helpers():
    mask = add_artifact(0, 2)
    assert has_artifact(mask, 2) is True
    assert has_artifact(mask, 1) is False
    assert artifact_name(2) == ARTIFACTS[2]


def test_generate_weaves_extra_ref_when_provided():
    line, _ = generate(
        tier=0, artifacts_mask=0, choice=lambda s: s[0], extra_refs=("beneath the full moon",)
    )
    assert "beneath the full moon" in line


def _rec(flags):
    # journal record tuple: (day_ordinal, mood_dom, season, flags, tier)
    return (20000, 2, 1, flags, 3)


def test_dream_context_tones_and_artifacts_from_state():
    ctx = dream_context(3, 0b101, [_rec(0b10)], "summer", None)  # busy flag, 2 artifacts
    assert ctx["fam"] == 3
    assert "busy" in ctx["tones"]
    assert ctx["artifacts"] == 2
    assert ctx["season"] == "summer"


def test_dream_context_quiet_when_no_flags():
    ctx = dream_context(1, 0, [], "winter", None)
    assert ctx["tones"] == ["quiet"]
    assert ctx["artifacts"] == 0


def test_dream_context_includes_oracle_signals():
    o = Ora("rain", 4, "heavy", True, "busy", True, "flooded")
    ctx = dream_context(2, 0, [], "spring", o)
    assert ctx["weather"] == "rain"
    assert ctx["moon"] == 4
    assert ctx["rhythm"] == "heavy"
    assert ctx["day_load"] == "busy"
    assert ctx["inbox"] == "flooded"


def test_dream_context_omits_gated_oracle_fields_when_unknown():
    o = Ora("clear", 2, "idle", False, "light", False, "clear")
    ctx = dream_context(0, 0, [], "autumn", o)
    assert "day_load" not in ctx  # cal_known False
    assert "inbox" not in ctx  # mail_known False
    assert ctx["weather"] == "clear"
