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
