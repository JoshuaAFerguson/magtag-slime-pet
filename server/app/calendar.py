"""Google Calendar (private ICS) -> privacy-safe day-presence signals. summarize() is pure."""

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import icalendar
import recurring_ical_events

_SOON_MIN = 15
_HEAVY = 4
_LIGHT = 1

CAL_IDLE = {
    "in_meeting": False,
    "meeting_soon": False,
    "day_load": "light",
    "free_rest_of_day": True,
}


def fetch_ics(client, url):
    """GET the private iCal feed; return the raw .ics bytes. `client` is an httpx.Client."""
    resp = client.get(url)
    resp.raise_for_status()
    return resp.content


def expand_today(ics_bytes, now, tz_name):
    """Parse + expand recurrences for the local calendar day containing `now`.

    Returns (start_utc, end_utc) pairs for TIMED events only (all-day events skipped).
    """
    cal = icalendar.Calendar.from_ical(ics_bytes)
    tz = ZoneInfo(tz_name)
    local_now = now.astimezone(tz)
    day_start = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start + timedelta(days=1)
    out = []
    for ev in recurring_ical_events.of(cal).between(day_start, day_end):
        start = ev.get("DTSTART").dt
        if not isinstance(start, datetime):  # all-day events have a date, not datetime
            continue
        end_field = ev.get("DTEND")
        end = end_field.dt if end_field is not None else start
        if not isinstance(end, datetime):
            continue
        if start.tzinfo is None:
            start = start.replace(tzinfo=tz)
        if end.tzinfo is None:
            end = end.replace(tzinfo=tz)
        out.append((start.astimezone(timezone.utc), end.astimezone(timezone.utc)))
    return out


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
