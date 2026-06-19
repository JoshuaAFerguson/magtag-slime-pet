"""Tests for status-bar text formatters: time, date, temperature, battery."""

from collections import namedtuple

from slime import statusbar

# Minimal oracle stand-in matching slime.oracle.Oracle's used fields.
Ora = namedtuple("Ora", ("weather_tag", "temp_c", "moon_phase"))


def test_clock_12h_midnight_and_noon():
    assert statusbar.clock_12h(0, 0.0) == "12:00 AM"  # 00:00
    assert statusbar.clock_12h(45000, 0.0) == "12:30 PM"  # 12:30


def test_clock_12h_morning_and_evening():
    assert statusbar.clock_12h(3660, 0.0) == "1:01 AM"  # 01:01
    assert statusbar.clock_12h(45000 + 3600, 0.0) == "1:30 PM"  # 13:30


def test_short_date_formats_month_abbrev_and_day():
    # 1781740800 = 2026-06-18 00:00:00 UTC
    assert statusbar.short_date(1781740800, 0.0) == "Jun 18"


def test_temp_str_converts_celsius_to_whole_fahrenheit():
    assert statusbar.temp_str(Ora("clear", 0.0, 1)) == "32°"
    assert statusbar.temp_str(Ora("extreme_heat", 38.9, 1)) == "102°"
    assert statusbar.temp_str(Ora("cold", -10.0, 1)) == "14°"


def test_temp_str_blank_when_missing():
    assert statusbar.temp_str(None) == ""
    assert statusbar.temp_str(Ora("clear", None, 1)) == ""


def test_battery_str_rounds_and_clamps():
    assert statusbar.battery_str(0.84) == "84%"
    assert statusbar.battery_str(1.0) == "100%"
    assert statusbar.battery_str(0.0) == "0%"
    assert statusbar.battery_str(1.5) == "100%"
    assert statusbar.battery_str(-0.2) == "0%"


def test_weather_icon_maps_known_tags():
    assert statusbar.weather_icon(Ora("clear", 30.0, 1)) == statusbar.ICON_CLEAR
    assert statusbar.weather_icon(Ora("cold", 5.0, 1)) == statusbar.ICON_CLOUD
    assert statusbar.weather_icon(Ora("rain", 18.0, 1)) == statusbar.ICON_RAIN
    assert statusbar.weather_icon(Ora("storm_incoming", 25.0, 1)) == statusbar.ICON_STORM
    assert statusbar.weather_icon(Ora("monsoon", 25.0, 1)) == statusbar.ICON_STORM
    assert statusbar.weather_icon(Ora("extreme_heat", 44.0, 1)) == statusbar.ICON_HEAT


def test_weather_icon_shows_moon_on_clear_notable_phase():
    # Clear sky + new (0) or full (4) moon -> moon glyph instead of sun.
    assert statusbar.weather_icon(Ora("clear", 20.0, 4)) == statusbar.ICON_MOON
    assert statusbar.weather_icon(Ora("clear", 20.0, 0)) == statusbar.ICON_MOON


def test_weather_icon_none_when_no_oracle():
    assert statusbar.weather_icon(None) is None


def test_wifi_constants_distinct():
    assert statusbar.WIFI_LIVE != statusbar.WIFI_STALE


def test_refresh_interval_by_state():
    assert statusbar.refresh_interval(on_usb=True, sleeping=False) == 300.0
    assert statusbar.refresh_interval(on_usb=False, sleeping=False) == 900.0
    assert statusbar.refresh_interval(on_usb=True, sleeping=True) is None
    assert statusbar.refresh_interval(on_usb=False, sleeping=True) is None


def test_is_sleep_mode_hysteresis_entering():
    # Not currently sleeping: only very dark (< 0.08) enters sleep.
    assert statusbar.is_sleep_mode(0.05, currently_sleeping=False) is True
    assert statusbar.is_sleep_mode(0.10, currently_sleeping=False) is False
    assert statusbar.is_sleep_mode(0.20, currently_sleeping=False) is False


def test_is_sleep_mode_hysteresis_holding_and_waking():
    # Already sleeping: stays asleep through the dead band, wakes only above 0.15.
    assert statusbar.is_sleep_mode(0.10, currently_sleeping=True) is True
    assert statusbar.is_sleep_mode(0.14, currently_sleeping=True) is True
    assert statusbar.is_sleep_mode(0.20, currently_sleeping=True) is False
