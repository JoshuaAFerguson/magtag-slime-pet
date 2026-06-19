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
    """Whole-degree Fahrenheit from the oracle's Celsius temp, '' if unknown.

    Renders as e.g. '94F' — the built-in terminalio.FONT is ASCII-only and has no
    degree glyph (U+00B0), so a literal '°' would silently drop on the device.
    """
    if oracle is None or oracle.temp_c is None:
        return ""
    return f"{round(oracle.temp_c * 9 / 5 + 32)}F"


def battery_str(frac: float) -> str:
    """Battery percentage from a 0..1 fraction, clamped, e.g. '84%'."""
    pct = round(max(0.0, min(1.0, frac)) * 100)
    return f"{pct}%"


# --- Tile indices into assets/statusicons.bmp (12x12 tiles, left to right) ---
ICON_CLEAR = 0  # sun
ICON_CLOUD = 1  # cloud (cold / overcast)
ICON_RAIN = 2
ICON_STORM = 3
ICON_HEAT = 4
ICON_MOON = 5
WIFI_LIVE = 6  # connected
WIFI_STALE = 7  # disconnected / cached

_WEATHER_ICON = {
    "clear": ICON_CLEAR,
    "cold": ICON_CLOUD,
    "rain": ICON_RAIN,
    "storm_incoming": ICON_STORM,
    "monsoon": ICON_STORM,
    "extreme_heat": ICON_HEAT,
}

_SLEEP_ENTER = 0.08  # below this (while awake) -> enter sleep
_SLEEP_EXIT = 0.15  # at/above this (while asleep) -> wake
_USB_REFRESH = 300.0
_BATTERY_REFRESH = 900.0


def weather_icon(oracle) -> int | None:
    """Tile index for the oracle's weather (or notable moon on a clear sky);
    None if no oracle.
    """
    if oracle is None:
        return None
    if oracle.weather_tag == "clear" and oracle.moon_phase in (0, 4):
        return ICON_MOON
    return _WEATHER_ICON.get(oracle.weather_tag, ICON_CLEAR)


def refresh_interval(on_usb: bool, sleeping: bool) -> float | None:
    """Seconds between scheduled repaints; None disables refresh (sleep mode)."""
    if sleeping:
        return None
    return _USB_REFRESH if on_usb else _BATTERY_REFRESH


def is_sleep_mode(light: float, currently_sleeping: bool) -> bool:
    """Whether the pet should be in dark 'sleep mode', with hysteresis to
    avoid flicker.
    """
    if currently_sleeping:
        return light < _SLEEP_EXIT
    return light < _SLEEP_ENTER
