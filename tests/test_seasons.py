"""Tests for pure seasonal logic: month -> season, mood bias, frames."""

from slime.seasons import (
    SEASONS,
    accent_frame,
    apply_bias,
    form_frame,
    quip_tag,
    season_of,
)
from slime.state import Mood


def test_season_of_month():
    """Month mapping to season."""
    assert season_of(4) == "spring"
    assert season_of(7) == "summer"
    assert season_of(10) == "autumn"
    assert season_of(1) == "winter"
    assert season_of(12) == "winter"


def test_apply_bias_moves_mood_toward_seasonal_target_and_clamps():
    """apply_bias nudges biased drives toward seasonal targets and clamps all."""
    cold = Mood(60, 30, 50, 30, 40)  # low comfort
    warmer = apply_bias(cold, "winter")
    assert warmer.comfort > cold.comfort  # winter nudges comfort up
    for v in warmer:
        assert 0.0 <= v <= 100.0


def test_apply_bias_is_self_limiting():
    """Repeated bias application converges, never overflows."""
    m = Mood(60, 30, 50, 30, 40)
    for _ in range(200):
        m = apply_bias(m, "winter")
    assert m.comfort <= 100.0  # converges, never overflows


def test_frames_and_quip_tag_distinct_per_season():
    """form_frame, accent_frame are distinct per season; quip_tag maps season to itself."""
    forms = {form_frame(s) for s in SEASONS}
    accents = {accent_frame(s) for s in SEASONS}
    assert len(forms) == 4 and len(accents) == 4
    assert quip_tag("summer") == "summer"
