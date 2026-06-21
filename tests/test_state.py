import glob
import os

from slime.state import MOOD_FIELDS, Mood, clamp, clamp_mood, default_state, evolve


def test_mood_has_five_named_drives():
    assert MOOD_FIELDS == ("energy", "comfort", "curiosity", "sleepiness", "affection")
    m = Mood(1, 2, 3, 4, 5)
    assert m.energy == 1 and m.affection == 5


def test_clamp_bounds_values_to_0_100():
    assert clamp(-10) == 0.0
    assert clamp(150) == 100.0
    assert clamp(42) == 42.0


def test_clamp_mood_clamps_every_drive():
    m = clamp_mood(Mood(-5, 200, 50, 50, 50))
    assert m.energy == 0.0
    assert m.comfort == 100.0
    assert m.curiosity == 50.0


def test_default_state_is_reasonable_and_immutable():
    s = default_state(now=100.0)
    assert isinstance(s.mood, Mood)
    assert s.total_boops == 0
    assert s.first_boot == 100.0
    assert s.last_seen == 100.0
    assert s.expression == "content"
    assert s.behavior == "idle"
    s2 = s._replace(total_boops=1)
    assert s.total_boops == 0 and s2.total_boops == 1


def test_evolve_changes_only_named_fields_without_mutating():
    s = default_state(now=5.0)
    s2 = evolve(s, total_boops=3, expression="happy")
    assert s2.total_boops == 3
    assert s2.expression == "happy"
    # untouched fields carry over
    assert s2.mood == s.mood
    assert s2.first_boot == s.first_boot
    # original is unchanged
    assert s.total_boops == 0 and s.expression == "content"


def test_production_modules_avoid_namedtuple_replace():
    """CircuitPython's namedtuple has no _replace(); on-device modules must use evolve()."""
    root = os.path.dirname(os.path.dirname(__file__))
    targets = glob.glob(os.path.join(root, "slime", "*.py"))
    targets += glob.glob(os.path.join(root, "sim", "*.py"))
    targets.append(os.path.join(root, "code.py"))
    offenders = []
    for path in targets:
        with open(path) as f:
            if "._replace(" in f.read():
                offenders.append(os.path.relpath(path, root))
    assert not offenders, f"namedtuple._replace breaks CircuitPython; found in: {offenders}"


def test_state_has_friendship_and_artifact_fields():
    s = default_state(now=0.0)
    assert s.familiarity == 0.0
    assert s.visit_count == 0
    assert s.artifacts == 0


def test_evolve_updates_new_fields():
    s = default_state(now=0.0)
    s2 = evolve(s, familiarity=12.0, visit_count=3, artifacts=5)
    assert s2.familiarity == 12.0
    assert s2.visit_count == 3
    assert s2.artifacts == 5
    assert s.familiarity == 0.0  # original unchanged


def test_state_has_last_journal_day_ordinal():
    s = default_state(now=0.0)
    assert s.last_journal_day_ordinal == 0
    s2 = evolve(s, last_journal_day_ordinal=42)
    assert s2.last_journal_day_ordinal == 42
    assert s.last_journal_day_ordinal == 0


def test_default_state_has_zero_milestones():
    from slime.state import default_state

    assert default_state().milestones == 0


def test_evolve_sets_milestones():
    from slime.state import default_state, evolve

    s = evolve(default_state(), milestones=0b101)
    assert s.milestones == 0b101
    assert s.familiarity == 0.0


def test_default_state_has_zero_visitors():
    from slime.state import default_state

    assert default_state().visitors == 0


def test_evolve_sets_visitors():
    from slime.state import default_state, evolve

    s = evolve(default_state(), visitors=0b1010)
    assert s.visitors == 0b1010
    assert s.milestones == 0  # other fields preserved
