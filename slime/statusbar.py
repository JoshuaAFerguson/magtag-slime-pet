"""Pure status-bar formatting + refresh/sleep decisions. No hardware imports."""

from slime import timekeeping


def clock_12h(epoch: int, tz_offset_hours: float) -> str:
    """Local time as a 12-hour string, e.g. '3:45 PM'."""
    hh, mm, _ = timekeeping.hms_from_epoch(epoch, tz_offset_hours)
    suffix = "AM" if hh < 12 else "PM"
    h12 = hh % 12 or 12
    return f"{h12}:{mm:02d} {suffix}"


def short_date(epoch: int, tz_offset_hours: float) -> str:
    """Local date as 'Mon D', e.g. 'Jun 18'."""
    _, month, day = timekeeping.civil_from_epoch(epoch, tz_offset_hours)
    return f"{timekeeping.MONTH_ABBR[month - 1]} {day}"


def temp_str(oracle) -> str:
    """Whole-degree Fahrenheit from the oracle's Celsius temp, '' if unknown."""
    if oracle is None or oracle.temp_c is None:
        return ""
    return f"{round(oracle.temp_c * 9 / 5 + 32)}°"


def battery_str(frac: float) -> str:
    """Battery percentage from a 0..1 fraction, clamped, e.g. '84%'."""
    pct = round(max(0.0, min(1.0, frac)) * 100)
    return f"{pct}%"
