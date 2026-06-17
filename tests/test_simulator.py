"""Pure day-in-the-life simulator tests. No hardware."""

from sim.simulator import Tick, run_day


def test_run_day_returns_a_timeline():
    timeline = run_day()
    assert len(timeline) > 0
    assert all(isinstance(t, Tick) for t in timeline)


def test_night_segment_makes_it_sleepy_by_morning():
    timeline = run_day()
    darkest = min(timeline, key=lambda t: t.light)
    assert darkest.mood.sleepiness > 40.0


def test_interaction_tick_records_greeting_behavior():
    timeline = run_day()
    assert any(t.behavior == "greeting" for t in timeline)


def test_repeated_visits_grow_familiarity():
    timeline = run_day()
    assert timeline[-1].familiarity > timeline[0].familiarity
