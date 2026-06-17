from slime.state import Mood, State, clamp, clamp_mood, default_state, MOOD_FIELDS


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
