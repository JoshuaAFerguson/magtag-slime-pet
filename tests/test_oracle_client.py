"""Tests for pure oracle parsing, behavioral effects, and NVM caching."""

from slime.oracle import (
    dream_refs,
    form_override,
    is_busy,
    mood_bias,
    pack,
    parse,
    quip_tag,
    unpack,
)
from slime.state import Mood


def _payload(tags, phase=4, illum=0.98, sunset=False, temp=43.0):
    return {
        "weather": {"tags": tags, "temp_c": temp, "sunset_soon": sunset},
        "moon": {"phase": phase, "illum": illum},
    }


def _with_presence(rhythm, hours):
    return {
        "weather": {"tags": ["clear"], "temp_c": 25.0, "sunset_soon": False},
        "moon": {"phase": 2, "illum": 0.5},
        "presence": {"coding_rhythm": rhythm, "hours_since_push": hours},
    }


def test_parse_picks_dominant_tag_by_priority():
    o = parse(_payload(["clear", "storm_incoming"]))
    assert o.weather_tag == "storm_incoming"


def test_parse_handles_missing_payload():
    assert parse(None) is None
    assert parse({}) is not None


def test_form_override():
    assert form_override(parse(_payload(["extreme_heat"]))) == "melting"
    assert form_override(parse(_payload(["storm_incoming"]))) == "hiding"
    assert form_override(parse(_payload(["clear"]))) is None


def test_quip_tag():
    assert quip_tag(parse(_payload(["rain"]))) == "rain"
    assert quip_tag(parse(_payload(["clear"], phase=4))) == "full_moon"
    assert quip_tag(parse(_payload(["clear"], phase=0))) == "new_moon"
    assert quip_tag(parse(_payload(["clear"], phase=2))) is None


def test_mood_bias_extreme_heat_drains_energy():
    o = parse(_payload(["extreme_heat"]))
    biased = mood_bias(Mood(80, 60, 50, 30, 40), o)
    assert biased.energy < 80


def test_dream_refs_full_moon():
    refs = dream_refs(parse(_payload(["clear"], phase=4)))
    assert any("moon" in r for r in refs)


def test_cache_roundtrip():
    o = parse(
        _payload(
            ["storm_incoming"],
            phase=4,
            illum=0.98,
            sunset=True,
            temp=30.0,
        )
    )
    o2 = unpack(pack(o))
    assert o2.weather_tag == "storm_incoming"
    assert o2.moon_phase == 4
    assert o2.sunset_soon is True


def test_parse_reads_presence():
    o = parse(_with_presence("heavy", 1.5))
    assert o.coding_rhythm == "heavy"
    assert o.hours_since_push == 1.5


def test_parse_defaults_presence_idle_when_absent():
    o = parse(_payload(["clear"]))
    assert o.coding_rhythm == "idle"
    assert o.hours_since_push is None


def test_heavy_rhythm_makes_it_content_alone():
    o = parse(_with_presence("heavy", 1.0))
    biased = mood_bias(Mood(60, 50, 50, 30, 40), o)
    assert biased.comfort > 50


def test_long_quiet_gap_makes_it_attentive():
    o = parse(_with_presence("idle", 100.0))
    biased = mood_bias(Mood(60, 60, 40, 30, 40), o)
    assert biased.curiosity > 40


def test_busy_quip_tag():
    o = parse(_with_presence("heavy", 1.0))
    assert quip_tag(o) == "busy"
    assert is_busy(o) is True
    assert is_busy(parse(_with_presence("idle", 1.0))) is False


def test_cache_roundtrip_preserves_presence():
    o = parse(_with_presence("light", 4.5))
    o2 = unpack(pack(o))
    assert o2.coding_rhythm == "light"
    assert abs(o2.hours_since_push - 4.5) < 0.01


def _with_calendar(in_meeting=False, soon=False, load="light", free=True):
    return {
        "weather": {"tags": ["clear"], "temp_c": 25.0, "sunset_soon": False},
        "moon": {"phase": 2, "illum": 0.5},
        "calendar": {
            "in_meeting": in_meeting,
            "meeting_soon": soon,
            "day_load": load,
            "free_rest_of_day": free,
        },
    }


def test_parse_reads_calendar():
    o = parse(_with_calendar(in_meeting=True, load="heavy", free=False))
    assert o.cal_known is True
    assert o.in_meeting is True
    assert o.day_load == "heavy"
    assert o.free_rest is False


def test_parse_calendar_unknown_when_absent():
    o = parse(_payload(["clear"]))
    assert o.cal_known is False
    assert o.in_meeting is False
    assert o.day_load == "light"
    assert o.free_rest is True


def test_cache_roundtrip_preserves_calendar():
    o = parse(_with_calendar(in_meeting=True, soon=True, load="normal", free=False))
    o2 = unpack(pack(o))
    assert o2.cal_known is True
    assert o2.in_meeting is True
    assert o2.meeting_soon is True
    assert o2.day_load == "normal"
    assert o2.free_rest is False


def test_unpack_old_format_defaults_calendar_idle():
    import struct

    from slime.oracle import _FMT_OLD

    old = struct.pack(_FMT_OLD, 1, 4, 1, 30.0, 0.98, 2, 1.5)
    o = unpack(old)
    assert o.weather_tag == "storm_incoming"
    assert o.cal_known is False
    assert o.in_meeting is False
