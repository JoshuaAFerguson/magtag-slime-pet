from app.moon import moon


def test_new_moon_2000():
    m = moon(2000, 1, 6)  # ~new moon
    assert m["phase"] == 0
    assert m["illum"] < 0.1
    assert m["name"] == "new"


def test_full_moon_2000():
    m = moon(2000, 1, 21)  # ~full moon
    assert m["phase"] == 4
    assert m["illum"] > 0.9
    assert m["name"] == "full"


def test_illumination_and_phase_bounds():
    for day in range(1, 29):
        m = moon(2026, 6, day)
        assert 0 <= m["phase"] <= 7
        assert 0.0 <= m["illum"] <= 1.0
