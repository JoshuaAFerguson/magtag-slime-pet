"""Tests for pure dream assembly and artifact memory."""

from slime.dreams import (
    ARTIFACTS,
    add_artifact,
    artifact_name,
    generate,
    has_artifact,
    should_dream,
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
