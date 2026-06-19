# Calendar Presence (Phase 2b-ii) — Design

**Date:** 2026-06-18
**Status:** Approved (design); pending spec review

## Goal

Give the Slime Pet ambient awareness of the user's day from their Google Calendar:
whether they are in a meeting now, whether one starts soon, how loaded the day is, and
whether the rest of the day is free — surfaced as mood bias, quips, and a "hush during
meetings" behavior. Only derived buckets ever leave the home server; no event content
reaches the device.

## Motivation

The pet already blends weather, moon, and GitHub coding-rhythm into its mood and voice via
the home oracle. Calendar is the next natural presence signal: it lets the companion be
unobtrusive during calls, sympathetic on heavy days, and playful on free evenings. It also
properly fixes the "it beeped during a meeting" incident — the sound was made greeting-only
as a blunt fix; now the pet can actually *know* it is a meeting and stay quiet.

## Decisions (locked)

- **Data source:** Google Calendar's **private "secret address in iCal format"** — a
  read-only HTTPS `.ics` feed. No OAuth, no token refresh, no write access. The secret URL
  lives in a gitignored `server/.env` (`CALENDAR_ICS_URL`).
- **Signals (derived, privacy-safe):** `in_meeting`, `meeting_soon`, `day_load`
  (light/normal/heavy), `free_rest_of_day`.
- **Manifestation:** mood bias + calendar quips + hush-during-meetings. **No status-bar
  element** (keeps parity with GitHub presence; no new visual scope).
- **Parsing:** `icalendar` + `recurring-ical-events` so recurring meetings expand into
  today's real occurrences. Only **timed** events count; all-day events are ignored for all
  four signals.
- **Signal thresholds (tunable):**
  - `in_meeting`: `now` falls within a timed event's `[start, end)`.
  - `meeting_soon`: the next timed event starts within **15 minutes** (and not already in a
    meeting).
  - `day_load`: by count of today's timed events — `light` ≤ 1, `normal` 2–3, `heavy` ≥ 4.
  - `free_rest_of_day`: no timed event remains today with a start ≥ `now`.
- **Privacy:** only the four buckets are serialized into the oracle payload — never titles,
  locations, descriptions, or attendees.

## Architecture

The two-tier split is preserved. The home server (FastAPI, Docker) does all calendar I/O
and reduces it to buckets; the device consumes only the buckets, caches them in NVM, and
reacts offline-first. Pure reduction logic is host-tested on both tiers, mirroring the
existing `github.summarize` / `oracle.parse` pattern.

### Server: `server/app/calendar.py` (new)

Mirrors `server/app/github.py`.

- `fetch_ics(client, url) -> bytes` — `client.get(url)`, `raise_for_status()`, returns the
  raw `.ics` body. `client` is an `httpx.Client`.
- `expand_today(ics_bytes, now, tz) -> list[tuple[datetime, datetime]]` — parse with
  `icalendar`, expand recurrences for the local calendar day containing `now` using
  `recurring-ical-events`, and return `(start_utc, end_utc)` pairs for **timed** events
  only (skip events whose `DTSTART` is a date, i.e. all-day). Impure (library calls) but
  thin; the heavy logic is in `summarize`.
- `summarize(intervals, now) -> dict` — **pure**. Input is a list of `(start, end)`
  tz-aware datetimes plus tz-aware `now`. Returns:
  ```python
  {
      "in_meeting": bool,
      "meeting_soon": bool,            # next start within 15 min, and not in_meeting
      "day_load": "light" | "normal" | "heavy",
      "free_rest_of_day": bool,
  }
  ```
  Constants: `_SOON_MIN = 15`, `_HEAVY = 4`, `_LIGHT = 1`.

`day_load` counts the intervals passed in (already scoped to today by `expand_today`).
`free_rest_of_day` is true when no interval has `start >= now`. `meeting_soon` is true when
the soonest future start is within `_SOON_MIN` minutes and `in_meeting` is false.

### Server: wiring

- `server/app/config.py`: add `CALENDAR_ICS_URL = os.getenv("CALENDAR_ICS_URL", "")`.
- `server/app/main.py`: add a `_calendar()` helper mirroring `_presence()` — returns the
  empty/idle block on missing URL or any exception:
  ```python
  _CAL_IDLE = {"in_meeting": False, "meeting_soon": False,
               "day_load": "light", "free_rest_of_day": True}

  def _calendar():
      if not config.CALENDAR_ICS_URL:
          return dict(_CAL_IDLE)
      try:
          with httpx.Client(timeout=10) as client:
              body = calendar.fetch_ics(client, config.CALENDAR_ICS_URL)
          now = datetime.now(timezone.utc)
          intervals = calendar.expand_today(body, now, config.TZ)
          return calendar.summarize(intervals, now)
      except Exception:
          return dict(_CAL_IDLE)
  ```
  `get_oracle` passes the new block through `oracle.build`.
- `server/app/oracle.py`: `build(weather, moon, presence, calendar, ts)` adds a
  `"calendar"` key. (One new positional arg; `main.py` is its only caller.)
- `server/requirements.txt`: add `icalendar` and `recurring-ical-events` (pinned).
- `server/.env.example`: document `CALENDAR_ICS_URL=` with a comment that it is the private
  iCal secret address and must stay gitignored.

### Device: `slime/oracle.py` (extend)

- `Oracle` namedtuple gains four fields: `in_meeting` (bool), `meeting_soon` (bool),
  `day_load` (str: "light"/"normal"/"heavy"), `free_rest` (bool).
