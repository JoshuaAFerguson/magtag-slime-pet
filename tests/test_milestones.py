from collections import namedtuple

from slime import milestones

Ora = namedtuple("Ora", "weather_tag moon_phase")
St = namedtuple("St", "artifacts longest_absence")


def test_evaluate_sets_storm_and_full_moon():
    f = milestones.evaluate(0, Ora("storm_incoming", 4), St(0, 0.0), 0)
    assert f & milestones.FIRST_STORM
    assert f & milestones.FULL_MOON_NIGHT


def test_evaluate_bonded_collector_faithful():
    f = milestones.evaluate(0, Ora("clear", 2), St(0xFF, 7 * 24 * 3600.0), 3)
    assert f & milestones.BONDED
    assert f & milestones.COLLECTOR
    assert f & milestones.FAITHFUL


def test_evaluate_never_clears_and_tolerates_no_oracle():
    f = milestones.evaluate(milestones.FIRST_STORM, None, St(0, 0.0), 0)
    assert f & milestones.FIRST_STORM  # preserved even with no oracle and no conditions


def test_memory_quip_none_when_nothing_unlocked():
    assert milestones.memory_quip(0, lambda options: options[0]) is None


def test_memory_quip_returns_an_unlocked_line():
    line = milestones.memory_quip(milestones.BONDED, lambda options: options[0])
    assert isinstance(line, str) and "you and i" in line
