from app.oracle import build


def test_build_shapes_payload():
    weather = {"tags": ["extreme_heat"], "temp_c": 43, "code": 0, "sunset_soon": False}
    mooninfo = {"phase": 4, "name": "full", "illum": 0.98}
    presence = {"coding_rhythm": "heavy", "hours_since_push": 1.5}
    out = build(weather, mooninfo, presence, ts=1718900000)
    assert out["weather"]["tags"] == ["extreme_heat"]
    assert out["moon"]["phase"] == 4
    assert out["presence"]["coding_rhythm"] == "heavy"
    assert out["ts"] == 1718900000


def test_build_includes_calendar_when_present():
    cal = {
        "in_meeting": True,
        "meeting_soon": False,
        "day_load": "heavy",
        "free_rest_of_day": False,
    }
    out = build({}, {}, {}, calendar=cal, ts=1)
    assert out["calendar"]["in_meeting"] is True


def test_build_omits_calendar_when_none():
    out = build({}, {}, {}, calendar=None, ts=1)
    assert "calendar" not in out
