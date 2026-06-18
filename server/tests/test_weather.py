from app.weather import normalize


def _payload(temp, humidity, precip, precip_prob, sunset="2026-06-18T19:42"):
    return {
        "current": {
            "temperature_2m": temp,
            "relative_humidity_2m": humidity,
            "precipitation": precip,
            "weather_code": 0,
            "time": "2026-06-18T15:00",
        },
        "daily": {"precipitation_probability_max": [precip_prob], "sunset": [sunset]},
    }


def test_extreme_heat_tag():
    out = normalize(_payload(43, 10, 0, 0), now_iso="2026-06-18T15:00")
    assert "extreme_heat" in out["tags"]
    assert out["temp_c"] == 43


def test_storm_incoming_on_high_precip_probability():
    out = normalize(_payload(30, 60, 0, 80), now_iso="2026-06-18T15:00")
    assert "storm_incoming" in out["tags"]


def test_rain_when_currently_precipitating():
    out = normalize(_payload(24, 80, 1.2, 90), now_iso="2026-06-18T15:00")
    assert "rain" in out["tags"]


def test_cold_tag():
    out = normalize(_payload(2, 40, 0, 0), now_iso="2026-01-05T07:00")
    assert "cold" in out["tags"]


def test_clear_default():
    out = normalize(_payload(28, 15, 0, 5), now_iso="2026-06-18T11:00")
    assert out["tags"] == ["clear"]


def test_monsoon_tag_in_season():
    out = normalize(_payload(35, 55, 0, 65), now_iso="2026-07-15T10:00")
    assert "monsoon" in out["tags"]


def test_monsoon_not_out_of_season():
    out = normalize(_payload(25, 55, 0, 65), now_iso="2026-02-15T10:00")
    assert "monsoon" not in out["tags"]


def test_sunset_soon_flag():
    out = normalize(_payload(35, 15, 0, 0, sunset="2026-06-18T19:42"), now_iso="2026-06-18T19:20")
    assert out["sunset_soon"] is True
    out2 = normalize(_payload(35, 15, 0, 0, sunset="2026-06-18T19:42"), now_iso="2026-06-18T12:00")
    assert out2["sunset_soon"] is False
