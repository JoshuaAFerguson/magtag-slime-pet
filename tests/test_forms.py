"""Tests for form selection logic."""

from slime.forms import choose_render
from slime.state import Mood
from slime.visuals import POSE_INDEX


def test_sleeping_renders_loaf():
    assert choose_render(Mood(50, 60, 40, 90, 40), tier=4, sleeping=True) == POSE_INDEX["loaf"]


def test_very_low_energy_renders_puddle():
    assert choose_render(Mood(8, 60, 40, 40, 40), tier=4, sleeping=False) == POSE_INDEX["puddle"]


def test_explorer_requires_tier_unlock():
    eager = Mood(80, 60, 85, 20, 40)
    assert choose_render(eager, tier=0, sleeping=False) == POSE_INDEX["curious"]
    assert choose_render(eager, tier=1, sleeping=False) == POSE_INDEX["explorer"]


def test_crowned_requires_high_tier_and_affection():
    bonded = Mood(70, 70, 40, 20, 90)
    assert choose_render(bonded, tier=2, sleeping=False) != POSE_INDEX["crowned"]
    assert choose_render(bonded, tier=3, sleeping=False) == POSE_INDEX["crowned"]


def test_long_quiet_low_drive_renders_wisp():
    quiet = Mood(30, 60, 15, 40, 40)
    assert choose_render(quiet, tier=0, sleeping=False) == POSE_INDEX["wisp"]


def test_default_falls_back_to_expression_face():
    calm = Mood(60, 80, 50, 30, 40)  # derive_expression -> content
    assert choose_render(calm, tier=4, sleeping=False) == POSE_INDEX["content"]


def test_calm_mood_shows_seasonal_form_when_season_given():
    calm = Mood(60, 80, 50, 30, 40)  # derive_expression -> content
    assert choose_render(calm, tier=4, sleeping=False, season="winter") == POSE_INDEX["winter_form"]


def test_no_season_keeps_content_face():
    calm = Mood(60, 80, 50, 30, 40)
    assert choose_render(calm, tier=4, sleeping=False) == POSE_INDEX["content"]


def test_mood_form_still_wins_over_season():
    sleepy = Mood(50, 60, 40, 90, 40)
    assert choose_render(sleepy, tier=4, sleeping=True, season="winter") == POSE_INDEX["loaf"]
