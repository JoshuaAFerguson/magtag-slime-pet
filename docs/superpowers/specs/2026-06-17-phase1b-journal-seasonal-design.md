# Slime Pet — Phase 1b: Journal & Seasonal (Design)

**Date:** 2026-06-17
**Status:** Approved (design)
**Scope:** Phase 1b — a network-time foundation, a daily journal, and seasonal behavior.
**Builds on:** Phase 0 (Local Soul) and Phase 1a (forms, friendship, sound, dreams).

---

## Context

Phase 1a deferred Journal and Seasonal because they need a real calendar date and the device has no
RTC. Rather than wait for the RTC add-on (Phase 3), Phase 1b adds a lightweight **NTP-over-WiFi**
time sync (the project's first "online" capability, distinct from the Phase 2 cloud oracle) with
graceful offline fallback, then builds the journal and seasonal features on top.

## Locked Decisions

| Area | Choice |
|---|---|
| Time source | NTP over WiFi; offline-first fallback to last-known/elapsed |
| Timezone | Phoenix UTC−7, no DST; overridable in `settings.toml` |
| Journal storage | Compact per-day records in an NVM ring; text **regenerated** from the record |
| Journal archive | Full readable history deferred to the Phase 2 cloud |
| Seasonal | Mood/quip bias + seasonal **form** (calm moods) + always-on corner **accent** |
| Persistence | NVM-only; state blob bumped v2 → v3 with v1/v2 migration |

---

## Architecture

Same pure/adapter discipline as before.

### New pure modules (host-tested)
- `slime/timekeeping.py` — `now_epoch(synced_epoch, mono_at_sync, mono_now)`,
  `civil_from_epoch(epoch, tz_offset)` → (year, month, day), `day_ordinal(epoch, tz_offset)`,
  `is_new_day(prev_ordinal, current_ordinal)`. Pure integer math; no hardware.
- `slime/seasons.py` — `season_of(month)` → spring/summer/autumn/winter; `bias(season)` → small
  per-drive mood deltas; `accent_frame(season)`, `form_frame(season)`; seasonal quip tags.
- `slime/journal.py` — `pack_record`/`unpack_record` for a compact day-record; ring-buffer
  `append`/`entries` over a `bytes` buffer (pure); `generate_entry(record, choice)` → the day's
  short lines (generate-from-seed, like dreams).

### New adapter (device-only)
- `slime/nettime.py` — connect WiFi using `settings.toml` creds, fetch NTP, return an epoch int.
  Returns `None` on missing creds / no WiFi / failure (offline-first; never raises into the loop).

### Extended modules
- `slime/forms.py` — `choose_render` gains a `season` param: a seasonal form shows in calm/neutral
  moods, after the mood forms (loaf/puddle/wisp/explorer/crowned still take priority).
- `slime/visuals.py` — `POSE_INDEX` gains 4 seasonal form frames; a new `ACCENT_INDEX` maps seasons
  to corner-accent frames.
- `slime/display.py` — draw a small **seasonal accent** in the top-right corner; add a **journal
  screen** render (a few short lines).
- `slime/persistence.py` — NVM **v3**: adds `last_journal_day_ordinal`; migrates v1 and v2 forward.
- `code.py` — boot flow: attempt NTP sync → derive season (bias mood, pick form + accent) → detect a
  new day → append a journal record and show the journal screen.

### Config & assets
- `settings.toml` on the device holds `WIFI_SSID`, `WIFI_PASSWORD`, `TZ_OFFSET` (default −7). It is
  **gitignored**; the repo ships a `settings.toml.example`.
- `assets/make_assets.py` grows the sprite sheet with 4 seasonal form frames; accents are small
  frames (in the main sheet or a small accent sheet).

## Time Foundation (offline-first)

- On boot, and at most once per day, the slime tries an NTP sync via `nettime`. A successful sync
  records `synced_epoch` and `monotonic()` at that moment.
- Current wall-clock = `synced_epoch + (monotonic_now − monotonic_at_sync)`.
- **Honest limitation:** with no RTC, a power loss/deep-sleep wake resets `monotonic`, so the date is
  only "live" once a sync succeeds in the current power-cycle. If offline at boot, time-dependent
  features (journal, season) **wait** until a sync happens — the slime stays fully alive meanwhile and
  never fabricates a date.
- **Power:** on USB it syncs on boot + daily. On battery it uses last-known time and skips WiFi to
  conserve power.

## Journal (NVM compact records, regenerated text)

- When the synced date advances to a **new day** (current day-ordinal > `last_journal_day_ordinal`),
  the slime appends a compact day-record (~8 bytes: day ordinal, dominant mood, season, event flags,
  familiarity tier) to an **NVM ring buffer** in a fixed region after the state blob (~48 days kept).
- The entry **text is regenerated** from the record on display (no text persisted), so the device
  stays NVM-sized.
- On a new day, a brief **journal screen** shows (e.g. "Day 14 — warm light. you were near. i watched
  the clouds."). The full readable archive is a Phase 2 cloud responsibility.

## Seasonal (forms + accent + mood bias)

From the synced date's month:
- **Mood bias:** `seasons.bias(season)` nudges drive baselines — spring energetic, summer
  adventurous, autumn reflective, winter cozy — applied gently each cycle.
- **Seasonal quips:** unlocked per season.
- **Seasonal form:** shown in calm/neutral moods only; mood forms (loaf/puddle/wisp/explorer/crowned)
  still win.
- **Corner accent:** a small bud / sun / leaf / snowflake in the top-right, always marking the
  season. (The owner is comfortable with a busier, playful screen — this supersedes the Phase-0
  minimal layout.)

## Persistence (NVM v3 with migration)

- State blob `NVM_VERSION` → 3, adding a single field: `last_journal_day_ordinal` (int).
- `unpack` migrates **v1 → v3** and **v2 → v3**, defaulting the new field(s); unknown versions fall
  back to `default_state`. Never lose progress across upgrades.
- The journal ring occupies a separate fixed NVM region after the state blob. Still NVM-only — no
  filesystem writes.

## Error Handling

`nettime` never raises into the loop — any WiFi/NTP failure returns `None` and the slime continues
on last-known time (or simply defers journal/season). All adapters stay guarded; the creature never
crashes from being offline (Rule 4: offline first).

## Testing

- Host unit tests (≥80% pure layer) for: epoch ↔ civil-date math (`timekeeping`), season mapping +
  bias (`seasons`), journal record pack/unpack + ring buffer + entry generation (`journal`), form
  selection with `season` (`forms`), and NVM **v2 → v3** (and v1 → v3) migration (`persistence`).
- `nettime` and the journal/accent rendering verified on-device.

## Success Criteria

1. NTP sets the clock when WiFi is configured/present; the slime degrades gracefully and stays alive
   when offline (no fabricated dates).
2. Season (from the date) biases mood and shows the correct seasonal form + corner accent.
3. A journal entry is recorded once per new day and displayed; the journal ring survives power loss.
4. Existing pets upgrade cleanly from a v2 (or v1) NVM blob — progress preserved.
5. Fully offline-capable; never crashes; never loses progress.
6. Pure-layer host tests ≥80%.

## Out of Scope (Phase 1b)

The Phase 2 cloud dreamscape (weather, moon, summaries, readable journal archive), Phoenix
weather-reactive behavior (needs live weather → Phase 2), and Phase 3 hardware add-ons.
