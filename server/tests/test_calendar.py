from datetime import datetime, timedelta, timezone

from app.calendar import summarize

NOW = datetime(2026, 6, 19, 15, 0, tzinfo=timezone.utc)


def _ev(start_min_from_now, dur_min=30):
    s = NOW + timedelta(minutes=start_min_from_now)
    return (s, s + timedelta(minutes=dur_min))


def test_empty_is_idle():
    out = summarize([], NOW)
    assert out == {
        "in_meeting": False,
        "meeting_soon": False,
        "day_load": "light",
        "free_rest_of_day": True,
    }


def test_in_meeting_boundaries():
    assert summarize([(NOW, NOW + timedelta(minutes=30))], NOW)["in_meeting"] is True
    assert summarize([(NOW - timedelta(minutes=30), NOW)], NOW)["in_meeting"] is False


def test_meeting_soon_edge_and_suppressed_when_in_meeting():
    assert summarize([_ev(15)], NOW)["meeting_soon"] is True
    assert summarize([_ev(16)], NOW)["meeting_soon"] is False
    out = summarize([(NOW, NOW + timedelta(minutes=60)), _ev(10)], NOW)
    assert out["in_meeting"] is True
    assert out["meeting_soon"] is False


def test_day_load_thresholds():
    assert summarize([_ev(60)], NOW)["day_load"] == "light"
    assert summarize([_ev(60), _ev(120)], NOW)["day_load"] == "normal"
    assert summarize([_ev(60), _ev(120), _ev(180)], NOW)["day_load"] == "normal"
    assert summarize([_ev(i * 60) for i in range(1, 5)], NOW)["day_load"] == "heavy"


def test_free_rest_of_day():
    assert summarize([_ev(-120)], NOW)["free_rest_of_day"] is True
    assert summarize([_ev(120)], NOW)["free_rest_of_day"] is False