- `parse(payload)` reads `payload["calendar"]` (defaulting to the idle block when absent),
  populating the new fields.
- `pack`/`unpack`: the cache format `<BBBffBf` is extended with **one flags byte** (bit0
  in_meeting, bit1 meeting_soon, bit2 free_rest) and **one load byte** (0 light / 1 normal /
  2 heavy) → new format `<BBBffBfBB`. This lives in the existing offset-512 oracle cache
  slot; the persistent **state blob stays v3** (oracle cache is its own ephemeral slot).
  Backward read: if a shorter (old-format) blob is read, default the calendar fields to
  idle rather than failing.
- `mood_bias(mood, oracle)`: add calendar nudges blended at the same `rate`:
  - `in_meeting` → toward calm/quiet (raise comfort, lower energy).
  - `day_load == "heavy"` → independent/proud (reuse the heavy-rhythm target shape:
    comfort/affection/energy up modestly).
  - `free_rest` (and not in_meeting) → playful & affectionate (curiosity/affection up).
  - `meeting_soon` → attentive (curiosity up).
- `quip_tag(oracle)`: extend the priority chain with calendar tags — `meeting_soon` →
  `"meeting_soon"`; `in_meeting` → `"in_meeting"`; `day_load == "heavy"` →
  `"busy_calendar"`; `free_rest` → `"clear_calendar"`. Weather/moon keep their existing
  priority; calendar slots in after weather/sunset/moon and around the existing busy/quiet
  coding tags (exact ordering specified in the plan).
- `is_in_meeting(oracle) -> bool` — small helper for `code.py`'s hush logic.

### Device: `slime/quips.py`

Add four quip pools: `meeting_soon`, `in_meeting`, `busy_calendar`, `clear_calendar`
(several short lines each, matching the tone of existing pools).

### Device: `code.py` — hush during meetings

When `oracle_mod.is_in_meeting(oracle)` is true:
- Suppress the greeting beep (skip `sound.play(...)` in the greeting branch).
- Dim the NeoPixels (use a low breathe rate / reduced brightness, similar to the sleep
  breath) so a live call isn't distracted by a bright pulsing pet.

This composes with the existing greeting-only sound rule and the new sleep-mode dimming.

## Data Flow

```
private .ics URL ─> calendar.fetch_ics ─> calendar.expand_today (icalendar + recurring) ─>
   [(start,end), ...] today, timed only ─> calendar.summarize(now) ─>
   {in_meeting, meeting_soon, day_load, free_rest_of_day}
        └─> oracle.build(..., calendar, ts) ─> GET /oracle JSON
                                   │
   device netoracle.fetch ─> oracle.parse ─> Oracle(+4 calendar fields) ─> NVM cache(512)
        ├─> oracle.mood_bias ─> mood
        ├─> oracle.quip_tag  ─> voice
        └─> oracle.is_in_meeting ─> code.py hush (no beep, dim pixels)
```

## Error Handling / Offline-First

- Missing `CALENDAR_ICS_URL`, fetch failure, or parse failure → server returns the idle
  calendar block (`in_meeting/meeting_soon/free_rest_of_day` false-ish, `day_load` light,
  `free_rest_of_day` true) → pet behaves exactly as today.
- Device offline → uses the cached oracle (now including calendar fields); an old-format
  cache reads calendar as idle.
- All calendar fields are optional in `parse`; the device never assumes the block exists.

## Testing

**Server (CI `server` job, host pytest):**
- `calendar.summarize` (pure): in_meeting boundary (now == start is in; now == end is out),
  meeting_soon at the 15-min edge (inside/outside), meeting_soon suppressed while
  in_meeting, day_load thresholds (0/1 → light, 2/3 → normal, 4+ → heavy), free_rest_of_day
  true/false, empty list → idle.
- `calendar.expand_today` against a small synthetic `.ics` fixture: a single timed event, a
  recurring (RRULE) event expanding to one occurrence today, an all-day event ignored.
- `main`/`oracle.build`: payload includes a `calendar` block; `_calendar()` returns idle
  when `CALENDAR_ICS_URL` is unset (monkeypatched).

**Device (CI `check` job, host pytest):**
- `oracle.parse` reads the calendar block (and defaults to idle when absent).
- `pack`/`unpack` round-trip including the new flags+load bytes; old-format blob → idle.
- `mood_bias` shifts as specified per signal; `quip_tag` returns the calendar tags in the
  defined priority; `is_in_meeting` true/false.
- New quip pools are non-empty (existing quip-pool test style).
- `code.py` stays device-only (not host-imported); hush behavior is verified on-device.

## Scope Guard (YAGNI)

- No status-bar changes, no OAuth, no service account.
- No new device NVM **state** fields (state stays v3); only the ephemeral oracle cache
  format grows.
- No event content (titles/locations/attendees) stored or transmitted anywhere.
- Single calendar (the one private ICS URL); multi-calendar merge is out of scope.

## Files Touched

- Create: `server/app/calendar.py`, `server/tests/test_calendar.py`
- Modify: `server/app/config.py`, `server/app/main.py`, `server/app/oracle.py`,
  `server/requirements.txt`, `server/.env.example`, `server/tests/test_main.py` (calendar
  block present)
- Modify: `slime/oracle.py` (+ `tests/test_oracle_client.py`), `slime/quips.py`
  (+ its test), `code.py`
