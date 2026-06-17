"""Tests for pure presentation & power-mode decisions."""

from slime.state import Mood
from slime.visuals import (
    POSE_INDEX,
    breath_brightness,
    choose_run_mode,
    expression_to_pose,
    mood_to_rgb,
    should_refresh,
)


def test_expression_to_pose_maps_known_expressions():
    assert expression_to_pose("content") == POSE_INDEX["content"]
    assert expression_to_pose("sleepy") == POSE_INDEX["sleepy"]


def test_expression_to_pose_unknown_falls_back_to_resting():
    assert expression_to_pose("???") == POSE_INDEX["resting"]


def test_mood_to_rgb_returns_byte_triple():
    r, g, b = mood_to_rgb(Mood(60, 70, 50, 30, 40))
    for c in (r, g, b):
        assert 0 <= c <= 255


def test_sleepy_mood_is_dim_blue_ish():
    r, g, b = mood_to_rgb(Mood(20, 60, 30, 95, 30))
    assert b >= r and b >= g


def test_breath_brightness_oscillates_within_bounds():
    vals = [breath_brightness(t, rate=0.25, lo=0.05, hi=0.5) for t in range(0, 40)]
    assert min(vals) >= 0.05 - 1e-9
    assert max(vals) <= 0.5 + 1e-9
    assert max(vals) - min(vals) > 0.1


def test_should_refresh_on_significant_event_even_if_recent():
    assert (
        should_refresh(
            now=10.0,
            last_refresh=9.0,
            pose_changed=False,
            significant_event=True,
            min_interval=180.0,
            scheduled_interval=21600.0,
        )
        is True
    )


def test_should_refresh_blocks_rapid_pose_flicker():
    assert (
        should_refresh(
            now=10.0,
            last_refresh=9.0,
            pose_changed=True,
            significant_event=False,
            min_interval=180.0,
            scheduled_interval=21600.0,
        )
        is False
    )


def test_should_refresh_allows_pose_change_after_min_interval():
    assert (
        should_refresh(
            now=200.0,
            last_refresh=10.0,
            pose_changed=True,
            significant_event=False,
            min_interval=180.0,
            scheduled_interval=21600.0,
        )
        is True
    )


def test_should_refresh_scheduled_update_when_stale():
    assert (
        should_refresh(
            now=30000.0,
            last_refresh=0.0,
            pose_changed=False,
            significant_event=False,
            min_interval=180.0,
            scheduled_interval=21600.0,
        )
        is True
    )


def test_choose_run_mode():
    assert choose_run_mode(on_usb=True, battery=0.9) == "continuous"
    assert choose_run_mode(on_usb=False, battery=0.9) == "wake_cycle"
