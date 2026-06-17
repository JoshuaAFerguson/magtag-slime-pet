"""Tests for the pure mood engine."""

from slime.mood import Inputs, derive_behavior, derive_expression, step
from slime.state import Mood, default_state


def idle_inputs(**kw):
    base = dict(light=0.5, battery=0.8, on_usb=True, seconds_since_interaction=10.0, events=())
    base.update(kw)
    return Inputs(**base)


def test_darkness_increases_sleepiness_over_time():
    s = default_state(now=0.0)
    s2 = step(s, idle_inputs(light=0.02), dt=60.0)
    assert s2.mood.sleepiness > s.mood.sleepiness


def test_bright_light_wakes_the_slime():
    s = default_state(now=0.0)._replace(mood=Mood(50, 70, 50, 80, 40))
    s2 = step(s, idle_inputs(light=0.95), dt=60.0)
    assert s2.mood.sleepiness < 80


def test_low_battery_lowers_energy():
    s = default_state(now=0.0)
    s2 = step(s, idle_inputs(battery=0.05), dt=60.0)
    assert s2.mood.energy < s.mood.energy


def test_double_tap_event_raises_affection_and_curiosity():
    s = default_state(now=0.0)
    s2 = step(s, idle_inputs(events=("double_tap",)), dt=1.0)
    assert s2.mood.affection > s.mood.affection
    assert s2.mood.curiosity > s.mood.curiosity


def test_long_absence_makes_it_contemplative_not_sad():
    s = default_state(now=0.0)
    s2 = step(s, idle_inputs(seconds_since_interaction=86400.0), dt=60.0)
    assert 0.0 <= s2.mood.comfort <= 100.0
    assert s2.expression in ("contemplative", "sleepy", "content")


def test_step_returns_clamped_new_state_without_mutating_input():
    s = default_state(now=0.0)
    s2 = step(s, idle_inputs(events=("double_tap", "double_tap", "double_tap")), dt=1.0)
    for v in s2.mood:
        assert 0.0 <= v <= 100.0
    assert s.mood.affection == 40.0


def test_derive_expression_maps_dominant_drive():
    assert derive_expression(Mood(50, 50, 50, 95, 30)) == "sleepy"
    assert derive_expression(Mood(50, 50, 95, 20, 30)) == "curious"
    assert derive_expression(Mood(90, 60, 50, 10, 85)) == "happy"
    assert derive_expression(Mood(60, 80, 40, 20, 40)) == "content"


def test_derive_behavior_prioritizes_events():
    assert derive_behavior(Mood(60, 70, 50, 30, 40), ("flip",)) == "dizzy"
    assert derive_behavior(Mood(60, 70, 50, 30, 40), ("double_tap",)) == "greeting"
    assert derive_behavior(Mood(60, 70, 50, 30, 40), ()) == "idle"
