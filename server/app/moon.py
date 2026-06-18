"""Pure moon-phase math from a civil date. No external dependencies."""

import math

_SYNODIC = 29.53058867  # mean synodic month, days
_REF_NEW_MOON_JD = 2451550.1  # JD of the 2000-01-06 new moon
_NAMES = (
    "new",
    "waxing crescent",
    "first quarter",
    "waxing gibbous",
    "full",
    "waning gibbous",
    "last quarter",
    "waning crescent",
)


def _julian_day(year, month, day):
    if month <= 2:
        year -= 1
        month += 12
    a = year // 100
    b = 2 - a + a // 4
    return int(365.25 * (year + 4716)) + int(30.6001 * (month + 1)) + day + b - 1524.5


def phase_fraction(year, month, day):
    """Position in the lunar cycle, 0.0 (new) .. ~0.5 (full) .. 1.0 (new again)."""
    days = _julian_day(year, month, day) - _REF_NEW_MOON_JD
    return (days / _SYNODIC) % 1.0


def moon(year, month, day):
    """Return {phase: 0-7, name: str, illum: 0..1} for the date."""
    frac = phase_fraction(year, month, day)
    illum = (1.0 - math.cos(2.0 * math.pi * frac)) / 2.0
    phase = int(round(frac * 8)) % 8
    return {"phase": phase, "name": _NAMES[phase], "illum": round(illum, 3)}
