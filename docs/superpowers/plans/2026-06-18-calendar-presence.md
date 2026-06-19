# Calendar Presence (Phase 2b-ii) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Google-Calendar-derived day presence (in_meeting / meeting_soon / day_load / free_rest_of_day) to the home oracle and the pet's mood, voice, and meeting-hush behavior — privacy-safe, offline-first.

**Architecture:** The FastAPI home server fetches a read-only private iCal feed, expands recurrences for today, and reduces it to four buckets in a new `calendar` block of `GET /oracle`. The device parses those buckets into its `Oracle`, biases mood, picks calendar quips, and hushes during meetings. Pure reduction logic (server `calendar.summarize`, device `oracle.parse`/effects) is host-tested; the calendar block is only emitted when an ICS URL is configured, and the device only applies calendar behavior when the block is present (`cal_known`).

**Tech Stack:** FastAPI + httpx (server), `icalendar` + `recurring-ical-events` (ICS parsing), pytest (host tests), CircuitPython (device), black + ruff line-length 100.

**Spec:** `docs/superpowers/specs/2026-06-18-calendar-presence-design.md`

**Conventions:**
- Pure modules import no hardware/network in their pure functions. `calendar.summarize` and all of `slime/oracle.py` stay pure (oracle's `save_cache`/`load_cache` import `microcontroller` lazily — keep that pattern).
- Run host tests with `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest` (a global pydantic pytest plugin otherwise errors at collection). A project `.venv` has black/ruff/pytest: `source .venv/bin/activate`.
- Server tests live in `server/tests/` and import `from app.X import ...` (run pytest from `server/`).
- Device tests live in `tests/` and import `from slime.X import ...` (run pytest from repo root).
- Repo is on branch `calendar-presence` (NOT main) — committing there is correct.

**Key design refinement (important):** The server emits a `calendar` block ONLY when `CALENDAR_ICS_URL` is set and the fetch succeeds; otherwise it omits the key entirely. The device sets `cal_known=True` only when the block is present, and gates ALL calendar mood/quip/hush behavior on `cal_known`. This prevents an unconfigured server's "free day" default from spamming clear-day quips, and keeps every existing test (which sends no calendar block) behaving exactly as before.

---

## File Structure

| File | Responsibility | Tested |
|------|----------------|--------|
| `server/app/calendar.py` (create) | `fetch_ics`, `expand_today` (impure, thin), `summarize` (pure) | `server/tests/test_calendar.py` |
| `server/app/config.py` (modify) | add `CALENDAR_ICS_URL` | — |
| `server/app/oracle.py` (modify) | `build(..., calendar=None, ...)` emits `calendar` when present | `server/tests/test_oracle.py` |
| `server/app/main.py` (modify) | `_calendar()` helper; pass into `build` | `server/tests/test_main.py` |
| `server/requirements.txt` (modify) | add `icalendar`, `recurring-ical-events` | — |
| `server/.env.example` (modify) | document `CALENDAR_ICS_URL` | — |
| `slime/oracle.py` (modify) | `Oracle` +5 fields, `parse`, `pack`/`unpack`, `mood_bias`, `quip_tag`, `is_in_meeting` | `tests/test_oracle_client.py` |
| `slime/quips.py` (modify) | 4 new quip pools | `tests/test_quips.py` |
| `code.py` (modify) | hush during meetings (no beep, dim pixels) | on-device |

---

## Task 1: Server — `calendar.summarize` (pure)

**Files:**
- Create: `server/app/calendar.py`
- Test: `server/tests/test_calendar.py`

- [ ] **Step 1: Write the failing tests**

Create `server/tests/test_calendar.py`:

```python
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
    # now == start -> in meeting; now == end -> not.
    assert summarize([(NOW, NOW + timedelta(minutes=30))], NOW)["in_meeting"] is True
    assert summarize([(NOW - timedelta(minutes=30), NOW)], NOW)["in_meeting"] is False


def test_meeting_soon_edge_and_suppressed_when_in_meeting():
    assert summarize([_ev(15)], NOW)["meeting_soon"] is True   # exactly 15 min
    assert summarize([_ev(16)], NOW)["meeting_soon"] is False  # just outside
    # in a meeting now AND another soon -> meeting_soon stays False (already in one)
    out = summarize([(NOW, NOW + timedelta(minutes=60)), _ev(10)], NOW)
    assert out["in_meeting"] is True
    assert out["meeting_soon"] is False


def test_day_load_thresholds():
    assert summarize([_ev(60)], NOW)["day_load"] == "light"            # 1
    assert summarize([_ev(60), _ev(120)], NOW)["day_load"] == "normal"  # 2
    assert summarize([_ev(60), _ev(120), _ev(180)], NOW)["day_load"] == "normal"  # 3
    assert summarize([_ev(i * 60) for i in range(1, 5)], NOW)["day_load"] == "heavy"  # 4


def test_free_rest_of_day():
    assert summarize([_ev(-120)], NOW)["free_rest_of_day"] is True   # only a past event
    assert summarize([_ev(120)], NOW)["free_rest_of_day"] is False   # a future event
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd server && PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest tests/test_calendar.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.calendar'`.

- [ ] **Step 3: Implement the pure reducer**

Create `server/app/calendar.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd server && PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest tests/test_calendar.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Lint + commit**

```bash
source .venv/bin/activate
black --line-length 100 server/app/calendar.py server/tests/test_calendar.py
ruff check server/app/calendar.py server/tests/test_calendar.py
git add server/app/calendar.py server/tests/test_calendar.py
git commit -m "feat: add calendar.summarize (pure day-presence reducer)"
```

---

## Task 2: Server — `fetch_ics` + `expand_today` (ICS parsing)

**Files:**
- Modify: `server/app/calendar.py`
- Modify: `server/requirements.txt`
- Test: `server/tests/test_calendar.py`

- [ ] **Step 1: Add the dependencies**

Append to `server/requirements.txt` (pinned):

```
icalendar==6.1.0
recurring-ical-events==3.3.4
```

Install into the venv so tests can import them:

```bash
source .venv/bin/activate
pip install "icalendar==6.1.0" "recurring-ical-events==3.3.4"
```

- [ ] **Step 2: Write the failing test (with an inline ICS fixture)**

Append to `server/tests/test_calendar.py`:

```python
from app.calendar import expand_today

_ICS = b"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//test//EN
BEGIN:VEVENT
UID:1
DTSTART:20260619T160000Z
DTEND:20260619T163000Z
SUMMARY:secret title
END:VEVENT
BEGIN:VEVENT
UID:2
DTSTART:20260101T170000Z
DTEND:20260101T173000Z
RRULE:FREQ=DAILY
SUMMARY:standup
END:VEVENT
BEGIN:VEVENT
UID:3
DTSTART;VALUE=DATE:20260619
DTEND;VALUE=DATE:20260620
SUMMARY:all day
END:VEVENT
END:VCALENDAR
"""


def test_expand_today_returns_timed_events_only():
    # Day window is 2026-06-19 in UTC. Expect the 16:00 one-off + the daily-recurring
    # 17:00 occurrence, and the all-day event excluded -> 2 timed intervals.
    intervals = expand_today(_ICS, NOW, "UTC")
    assert len(intervals) == 2
    starts = sorted(s.hour for s, _ in intervals)
    assert starts == [16, 17]
    # All returned datetimes are tz-aware UTC.
    for s, e in intervals:
        assert s.tzinfo is not None and e.tzinfo is not None
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd server && PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest tests/test_calendar.py::test_expand_today_returns_timed_events_only -v`
Expected: FAIL — `AttributeError: module 'app.calendar' has no attribute 'expand_today'`.

- [ ] **Step 4: Implement `fetch_ics` + `expand_today`**

Add to the TOP of `server/app/calendar.py` (imports) and then the two functions. Final import block:

```python
"""Google Calendar (private ICS) -> privacy-safe day-presence signals. summarize() is pure."""

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import icalendar
import recurring_ical_events
```

Add these functions (e.g. above `summarize`):

```python
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
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd server && PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest tests/test_calendar.py -v`
Expected: PASS (6 tests).

- [ ] **Step 6: Lint + commit**

```bash
source .venv/bin/activate
black --line-length 100 server/app/calendar.py server/tests/test_calendar.py
ruff check server/app/calendar.py server/tests/test_calendar.py
git add server/app/calendar.py server/tests/test_calendar.py server/requirements.txt
git commit -m "feat: fetch + expand today's timed calendar events from a private ICS feed"
```

---

## Task 3: Server — wire calendar into `/oracle`

**Files:**
- Modify: `server/app/config.py`, `server/app/oracle.py`, `server/app/main.py`, `server/.env.example`
- Test: `server/tests/test_oracle.py`, `server/tests/test_main.py`

- [ ] **Step 1: Write the failing tests**

In `server/tests/test_oracle.py`, append:

```python
def test_build_includes_calendar_when_present():
    cal = {"in_meeting": True, "meeting_soon": False,
           "day_load": "heavy", "free_rest_of_day": False}
    out = build({}, {}, {}, calendar=cal, ts=1)
    assert out["calendar"]["in_meeting"] is True


def test_build_omits_calendar_when_none():
    out = build({}, {}, {}, calendar=None, ts=1)
    assert "calendar" not in out
```

In `server/tests/test_main.py`, append:

```python
def test_oracle_includes_calendar_when_configured(monkeypatch):
    monkeypatch.setattr(main_mod.config, "CALENDAR_ICS_URL", "https://example/ics")
    monkeypatch.setattr(main_mod.calendar, "fetch_ics", lambda client, url: b"ICS")
    monkeypatch.setattr(
        main_mod.calendar, "expand_today", lambda body, now, tz: []
    )  # no events -> idle block, but the key must be present
    body = _client(monkeypatch).get("/oracle").json()
    assert "calendar" in body
    assert body["calendar"]["free_rest_of_day"] is True


def test_oracle_omits_calendar_without_url(monkeypatch):
    body = _client(monkeypatch).get("/oracle").json()
    assert "calendar" not in body
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd server && PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest tests/test_oracle.py tests/test_main.py -v`
Expected: FAIL — `build()` rejects `calendar=`; `main_mod.calendar` doesn't exist.

- [ ] **Step 3: Add the config var**

In `server/app/config.py`, after the `GITHUB_TOKEN` line:

```python
CALENDAR_ICS_URL = os.getenv("CALENDAR_ICS_URL", "")  # private iCal secret address; empty -> off
```

- [ ] **Step 4: Extend `build`**

Replace the body of `server/app/oracle.py`'s `build` with:

```python
def build(weather, moon, presence, calendar=None, ts=0):
    """Return the compact oracle payload served to the device.

    The `calendar` block is included only when present (calendar is not None)."""
    payload = {"weather": weather, "moon": moon, "presence": presence, "ts": ts}
    if calendar is not None:
        payload["calendar"] = calendar
    return payload
```

- [ ] **Step 5: Add `_calendar()` and wire it into `get_oracle`**

In `server/app/main.py`: add `calendar` to the imports line:

```python
from . import calendar, config, github, moon, oracle, weather
```

Add the helper (after `_presence`):

```python
def _calendar():
    """Derive the calendar block; None (omitted) on missing URL or any failure."""
    if not config.CALENDAR_ICS_URL:
        return None
    try:
        with httpx.Client(timeout=10) as client:
            body = calendar.fetch_ics(client, config.CALENDAR_ICS_URL)
        now = datetime.now(timezone.utc)
        intervals = calendar.expand_today(body, now, config.TZ)
        return calendar.summarize(intervals, now)
    except Exception:
        return None
```

Change the final return of `get_oracle` to pass the calendar block:

```python
    return oracle.build(w, mooninfo, _presence(), calendar=_calendar(), ts=int(time.time()))
```

- [ ] **Step 6: Document the env var**

In `server/.env.example`, add:

```
# Google Calendar private iCal "secret address" (read-only). Empty -> calendar presence off.
# Settings -> your calendar -> "Secret address in iCal format". Keep this file gitignored.
CALENDAR_ICS_URL=
```

- [ ] **Step 7: Run the full server suite**

Run: `cd server && PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q`
Expected: PASS (existing + new; the no-URL tests confirm the block is omitted by default).

- [ ] **Step 8: Lint + commit**

```bash
source .venv/bin/activate
black --line-length 100 server/app/config.py server/app/oracle.py server/app/main.py server/tests/test_oracle.py server/tests/test_main.py
ruff check server/app/config.py server/app/oracle.py server/app/main.py server/tests/test_oracle.py server/tests/test_main.py
git add server/app/config.py server/app/oracle.py server/app/main.py server/.env.example server/tests/test_oracle.py server/tests/test_main.py
git commit -m "feat: serve calendar presence block in /oracle when ICS URL configured"
```

---

## Task 4: Device — `Oracle` calendar fields, `parse`, cache format

**Files:**
- Modify: `slime/oracle.py`
- Test: `tests/test_oracle_client.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_oracle_client.py`:

```python
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
    assert o.free_rest is True  # idle default, but cal_known False gates behavior


def test_cache_roundtrip_preserves_calendar():
    o = parse(_with_calendar(in_meeting=True, soon=True, load="normal", free=False))
    o2 = unpack(pack(o))
    assert o2.cal_known is True
    assert o2.in_meeting is True
    assert o2.meeting_soon is True
    assert o2.day_load == "normal"
    assert o2.free_rest is False


def test_unpack_old_format_defaults_calendar_idle():
    # An old (pre-calendar) cache blob must still unpack, with calendar marked unknown.
    import struct

    from slime.oracle import _FMT_OLD

    old = struct.pack(_FMT_OLD, 1, 4, 1, 30.0, 0.98, 2, 1.5)  # storm, full moon, light rhythm
    o = unpack(old)
    assert o.weather_tag == "storm_incoming"
    assert o.cal_known is False
    assert o.in_meeting is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest tests/test_oracle_client.py -v`
Expected: FAIL — `Oracle` has no `cal_known`/`in_meeting`/etc.; `_FMT_OLD` missing.

- [ ] **Step 3: Extend the `Oracle` namedtuple**

In `slime/oracle.py`, replace the `Oracle = namedtuple(...)` definition with (append the 5 calendar fields):

```python
Oracle = namedtuple(
    "Oracle",
    (
        "weather_tag",
        "temp_c",
        "moon_phase",
        "moon_illum",
        "sunset_soon",
        "coding_rhythm",
        "hours_since_push",
        "in_meeting",
        "meeting_soon",
        "day_load",
        "free_rest",
        "cal_known",
    ),
)
```

- [ ] **Step 4: Add calendar constants + extend `parse`**

Add near the other module constants (after `_RHYTHM_IDS`/`_QUIET_GAP_HOURS`):

```python
_LOAD_IDS = ("light", "normal", "heavy")
_CAL_IDLE = {"in_meeting": False, "meeting_soon": False, "day_load": "light",
             "free_rest_of_day": True}
```

In `parse`, after the `p = payload.get("presence", {})` line, add:

```python
    cal = payload.get("calendar")
    cal_known = cal is not None
    c = cal if cal_known else _CAL_IDLE
```

And extend the returned `Oracle(...)` with the new keyword fields:

```python
    return Oracle(
        weather_tag=tag,
        temp_c=w.get("temp_c"),
        moon_phase=m.get("phase", 0),
        moon_illum=m.get("illum", 0.0),
        sunset_soon=bool(w.get("sunset_soon", False)),
        coding_rhythm=p.get("coding_rhythm", "idle"),
        hours_since_push=p.get("hours_since_push"),
        in_meeting=bool(c.get("in_meeting", False)),
        meeting_soon=bool(c.get("meeting_soon", False)),
        day_load=c.get("day_load", "light"),
        free_rest=bool(c.get("free_rest_of_day", True)),
        cal_known=cal_known,
    )
```

- [ ] **Step 5: Extend pack/unpack with backward compatibility**

Replace the format/size block and `pack`/`unpack`:

```python
_FMT_OLD = "<BBBffBf"  # pre-calendar layout (still readable for migration)
SIZE_OLD = struct.calcsize(_FMT_OLD)
# + flags byte (bit0 in_meeting, bit1 meeting_soon, bit2 free_rest, bit3 cal_known)
# + load byte (index into _LOAD_IDS)
_FMT = "<BBBffBfBB"
SIZE = struct.calcsize(_FMT)


def pack(oracle):
    """Pack an Oracle into binary form for NVM storage."""
    tag_id = _TAG_IDS.index(oracle.weather_tag) if oracle.weather_tag in _TAG_IDS else 0
    temp = oracle.temp_c if oracle.temp_c is not None else -999.0
    rhythm_id = (
        _RHYTHM_IDS.index(oracle.coding_rhythm) if oracle.coding_rhythm in _RHYTHM_IDS else 0
    )
    hours = oracle.hours_since_push if oracle.hours_since_push is not None else -1.0
    flags = (
        (0b0001 if oracle.in_meeting else 0)
        | (0b0010 if oracle.meeting_soon else 0)
        | (0b0100 if oracle.free_rest else 0)
        | (0b1000 if oracle.cal_known else 0)
    )
    load_id = _LOAD_IDS.index(oracle.day_load) if oracle.day_load in _LOAD_IDS else 0
    return struct.pack(
        _FMT,
        tag_id,
        oracle.moon_phase,
        1 if oracle.sunset_soon else 0,
        temp,
        oracle.moon_illum,
        rhythm_id,
        hours,
        flags,
        load_id,
    )


def _oracle_from(tag_id, phase, sunset, temp, illum, rhythm_id, hours,
                 in_meeting, meeting_soon, day_load, free_rest, cal_known):
    return Oracle(
        weather_tag=_TAG_IDS[tag_id] if tag_id < len(_TAG_IDS) else "clear",
        temp_c=None if temp < -900.0 else temp,
        moon_phase=phase,
        moon_illum=illum,
        sunset_soon=bool(sunset),
        coding_rhythm=_RHYTHM_IDS[rhythm_id] if rhythm_id < len(_RHYTHM_IDS) else "idle",
        hours_since_push=None if hours < 0.0 else hours,
        in_meeting=in_meeting,
        meeting_soon=meeting_soon,
        day_load=day_load,
        free_rest=free_rest,
        cal_known=cal_known,
    )


def unpack(blob):
    """Unpack binary form back into an Oracle. Old (pre-calendar) blobs read as cal unknown."""
    if len(blob) >= SIZE:
        tag_id, phase, sunset, temp, illum, rhythm_id, hours, flags, load_id = struct.unpack(
            _FMT, blob[:SIZE]
        )
        return _oracle_from(
            tag_id, phase, sunset, temp, illum, rhythm_id, hours,
            bool(flags & 0b0001), bool(flags & 0b0010),
            _LOAD_IDS[load_id] if load_id < len(_LOAD_IDS) else "light",
            bool(flags & 0b0100), bool(flags & 0b1000),
        )
    tag_id, phase, sunset, temp, illum, rhythm_id, hours = struct.unpack(_FMT_OLD, blob[:SIZE_OLD])
    return _oracle_from(
        tag_id, phase, sunset, temp, illum, rhythm_id, hours,
        False, False, "light", True, False,
    )
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest tests/test_oracle_client.py -v`
Expected: PASS (existing + 4 new). Existing tests are unaffected because the calendar fields default to idle/unknown when no `calendar` block is present.

- [ ] **Step 7: Lint + commit**

```bash
source .venv/bin/activate
black --line-length 100 slime/oracle.py tests/test_oracle_client.py
ruff check slime/oracle.py tests/test_oracle_client.py
git add slime/oracle.py tests/test_oracle_client.py
git commit -m "feat: parse + cache calendar presence fields on the device oracle"
```

---

## Task 5: Device — calendar mood bias, quips, `is_in_meeting`

**Files:**
- Modify: `slime/oracle.py`, `slime/quips.py`
- Test: `tests/test_oracle_client.py`, `tests/test_quips.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_oracle_client.py`:

```python
from slime.oracle import is_in_meeting


def test_in_meeting_calms_and_lowers_energy():
    o = parse(_with_calendar(in_meeting=True))
    biased = mood_bias(Mood(80, 50, 50, 30, 40), o)
    assert biased.energy < 80
    assert biased.comfort >= 50


def test_free_rest_makes_it_affectionate():
    o = parse(_with_calendar(in_meeting=False, free=True))
    biased = mood_bias(Mood(60, 60, 40, 30, 40), o)
    assert biased.affection > 30


def test_calendar_quip_tags_by_priority():
    assert quip_tag(parse(_with_calendar(soon=True))) == "meeting_soon"
    assert quip_tag(parse(_with_calendar(in_meeting=True))) == "in_meeting"
    assert quip_tag(parse(_with_calendar(load="heavy", free=False))) == "busy_calendar"
    assert quip_tag(parse(_with_calendar(free=True))) == "clear_calendar"


def test_calendar_silent_when_unknown():
    # No calendar block -> cal_known False -> no calendar quip, falls through to moon/None.
    assert quip_tag(parse(_payload(["clear"], phase=2))) is None


def test_is_in_meeting_gated_on_cal_known():
    assert is_in_meeting(parse(_with_calendar(in_meeting=True))) is True
    assert is_in_meeting(parse(_payload(["clear"]))) is False  # cal_known False
    assert is_in_meeting(None) is False
```

Append to `tests/test_quips.py` (create it if it does not exist, with this content):

```python
from slime.quips import QUIPS, pick


def test_calendar_pools_present_and_nonempty():
    for tag in ("meeting_soon", "in_meeting", "busy_calendar", "clear_calendar"):
        assert tag in QUIPS
        assert len(QUIPS[tag]) >= 1
        assert pick(tag) in QUIPS[tag]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest tests/test_oracle_client.py tests/test_quips.py -v`
Expected: FAIL — `is_in_meeting` missing; calendar quip tags/pools missing.

- [ ] **Step 3: Add calendar mood bias**

In `slime/oracle.py` `mood_bias`, insert before the final `return clamp_mood(Mood(**vals))` (gated on `cal_known`):

```python
    if oracle.cal_known:
        if oracle.in_meeting:
            vals["comfort"] += (75.0 - vals["comfort"]) * rate
            vals["energy"] += (30.0 - vals["energy"]) * rate
        if oracle.day_load == "heavy":
            for drive, target in {"comfort": 78.0, "affection": 60.0, "energy": 62.0}.items():
                vals[drive] += (target - vals[drive]) * rate
        if oracle.free_rest and not oracle.in_meeting:
            vals["affection"] += (68.0 - vals["affection"]) * rate
            vals["curiosity"] += (65.0 - vals["curiosity"]) * rate
        if oracle.meeting_soon:
            vals["curiosity"] += (70.0 - vals["curiosity"]) * rate
```

- [ ] **Step 4: Add calendar quip tags + `is_in_meeting`**

Replace `slime/oracle.py`'s `quip_tag` with this (weather first; calendar meeting states next; then sunset/moon; then coding; then day-load/free; then quiet):

```python
def quip_tag(oracle):
    """Weather/calendar/moon/coding quip pool tag, or None."""
    if oracle is None:
        return None
    if oracle.weather_tag in _QUIP:
        return _QUIP[oracle.weather_tag]
    if oracle.cal_known and oracle.meeting_soon:
        return "meeting_soon"
    if oracle.cal_known and oracle.in_meeting:
        return "in_meeting"
    if oracle.sunset_soon:
        return "sunset"
    if oracle.moon_phase == 4:
        return "full_moon"
    if oracle.moon_phase == 0:
        return "new_moon"
    if oracle.coding_rhythm in ("heavy", "light"):
        return "busy"
    if oracle.cal_known and oracle.day_load == "heavy":
        return "busy_calendar"
    if oracle.cal_known and oracle.free_rest:
        return "clear_calendar"
    if oracle.hours_since_push is not None and oracle.hours_since_push >= _QUIET_GAP_HOURS:
        return "quiet"
    return None
```

Add `is_in_meeting` (e.g. after `is_busy`):

```python
def is_in_meeting(oracle):
    """True only when calendar data is present and a meeting is happening now."""
    return oracle is not None and oracle.cal_known and oracle.in_meeting
```

- [ ] **Step 5: Add the quip pools**

In `slime/quips.py`, add four entries to the `QUIPS` dict (before the closing brace, after `"quiet"`):

```python
    "meeting_soon": (
        "something starts soon",
        "your day is about to turn",
        "i'll keep quiet in a moment",
    ),
    "in_meeting": (
        "i'll be still for now",
        "go on, i'm listening too",
        "quiet company while you talk",
    ),
    "busy_calendar": (
        "a full day ahead",
        "so many moments booked",
        "i'll wait between your meetings",
    ),
    "clear_calendar": (
        "the day is open",
        "nothing pulls you away",
        "all this time is yours",
    ),
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest tests/test_oracle_client.py tests/test_quips.py -v`
Expected: PASS. Re-run the full device suite to confirm no regression:
`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q` → all pass.

- [ ] **Step 7: Lint + commit**

```bash
source .venv/bin/activate
black --line-length 100 slime/oracle.py slime/quips.py tests/test_oracle_client.py tests/test_quips.py
ruff check slime/oracle.py slime/quips.py tests/test_oracle_client.py tests/test_quips.py
git add slime/oracle.py slime/quips.py tests/test_oracle_client.py tests/test_quips.py
git commit -m "feat: calendar mood bias, quips, and is_in_meeting on the device oracle"
```

---

## Task 6: Device — hush during meetings in `code.py`

**Files:**
- Modify: `code.py`

Device-only entry point (cannot import on host). Gate: `python3 -c "import ast; ast.parse(open('code.py').read()); print('ok')"`. READ `code.py` first. The USB continuous loop currently: computes `sleeping` each iteration; plays the greeting motif when `sound and state.behavior == "greeting"`; and breathes pixels at `rate=0.05` when sleeping else an energy-scaled rate. You will add an `in_meeting` flag that (a) suppresses the greeting beep and (b) dims pixels like sleep.

- [ ] **Step 1: Compute `in_meeting` each iteration**

In the USB `while True` loop, right after the line that updates `sleeping` (`sleeping = statusbar.is_sleep_mode(inputs.light, sleeping)`), add:

```python
            in_meeting = oracle_mod.is_in_meeting(oracle)
```

(`oracle_mod` is already imported as `from slime import oracle as oracle_mod`.)

- [ ] **Step 2: Suppress the greeting beep during a meeting**

In the event-handling block, change the greeting sound condition from:

```python
                if sound and state.behavior == "greeting":
                    sound.play(pick_motif("greeting", ftier))
```

to:

```python
                if sound and state.behavior == "greeting" and not in_meeting:
                    sound.play(pick_motif("greeting", ftier))
```

- [ ] **Step 3: Dim pixels during a meeting**

Change the end-of-loop pixel breath from:

```python
            if pixels:
                if sleeping:
                    pixels.breathe(state.mood, time.monotonic() - t0, rate=0.05)
                else:
                    rate = 0.12 + (state.mood.energy / 100.0) * 0.35
                    pixels.breathe(state.mood, time.monotonic() - t0, rate=rate)
```

to:

```python
            if pixels:
                if sleeping or in_meeting:
                    pixels.breathe(state.mood, time.monotonic() - t0, rate=0.05)
                else:
                    rate = 0.12 + (state.mood.energy / 100.0) * 0.35
                    pixels.breathe(state.mood, time.monotonic() - t0, rate=rate)
```

- [ ] **Step 4: Offline gate**

Run: `python3 -c "import ast; ast.parse(open('code.py').read()); print('ok')"`
Expected: `ok`.

- [ ] **Step 5: Full host suite (code.py not imported by host tests; guard test scans modules)**

Run: `source .venv/bin/activate && PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q`
Expected: all pass.

- [ ] **Step 6: Lint + commit**

```bash
black --line-length 100 code.py
ruff check code.py
git add code.py
git commit -m "feat: hush the pet during calendar meetings (no greeting beep, dim pixels)"
```

- [ ] **Step 7: On-device + live-server verification**

1. Put `CALENDAR_ICS_URL` (your Google private iCal secret address) in `server/.env`; `docker compose up -d --build` the server so `/oracle` now returns a `calendar` block (verify: `curl http://192.168.0.38:8080/oracle` shows `"calendar": {...}`).
2. Deploy `code.py` + `slime/` to `CIRCUITPY`.
3. During a real (or test) calendar event: confirm the greeting beep is suppressed on a double-tap and NeoPixels stay dim; confirm calendar quips appear (busy/clear/soon) on scheduled refreshes; confirm with no `CALENDAR_ICS_URL` set the pet behaves exactly as before (no calendar quips).

---

## Self-Review

**Spec coverage:**
- Private ICS data source → Task 2 `fetch_ics` + Task 3 `CALENDAR_ICS_URL`. ✓
- `summarize` four signals with thresholds (15 min / load 1·3·4 / boundaries) → Task 1. ✓
- Recurring expansion + timed-only (all-day ignored) → Task 2 `expand_today`. ✓
- Calendar block only when configured; omitted otherwise → Task 3 `_calendar()` returns None, `build` omits. ✓
- Device `Oracle` +fields, parse, cache format (+backward compat), state stays v3 → Task 4. ✓
- Mood bias (in_meeting/heavy/free/soon), quips, `is_in_meeting`, gated on `cal_known` → Task 5. ✓
- Hush during meetings (no beep + dim pixels) → Task 6. ✓
- Privacy (only buckets leave Pi) → server never serializes titles; Tasks 1–3 only emit buckets. ✓
- Offline-first / idle fallback → Task 3 None-on-failure, Task 4 old-format + absent-block defaults. ✓
- Testing on both tiers → Tasks 1–5 host tests; Task 6 on-device. ✓

**Placeholder scan:** No TBD/TODO; every code step has full code. ✓

**Type consistency:** Server payload key `free_rest_of_day` maps to device `Oracle.free_rest` (parse reads `c.get("free_rest_of_day")`). `day_load` strings `"light"/"normal"/"heavy"` consistent across `summarize`, `_LOAD_IDS`, parse, pack/unpack, mood_bias, quip_tag. `cal_known` set in parse and both unpack paths. `build(weather, moon, presence, calendar=None, ts=0)` matches the `main.py` keyword call and the existing `build(..., ts=...)` test. `is_in_meeting` defined Task 5, used Task 6. New quip tags (`meeting_soon`/`in_meeting`/`busy_calendar`/`clear_calendar`) returned by `quip_tag` (Task 5) all exist as pools in `quips.py` (Task 5 Step 5). ✓
