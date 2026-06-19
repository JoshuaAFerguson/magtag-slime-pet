"""Google Calendar (private ICS) -> privacy-safe day-presence signals. summarize() is pure."""

from datetime import timedelta

_SOON_MIN = 15
_HEAVY = 4
_LIGHT = 1

CAL_IDLE = {
    "in_meeting": False,
    "meeting_soon": False,
    "day_load": "light",
    "free_rest_of_day": True,
}


def summarize(intervals, now):
    """Pure: list of (start, end) tz-aware datetimes (today, timed only) + tz-aware `now`
    -> {in_meeting, meeting_soon, day_load, free_rest_of_day}."""
    in_meeting = any(s <= now < e for s, e in intervals)
    future_starts = sorted(s for s, _ in intervals if s >= now)
    free_rest = not future_starts
    meeting_soon = False
    if not in_meeting and future_starts:
        meeting_soon = (future_starts[0] - now) <= timedelta(minutes=_SOON_MIN)
    count = len(intervals)
    if count >= _HEAVY:
        load = "heavy"
    elif count <= _LIGHT:
        load = "light"
    else:
        load = "normal"
    return {
        "in_meeting": in_meeting,
        "meeting_soon": meeting_soon,
        "day_load": load,
        "free_rest_of_day": free_rest,
    }
