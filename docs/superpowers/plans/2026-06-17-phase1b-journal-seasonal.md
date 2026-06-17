# Phase 1b — Journal & Seasonal Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an NTP-over-WiFi time foundation (offline-first), a daily journal stored as compact NVM records with regenerated text, and date-driven seasonal behavior (mood bias + seasonal forms + corner accents).

**Architecture:** Extends the pure/adapter split. New pure modules (`timekeeping`, `seasons`, `journal`) and extensions (`state`, `persistence`, `forms`, `visuals`, `quips`) are host-tested; new/extended adapters (`nettime`, `display`) and `code.py` are verified on-device. State stays NVM-only (struct v2→v3 with migration); the journal ring lives in a separate fixed NVM region.

**Tech Stack:** CircuitPython 10.x (ESP32-S2): `wifi`, `socketpool`, `adafruit_ntp`, `os.getenv` (settings.toml). Host testing: pytest via `.venv/bin/python -m pytest`, ruff, black (line length 100).

**Conventions:** Always run Python via `.venv/bin/python`. Pure modules must NOT import hardware libs. Never use `namedtuple._replace` (use `state.evolve`). After each task: `.venv/bin/ruff check .` and `.venv/bin/black --check .` must pass.

---

## File Structure

```
slime/
  state.py        # MODIFY: add last_journal_day_ordinal; extend default_state/evolve
  timekeeping.py  # NEW (pure): epoch <-> civil date, day ordinal, new-day
  seasons.py      # NEW (pure): season_of, mood bias, accent/form frames, quip tag
  journal.py      # NEW (pure): record pack/unpack, NVM ring, entry text; device save/load (lazy)
  persistence.py  # MODIFY: NVM v3 + v1/v2 -> v3 migration
  forms.py        # MODIFY: choose_render gains optional season
  visuals.py      # MODIFY: POSE_INDEX += 4 seasonal forms; ACCENT_INDEX
  quips.py        # MODIFY: seasonal quip pools
  nettime.py      # NEW (adapter): WiFi + NTP -> epoch (or None)
  display.py      # MODIFY: corner accent + render_journal()
assets/make_assets.py  # MODIFY: slime.bmp 16 frames + accents.bmp 4 frames
code.py           # MODIFY: sync -> season -> journal flow
settings.toml.example  # NEW: WIFI_SSID/PASSWORD/TZ_OFFSET template
.gitignore        # MODIFY: ignore settings.toml
README.md         # MODIFY: circup adafruit_ntp + settings.toml note
```

Pure modules tested on host: `timekeeping`, `seasons`, `journal`, `state`, `persistence`, `forms`.

---

## Task 1: `slime/timekeeping.py` — epoch & civil date (PURE)

**Files:** Create `slime/timekeeping.py`; Test `tests/test_timekeeping.py`

- [ ] **Step 1: Write the failing tests** — `tests/test_timekeeping.py`:

```python
from slime.timekeeping import civil_from_epoch, day_ordinal, is_new_day, now_epoch


def test_now_epoch_adds_elapsed_monotonic():
    assert now_epoch(1000, mono_at_sync=50.0, mono_now=80.0) == 1030


def test_civil_from_epoch_unix_origin():
    assert civil_from_epoch(0, tz_offset_hours=0) == (1970, 1, 1)
    assert civil_from_epoch(86400, tz_offset_hours=0) == (1970, 1, 2)
    assert civil_from_epoch(31 * 86400, tz_offset_hours=0) == (1970, 2, 1)


def test_civil_from_epoch_applies_timezone():
    # -7h before 1970-01-01 00:00 UTC is the previous day, local
    assert civil_from_epoch(0, tz_offset_hours=-7) == (1969, 12, 31)


def test_day_ordinal_counts_local_days():
    assert day_ordinal(5 * 86400 + 3600, tz_offset_hours=0) == 5


def test_is_new_day():
    assert is_new_day(4, 5) is True
    assert is_new_day(5, 5) is False
    assert is_new_day(6, 5) is False
```

- [ ] **Step 2: Run** `.venv/bin/python -m pytest tests/test_timekeeping.py -v` — expect FAIL (no module).

- [ ] **Step 3: Implement `slime/timekeeping.py`:**

```python
"""Pure time math: epoch <-> civil date, day ordinals. No hardware imports."""

_SECONDS_PER_DAY = 86400


def now_epoch(synced_epoch, mono_at_sync, mono_now):
    """Current epoch seconds = last sync epoch + elapsed monotonic since that sync."""
    return int(synced_epoch + (mono_now - mono_at_sync))


def _local_seconds(epoch, tz_offset_hours):
    return epoch + int(tz_offset_hours * 3600)


def day_ordinal(epoch, tz_offset_hours):
    """Whole local days since the Unix epoch."""
    return _local_seconds(epoch, tz_offset_hours) // _SECONDS_PER_DAY


def civil_from_epoch(epoch, tz_offset_hours):
    """Return (year, month, day) in local time. Howard Hinnant's civil_from_days."""
    z = day_ordinal(epoch, tz_offset_hours) + 719468
    era = (z if z >= 0 else z - 146096) // 146097
    doe = z - era * 146097
    yoe = (doe - doe // 1460 + doe // 36524 - doe // 146096) // 365
    y = yoe + era * 400
    doy = doe - (365 * yoe + yoe // 4 - yoe // 100)
    mp = (5 * doy + 2) // 153
    d = doy - (153 * mp + 2) // 5 + 1
    m = mp + 3 if mp < 10 else mp - 9
    if m <= 2:
        y += 1
    return (y, m, d)


def is_new_day(prev_ordinal, current_ordinal):
    """True when the calendar day has advanced."""
    return current_ordinal > prev_ordinal
```

- [ ] **Step 4: Run** `.venv/bin/python -m pytest tests/test_timekeeping.py -v` — expect PASS (5 passed).

- [ ] **Step 5: Lint/format** `.venv/bin/ruff check slime/timekeeping.py tests/test_timekeeping.py && .venv/bin/black slime/timekeeping.py tests/test_timekeeping.py`

- [ ] **Step 6: Commit**
```bash
git add slime/timekeeping.py tests/test_timekeeping.py
git commit -m "feat: add pure epoch/civil-date time math"
```

---

## Task 2: `slime/seasons.py` — season mapping, bias, frames (PURE)

**Files:** Create `slime/seasons.py`; Test `tests/test_seasons.py`

- [ ] **Step 1: Write the failing tests** — `tests/test_seasons.py`:

```python
from slime.state import Mood
from slime.seasons import (
    SEASONS, accent_frame, apply_bias, form_frame, quip_tag, season_of,
)


def test_season_of_month():
    assert season_of(4) == "spring"
    assert season_of(7) == "summer"
    assert season_of(10) == "autumn"
    assert season_of(1) == "winter"
    assert season_of(12) == "winter"


def test_apply_bias_moves_mood_toward_seasonal_target_and_clamps():
    cold = Mood(60, 30, 50, 30, 40)  # low comfort
    warmer = apply_bias(cold, "winter")
    assert warmer.comfort > cold.comfort  # winter nudges comfort up
    for v in warmer:
        assert 0.0 <= v <= 100.0


def test_apply_bias_is_self_limiting():
    m = Mood(60, 30, 50, 30, 40)
    for _ in range(200):
        m = apply_bias(m, "winter")
    assert m.comfort <= 100.0  # converges, never overflows


def test_frames_and_quip_tag_distinct_per_season():
    forms = {form_frame(s) for s in SEASONS}
    accents = {accent_frame(s) for s in SEASONS}
    assert len(forms) == 4 and len(accents) == 4
    assert quip_tag("summer") == "summer"
```

- [ ] **Step 2: Run** `.venv/bin/python -m pytest tests/test_seasons.py -v` — expect FAIL (no module).

- [ ] **Step 3: Implement `slime/seasons.py`:**

```python
"""Pure seasonal logic: month -> season, mood bias, sprite/accent frames. No hardware imports."""
from slime.state import MOOD_FIELDS, Mood, clamp_mood

SEASONS = ("winter", "spring", "summer", "autumn")

_MONTH_SEASON = {
    12: "winter", 1: "winter", 2: "winter",
    3: "spring", 4: "spring", 5: "spring",
    6: "summer", 7: "summer", 8: "summer",
    9: "autumn", 10: "autumn", 11: "autumn",
}

# Frame indices into visuals.POSE_INDEX (seasonal forms) and accent frames.
_FORM_FRAME = {"spring": 12, "summer": 13, "autumn": 14, "winter": 15}
_ACCENT_FRAME = {"spring": 0, "summer": 1, "autumn": 2, "winter": 3}

# Gentle per-drive targets the mood drifts toward in each season.
_TARGETS = {
    "spring": {"energy": 70.0, "curiosity": 65.0},
    "summer": {"curiosity": 70.0, "energy": 68.0},
    "autumn": {"sleepiness": 55.0, "comfort": 68.0},
    "winter": {"comfort": 75.0, "sleepiness": 58.0},
}


def season_of(month):
    return _MONTH_SEASON[month]


def apply_bias(mood, season, rate=0.05):
    """Nudge biased drives a small step toward seasonal targets. Self-limiting; returns new Mood."""
    targets = _TARGETS[season]
    vals = {field: getattr(mood, field) for field in MOOD_FIELDS}
    for drive, target in targets.items():
        vals[drive] += (target - vals[drive]) * rate
    return clamp_mood(Mood(**vals))


def form_frame(season):
    return _FORM_FRAME[season]


def accent_frame(season):
    return _ACCENT_FRAME[season]


def quip_tag(season):
    return season
```

- [ ] **Step 4: Run** `.venv/bin/python -m pytest tests/test_seasons.py -v` — expect PASS.

- [ ] **Step 5: Lint/format** `.venv/bin/ruff check slime/seasons.py tests/test_seasons.py && .venv/bin/black slime/seasons.py tests/test_seasons.py`

- [ ] **Step 6: Commit**
```bash
git add slime/seasons.py tests/test_seasons.py
git commit -m "feat: add pure seasonal mapping, mood bias, and frame indices"
```

---

## Task 3: Extend `slime/state.py` with `last_journal_day_ordinal`

**Files:** Modify `slime/state.py`; Modify `tests/test_state.py`

- [ ] **Step 1: Add the failing test** — append to `tests/test_state.py`:

```python
def test_state_has_last_journal_day_ordinal():
    s = default_state(now=0.0)
    assert s.last_journal_day_ordinal == 0
    s2 = evolve(s, last_journal_day_ordinal=42)
    assert s2.last_journal_day_ordinal == 42
    assert s.last_journal_day_ordinal == 0
```

- [ ] **Step 2: Run** `.venv/bin/python -m pytest tests/test_state.py -v` — expect FAIL.

- [ ] **Step 3: Modify `slime/state.py`.** Add `"last_journal_day_ordinal"` as the final field of the
  `State` namedtuple; add `last_journal_day_ordinal=0` to `default_state`; and add this line to
  `evolve`'s constructor call:

```python
        last_journal_day_ordinal=changes.get(
            "last_journal_day_ordinal", state.last_journal_day_ordinal
        ),
```

(Place the new namedtuple field after `artifacts`, and the `default_state` kwarg after
`artifacts=0,`.)

- [ ] **Step 4: Run** `.venv/bin/python -m pytest tests/test_state.py -v` — expect PASS (note: the full
  suite will fail in `test_persistence` until Task 4 — that is expected).

- [ ] **Step 5: Lint/format** `.venv/bin/ruff check slime/state.py tests/test_state.py && .venv/bin/black slime/state.py tests/test_state.py`

- [ ] **Step 6: Commit**
```bash
git add slime/state.py tests/test_state.py
git commit -m "feat: add last_journal_day_ordinal to State"
```

---

## Task 4: `slime/persistence.py` — NVM v3 with v1/v2 migration

**Files:** Modify `slime/persistence.py`; Modify `tests/test_persistence.py`

- [ ] **Step 1: Add the failing tests** — append to `tests/test_persistence.py`:

```python
from slime.persistence import _FORMAT_V2


def test_v3_roundtrip_includes_journal_day():
    s = evolve(default_state(now=1.0), last_journal_day_ordinal=20630)
    out = unpack(pack(s))
    assert out.last_journal_day_ordinal == 20630


def test_v2_blob_migrates_to_v3_defaulting_journal_day():
    # A v2 blob (version byte 2) must migrate, keeping its fields and defaulting the new one.
    s = evolve(default_state(now=2.0), familiarity=30.0, visit_count=4, artifacts=3)
    v2_blob = struct.pack(
        _FORMAT_V2,
        2,
        s.mood.energy, s.mood.comfort, s.mood.curiosity, s.mood.sleepiness, s.mood.affection,
        s.last_seen, s.longest_absence, s.first_boot, s.total_boops,
        s.familiarity, s.visit_count, s.artifacts,
    )
    out = unpack(v2_blob)
    assert out.familiarity == 30.0 and out.visit_count == 4 and out.artifacts == 3
    assert out.last_journal_day_ordinal == 0
```

(`struct`, `default_state`, `evolve`, `unpack`, `pack` are already imported in this test file from
earlier phases. `_FORMAT_V2` import is added above.)

- [ ] **Step 2: Run** `.venv/bin/python -m pytest tests/test_persistence.py -v` — expect FAIL.

- [ ] **Step 3: Modify `slime/persistence.py`.** Bump to v3 by editing these parts:

Set the version and add the v3 format (keep `_FORMAT_V1` and `_FORMAT_V2` as-is):
```python
NVM_VERSION = 3

# v3 (Phase 1b): v2 fields + last_journal_day_ordinal (I).
_FORMAT_V3 = "<B5ffffIfIII"
_SIZE_V3 = struct.calcsize(_FORMAT_V3)

BLOB_SIZE = _SIZE_V3
```

Update `pack` to write v3 (append the new field):
```python
def pack(state):
    """Serialize the durable parts of a State to a v3 NVM blob."""
    m = state.mood
    return struct.pack(
        _FORMAT_V3,
        NVM_VERSION,
        m.energy, m.comfort, m.curiosity, m.sleepiness, m.affection,
        state.last_seen, state.longest_absence, state.first_boot,
        state.total_boops,
        state.familiarity, state.visit_count, state.artifacts,
        state.last_journal_day_ordinal,
    )
```

Extend `_build` to take the new field, and update both call sites:
```python
def _build(mood, last_seen, longest_absence, first_boot, total_boops,
           familiarity, visit_count, artifacts, last_journal_day_ordinal):
    return State(
        mood=mood,
        last_seen=last_seen,
        total_boops=total_boops,
        longest_absence=longest_absence,
        first_boot=first_boot,
        expression=mood_engine.derive_expression(mood),
        behavior="idle",
        familiarity=familiarity,
        visit_count=visit_count,
        artifacts=artifacts,
        last_journal_day_ordinal=last_journal_day_ordinal,
    )
```

Rewrite `unpack` to handle v3, v2, v1:
```python
def unpack(blob):
    """Deserialize a v3 blob, migrating v2 and v1. Raises ValueError on bad data."""
    if len(blob) < 1:
        raise ValueError("nvm blob empty")
    version = blob[0]
    if version == 3:
        if len(blob) < _SIZE_V3:
            raise ValueError("nvm v3 blob too short")
        f = struct.unpack(_FORMAT_V3, blob[:_SIZE_V3])
        return _build(Mood(*f[1:6]), f[6], f[7], f[8], f[9], f[10], f[11], f[12], f[13])
    if version == 2:
        if len(blob) < _SIZE_V2:
            raise ValueError("nvm v2 blob too short")
        f = struct.unpack(_FORMAT_V2, blob[:_SIZE_V2])
        return _build(Mood(*f[1:6]), f[6], f[7], f[8], f[9], f[10], f[11], f[12], 0)
    if version == 1:
        if len(blob) < _SIZE_V1:
            raise ValueError("nvm v1 blob too short")
        f = struct.unpack(_FORMAT_V1, blob[:_SIZE_V1])
        return _build(Mood(*f[1:6]), f[6], f[7], f[8], f[9], 0.0, 0, 0, 0)
    raise ValueError("nvm version unknown")
```

- [ ] **Step 4: Run the FULL suite** `.venv/bin/python -m pytest -q` — expect ALL pass (this restores green).

- [ ] **Step 5: Lint/format** `.venv/bin/ruff check slime/persistence.py tests/test_persistence.py && .venv/bin/black slime/persistence.py tests/test_persistence.py`

- [ ] **Step 6: Commit**
```bash
git add slime/persistence.py tests/test_persistence.py
git commit -m "feat: NVM v3 persistence with v1/v2 -> v3 migration"
```

---

## Task 5: `slime/journal.py` — records, ring buffer, entry text (PURE)

**Files:** Create `slime/journal.py`; Test `tests/test_journal.py`

- [ ] **Step 1: Write the failing tests** — `tests/test_journal.py`:

```python
from slime.journal import (
    CAPACITY, append, empty_ring, entries, generate_entry, pack_record, unpack_record,
)


def test_record_roundtrip():
    rec = (20630, 3, 1, 0b101, 2)  # day, mood, season, flags, tier
    assert unpack_record(pack_record(*rec)) == rec


def test_ring_append_and_entries_in_order():
    ring = empty_ring()
    ring = append(ring, pack_record(1, 0, 0, 0, 0))
    ring = append(ring, pack_record(2, 0, 0, 0, 0))
    got = [e[0] for e in entries(ring)]  # day ordinals
    assert got == [1, 2]


def test_ring_wraps_at_capacity():
    ring = empty_ring()
    for day in range(CAPACITY + 5):
        ring = append(ring, pack_record(day, 0, 0, 0, 0))
    got = [e[0] for e in entries(ring)]
    assert len(got) == CAPACITY
    assert got[0] == 5 and got[-1] == CAPACITY + 4  # oldest dropped


def test_generate_entry_mentions_day_number_and_is_a_string():
    rec = (20630, 3, 2, 0b001, 1)  # happy mood, autumn, greeted
    line = generate_entry(rec, day_number=14, choice=lambda s: s[0])
    assert line.startswith("Day 14")
    assert line.endswith(".")
```

- [ ] **Step 2: Run** `.venv/bin/python -m pytest tests/test_journal.py -v` — expect FAIL (no module).

- [ ] **Step 3: Implement `slime/journal.py`:**

```python
"""Pure daily-journal records + NVM ring buffer + regenerated entry text.

Records are compact (8 bytes). Text is regenerated from the record, not stored.
Device read/write of the ring (save_ring/load_ring) import microcontroller lazily.
"""
import struct

_RECORD_FMT = "<IBBBB"  # day_ordinal, mood_dom, season, flags, tier
RECORD_SIZE = struct.calcsize(_RECORD_FMT)  # 8
_HEADER_FMT = "<HH"  # count, head
_HEADER_SIZE = struct.calcsize(_HEADER_FMT)  # 4
CAPACITY = 48
RING_SIZE = _HEADER_SIZE + CAPACITY * RECORD_SIZE

# Mood byte -> ambience tone words used in the entry.
_MOOD_WORD = {0: "i watched the clouds", 1: "i drifted", 2: "a good day",
              3: "i wondered at things", 4: "i thought of far places"}
_SEASON_WORD = {0: "still cold air", 1: "green light", 2: "long warm hours", 3: "soft gray light"}


def pack_record(day_ordinal, mood_dom, season, flags, tier):
    return struct.pack(_RECORD_FMT, day_ordinal, mood_dom, season, flags, tier)


def unpack_record(blob):
    return struct.unpack(_RECORD_FMT, blob[:RECORD_SIZE])


def empty_ring():
    return struct.pack(_HEADER_FMT, 0, 0) + bytes(CAPACITY * RECORD_SIZE)


def append(ring, record_bytes):
    """Return a new ring with record appended at the head (wrapping at CAPACITY)."""
    count, head = struct.unpack(_HEADER_FMT, ring[:_HEADER_SIZE])
    body = bytearray(ring[_HEADER_SIZE:])
    off = head * RECORD_SIZE
    body[off:off + RECORD_SIZE] = record_bytes[:RECORD_SIZE]
    head = (head + 1) % CAPACITY
    count = min(count + 1, CAPACITY)
    return struct.pack(_HEADER_FMT, count, head) + bytes(body)


def entries(ring):
    """Return unpacked records oldest-first."""
    count, head = struct.unpack(_HEADER_FMT, ring[:_HEADER_SIZE])
    body = ring[_HEADER_SIZE:]
    start = (head - count) % CAPACITY
    out = []
    for i in range(count):
        idx = (start + i) % CAPACITY
        off = idx * RECORD_SIZE
        out.append(unpack_record(body[off:off + RECORD_SIZE]))
    return out


def generate_entry(record, day_number, choice):
    """Regenerate the journal line for a record. `choice` picks a closing variant."""
    _, mood_dom, season, flags, _tier = record
    ambience = _SEASON_WORD.get(season, "the usual light")
    presence = "you came near" if flags & 0b1 else "a quiet day alone"
    closing = choice((_MOOD_WORD.get(mood_dom, "i watched the clouds"),))
    return "Day {} - {}. {}. {}.".format(day_number, ambience, presence, closing)


def save_ring(ring):
    """Write the journal ring to NVM after the state blob. Device-only."""
    import microcontroller

    from slime.persistence import BLOB_SIZE

    start = ((BLOB_SIZE // 16) + 1) * 16  # 16-byte aligned region after the state blob
    microcontroller.nvm[start:start + RING_SIZE] = ring


def load_ring():
    """Read the journal ring from NVM; return an empty ring on any problem. Device-only."""
    import microcontroller

    from slime.persistence import BLOB_SIZE

    start = ((BLOB_SIZE // 16) + 1) * 16
    try:
        data = bytes(microcontroller.nvm[start:start + RING_SIZE])
        struct.unpack(_HEADER_FMT, data[:_HEADER_SIZE])  # sanity
        return data
    except Exception:
        return empty_ring()
```

- [ ] **Step 4: Run** `.venv/bin/python -m pytest tests/test_journal.py -v` — expect PASS.

- [ ] **Step 5: Confirm host import is clean** `.venv/bin/python -c "import slime.journal"` — succeeds
  (no module-level `microcontroller`).

- [ ] **Step 6: Lint/format** `.venv/bin/ruff check slime/journal.py tests/test_journal.py && .venv/bin/black slime/journal.py tests/test_journal.py`

- [ ] **Step 7: Commit**
```bash
git add slime/journal.py tests/test_journal.py
git commit -m "feat: add pure journal records, NVM ring, and entry generation"
```

---

## Task 6: Seasonal frames + `forms.choose_render(season=...)`

**Files:** Modify `slime/visuals.py`; Modify `slime/forms.py`; Modify `tests/test_forms.py`

- [ ] **Step 1: Extend `POSE_INDEX` in `slime/visuals.py`** — add these keys (after `wisp`):

```python
    "spring_form": 12,
    "summer_form": 13,
    "autumn_form": 14,
    "winter_form": 15,
```

  (No accent map here — `seasons.form_frame`/`seasons.accent_frame` are the single source for
  season→frame indices.)

- [ ] **Step 2: Add the failing tests** — append to `tests/test_forms.py`:

```python
def test_calm_mood_shows_seasonal_form_when_season_given():
    calm = Mood(60, 80, 50, 30, 40)  # derive_expression -> content
    assert choose_render(calm, tier=4, sleeping=False, season="winter") == POSE_INDEX["winter_form"]


def test_no_season_keeps_content_face():
    calm = Mood(60, 80, 50, 30, 40)
    assert choose_render(calm, tier=4, sleeping=False) == POSE_INDEX["content"]


def test_mood_form_still_wins_over_season():
    sleepy = Mood(50, 60, 40, 90, 40)
    assert choose_render(sleepy, tier=4, sleeping=True, season="winter") == POSE_INDEX["loaf"]
```

- [ ] **Step 3: Run** `.venv/bin/python -m pytest tests/test_forms.py -v` — expect FAIL.

- [ ] **Step 4: Modify `slime/forms.py`.** Replace the final return of `choose_render` and add the
  `season` parameter:

```python
from slime.friendship import unlocked_forms
from slime.mood import derive_expression
from slime.seasons import form_frame
from slime.visuals import POSE_INDEX


def choose_render(mood, tier, sleeping, season=None):
    """Return the sprite frame index to display, in priority order."""
    forms_ok = unlocked_forms(tier)

    if sleeping or mood.sleepiness >= 85.0:
        return POSE_INDEX["loaf"]
    if mood.energy <= 15.0:
        return POSE_INDEX["puddle"]
    if "explorer" in forms_ok and mood.curiosity >= 70.0 and mood.energy >= 60.0:
        return POSE_INDEX["explorer"]
    if "crowned" in forms_ok and mood.affection >= 75.0 and mood.energy >= 50.0:
        return POSE_INDEX["crowned"]
    if mood.curiosity <= 25.0 and mood.energy <= 35.0:
        return POSE_INDEX["wisp"]
    expression = derive_expression(mood)
    if season and expression == "content":
        return form_frame(season)  # seasons module owns season->frame index (12-15)
    return POSE_INDEX[expression]
```

(`form_frame(season)` returns the same integer as `POSE_INDEX["<season>_form"]`; `seasons` is the
single source of truth for those indices.)

- [ ] **Step 5: Run** `.venv/bin/python -m pytest tests/test_forms.py tests/test_visuals.py -v` — expect PASS.

- [ ] **Step 6: Lint/format** `.venv/bin/ruff check slime/forms.py slime/visuals.py tests/test_forms.py && .venv/bin/black slime/forms.py slime/visuals.py tests/test_forms.py`

- [ ] **Step 7: Commit**
```bash
git add slime/forms.py slime/visuals.py tests/test_forms.py
git commit -m "feat: seasonal forms + accent index; forms.choose_render takes season"
```

---

## Task 7: Seasonal quip pools (PURE)

**Files:** Modify `slime/quips.py`; Modify `tests/test_quips.py`

- [ ] **Step 1: Add the failing test** — append to `tests/test_quips.py`:

```python
def test_seasonal_quip_pools_exist():
    for tag in ("spring", "summer", "autumn", "winter"):
        assert tag in QUIPS
        assert len(QUIPS[tag]) >= 2
```

- [ ] **Step 2: Run** `.venv/bin/python -m pytest tests/test_quips.py -v` — expect FAIL.

- [ ] **Step 3: Modify `slime/quips.py`** — add these four entries to the `QUIPS` dict:

```python
    "spring": (
        "everything is waking",
        "green and new",
        "the air feels young",
    ),
    "summer": (
        "long bright hours",
        "i want to wander",
        "warm all the way through",
    ),
    "autumn": (
        "the light goes gold",
        "i think back often",
        "a season for quiet",
    ),
    "winter": (
        "cozy and slow",
        "the cold is gentle",
        "wrapped up small",
    ),
```

- [ ] **Step 4: Run** `.venv/bin/python -m pytest tests/test_quips.py -v` — expect PASS.

- [ ] **Step 5: Lint/format** `.venv/bin/ruff check slime/quips.py tests/test_quips.py && .venv/bin/black slime/quips.py tests/test_quips.py`

- [ ] **Step 6: Commit**
```bash
git add slime/quips.py tests/test_quips.py
git commit -m "feat: add seasonal quip pools"
```

---

## Task 8: Sprite sheet (16 forms) + accents sheet

**Files:** Modify `assets/make_assets.py`; regenerate `assets/slime.bmp` and `assets/accents.bmp`

- [ ] **Step 1: Modify `assets/make_assets.py`.** Add the four seasonal forms to `POSES` (after
  `"wisp"`):

```python
    "spring_form", "summer_form", "autumn_form", "winter_form",
```

  Add these branches in `draw_pose` before the final `else:  # content`:

```python
    elif pose == "spring_form":
        _blob(d, ox)
        d.rectangle([ox + 30, 6, ox + 34, 16], fill=BLACK)  # stem
        d.ellipse([ox + 22, 0, ox + 34, 10], fill=GRAY, outline=BLACK)  # leaf
        _eyes(d, ox, 32)
    elif pose == "summer_form":
        _blob(d, ox)
        d.rectangle([ox + 20, 30, ox + 44, 38], fill=BLACK)  # shades
        d.rectangle([ox + 30, 32, ox + 34, 36], fill=GRAY)
    elif pose == "autumn_form":
        _blob(d, ox)
        d.polygon([(ox + 32, 4), (ox + 26, 14), (ox + 38, 14)], fill=GRAY, outline=BLACK)  # leaf
        _eyes(d, ox, 32)
    elif pose == "winter_form":
        _blob(d, ox)
        d.rectangle([ox + 10, 44, ox + 54, 52], fill=BLACK)  # scarf
        _eyes(d, ox, 32)
```

  Then, at the END of `main()` (after `sheet.save(...)` and its print), add accent-sheet generation:

```python
    accents = Image.new("P", (28 * 4, 28), WHITE)
    accents.putpalette([0, 0, 0, 90, 90, 90, 170, 170, 170, 255, 255, 255] + [0] * (256 * 3 - 12))
    ad = ImageDraw.Draw(accents)
    # 0 spring bud, 1 summer sun, 2 autumn leaf, 3 winter snowflake
    ad.ellipse([4, 6, 16, 18], fill=GRAY, outline=BLACK)
    ad.rectangle([9, 16, 11, 24], fill=BLACK)
    ad.ellipse([28 + 6, 6, 28 + 18, 18], fill=GRAY, outline=BLACK)
    for ang in range(0, 360, 45):
        import math

        cx, cy = 28 + 12, 12
        ad.line([cx, cy, int(cx + 11 * math.cos(math.radians(ang))),
                 int(cy + 11 * math.sin(math.radians(ang)))], fill=BLACK)
    ad.polygon([(56 + 12, 4), (56 + 5, 18), (56 + 19, 18)], fill=GRAY, outline=BLACK)
    cx, cy = 84 + 12, 12
    for ang in range(0, 180, 45):
        import math

        dx, dy = int(11 * math.cos(math.radians(ang))), int(11 * math.sin(math.radians(ang)))
        ad.line([cx - dx, cy - dy, cx + dx, cy + dy], fill=BLACK)
    accents.save("assets/accents.bmp")
    print("wrote assets/accents.bmp (%dx%d, 4 frames)" % (accents.width, accents.height))
```

- [ ] **Step 2: Regenerate** `.venv/bin/python assets/make_assets.py` — expect two lines:
  `wrote assets/slime.bmp (1024x64, 16 frames)` and `wrote assets/accents.bmp (112x28, 4 frames)`.

- [ ] **Step 3: Verify** `.venv/bin/python -c "from PIL import Image; print(Image.open('assets/slime.bmp').size, Image.open('assets/accents.bmp').size)"` — expect `(1024, 64) (112, 28)`.

- [ ] **Step 4: Lint/format** `.venv/bin/ruff check assets/make_assets.py && .venv/bin/black assets/make_assets.py`

- [ ] **Step 5: Commit**
```bash
git add assets/make_assets.py assets/slime.bmp assets/accents.bmp
git commit -m "feat: add seasonal form frames and an accents sprite sheet"
```

---

## Task 9: `slime/nettime.py` — WiFi + NTP adapter (DEVICE)

**Files:** Create `slime/nettime.py`; Create `settings.toml.example`; Modify `.gitignore`; Modify `README.md`

- [ ] **Step 1: Implement `slime/nettime.py`:**

```python
"""Hardware adapter: WiFi + NTP -> epoch seconds (UTC). Device-only. Never raises into the loop."""
import os
import time


def sync():
    """Return current epoch seconds from NTP, or None if WiFi/NTP is unavailable."""
    try:
        import adafruit_ntp
        import socketpool
        import wifi

        ssid = os.getenv("WIFI_SSID")
        password = os.getenv("WIFI_PASSWORD")
        if not ssid:
            return None
        wifi.radio.connect(ssid, password)
        pool = socketpool.SocketPool(wifi.radio)
        ntp = adafruit_ntp.NTP(pool, tz_offset=0)
        return int(time.mktime(ntp.datetime))
    except Exception:
        return None


def tz_offset_hours():
    """Timezone offset from settings.toml (default -7, Phoenix)."""
    try:
        value = os.getenv("TZ_OFFSET")
        return float(value) if value is not None else -7.0
    except Exception:
        return -7.0
```

- [ ] **Step 2: Create `settings.toml.example`:**

```toml
# Copy to settings.toml on the CIRCUITPY drive and fill in. settings.toml is gitignored.
WIFI_SSID = "your-network"
WIFI_PASSWORD = "your-password"
TZ_OFFSET = "-7"   # Phoenix (UTC-7, no DST)
```

- [ ] **Step 3: Add `settings.toml` to `.gitignore`** — append a line:
```
settings.toml
```

- [ ] **Step 4: Add a note to `README.md`** under the deploy section: install `adafruit_ntp` with
  circup and copy `settings.toml` for WiFi/NTP. Add to the existing `circup install` line so it reads:
```
circup install adafruit_lis3dh neopixel adafruit_display_text adafruit_ntp
```
  and add a bullet: "Copy `settings.toml` (see `settings.toml.example`) with your WiFi credentials to enable the daily journal and seasons."

- [ ] **Step 5: Verify host import** `.venv/bin/python -c "import slime.nettime"` — succeeds (no
  module-level hardware import; `os`/`time` only).

- [ ] **Step 6: Lint/format** `.venv/bin/ruff check slime/nettime.py && .venv/bin/black slime/nettime.py`

- [ ] **Step 7: Commit**
```bash
git add slime/nettime.py settings.toml.example .gitignore README.md
git commit -m "feat: add WiFi+NTP time adapter and settings.toml template"
```

---

## Task 10: `slime/display.py` — corner accent + journal screen (DEVICE)

**Files:** Modify `slime/display.py`

- [ ] **Step 1: Modify `slime/display.py`.** In `__init__`, after building the sprite tile/group,
  load the accents sheet and add a corner accent TileGrid:

```python
        # Seasonal corner accent (top-right), hidden by default.
        self._accent_bmp = displayio.OnDiskBitmap("/assets/accents.bmp")
        self._accent = displayio.TileGrid(
            self._accent_bmp,
            pixel_shader=self._accent_bmp.pixel_shader,
            width=1, height=1, tile_width=28, tile_height=28,
        )
        self._accent.x = self._display.width - 32
        self._accent.y = 4
        self._accent_hidden = True
```

  Update `render_frame` to accept an optional accent index and show/hide the accent:
```python
    def render_frame(self, frame_index, quip_text="", accent_index=None):
        """Set the sprite frame + quip (+ optional seasonal accent) and refresh."""
        self._tile[0] = frame_index
        self._quip.text = quip_text or ""
        if accent_index is None:
            if not self._accent_hidden and self._accent in self._root:
                self._root.remove(self._accent)
                self._accent_hidden = True
        else:
            self._accent[0] = accent_index
            if self._accent_hidden:
                self._root.append(self._accent)
                self._accent_hidden = False
        self._display.root_group = self._root
        while self._display.time_to_refresh > 0:
            time.sleep(0.05)
        self._display.refresh()
```

  Add a journal screen renderer:
```python
    def render_journal(self, lines):
        """Full-screen journal: a list of short lines, centered, then a slow refresh."""
        group = displayio.Group()
        bg = displayio.Bitmap(self._display.width, self._display.height, 1)
        palette = displayio.Palette(1)
        palette[0] = 0xFFFFFF
        group.append(displayio.TileGrid(bg, pixel_shader=palette))
        n = len(lines)
        for i, text in enumerate(lines):
            lbl = label.Label(terminalio.FONT, text=text, color=0x000000, scale=1)
            lbl.anchor_point = (0.5, 0.5)
            lbl.anchored_position = (
                self._display.width // 2,
                self._display.height // 2 + (i - (n - 1) / 2) * 18,
            )
            group.append(lbl)
        self._display.root_group = group
        while self._display.time_to_refresh > 0:
            time.sleep(0.05)
        self._display.refresh()
```

(`displayio`, `terminalio`, `label`, `time` are already imported in this file.)

- [ ] **Step 2: Verify on device** (after deploy in Task 12). In the REPL:
```python
from slime.display import Display
d = Display()
d.render_frame(0, "hi", accent_index=3)   # winter snowflake accent in the corner
```
Expected: slime + quip + a snowflake top-right.

- [ ] **Step 3: Lint/format** `.venv/bin/ruff check slime/display.py && .venv/bin/black slime/display.py`

- [ ] **Step 4: Commit**
```bash
git add slime/display.py
git commit -m "feat: seasonal corner accent and journal screen in display adapter"
```

---

## Task 11: Integrate time/journal/season in `code.py` (DEVICE)

**Files:** Modify `code.py`

- [ ] **Step 1: Add imports** at the top of `code.py` (with the other `from slime import ...`):

```python
from slime import journal, nettime, seasons, timekeeping
```

- [ ] **Step 2: Add a time/season bootstrap** helper near the other helpers:

```python
def _sync_time():
    """Try NTP once. Returns (synced_epoch, mono_at_sync, tz_offset) or (None, None, tz)."""
    tz = nettime.tz_offset_hours()
    epoch = nettime.sync()
    if epoch is None:
        return None, None, tz
    return epoch, time.monotonic(), tz


def _current_season(synced_epoch, mono_at_sync, tz):
    """Season string if time is known this power-cycle, else None."""
    if synced_epoch is None:
        return None
    epoch = timekeeping.now_epoch(synced_epoch, mono_at_sync, time.monotonic())
    _, month, _ = timekeeping.civil_from_epoch(epoch, tz)
    return seasons.season_of(month)
```

- [ ] **Step 3: In `main()`**, right after `state = persistence.load(now)`, sync time and load the
  journal ring:

```python
    synced_epoch, mono_at_sync, tz = (None, None, -7.0)
    ring = journal.empty_ring()
    on_usb_guess = sensors.on_usb() if (sensors := _new_adapter(Sensors)) else True
    if on_usb_guess:  # only spend WiFi/power on USB
        synced_epoch, mono_at_sync, tz = _sync_time()
    ring = journal.load_ring()
```

  Remove the later duplicate `sensors = _new_adapter(Sensors)` line (it is created above now). Keep
  `pixels`, `display`, `sound` construction as-is.

- [ ] **Step 4: Add the season + journal flow** before the first `_render_frame(display, state)` call.
  Compute the season, apply its mood bias, and write a journal entry on a new day:

```python
    season = _current_season(synced_epoch, mono_at_sync, tz)
    if season:
        state = evolve(state, mood=seasons.apply_bias(state.mood, season))

        ordinal = timekeeping.day_ordinal(
            timekeeping.now_epoch(synced_epoch, mono_at_sync, time.monotonic()), tz
        )
        if timekeeping.is_new_day(state.last_journal_day_ordinal, ordinal):
            mood_dom = {"content": 0, "sleepy": 1, "happy": 2, "curious": 3,
                        "contemplative": 4}.get(state.expression, 0)
            season_byte = seasons.accent_frame(season)
            flags = 0b1 if "double_tap" in events else 0
            tier = friendship.tier(state.familiarity)
            ring = journal.append(ring, journal.pack_record(ordinal, mood_dom, season_byte, flags, tier))
            journal.save_ring(ring)
            state = evolve(state, last_journal_day_ordinal=ordinal)
            if display:
                day_number = len(journal.entries(ring))
                line = journal.generate_entry(
                    journal.entries(ring)[-1], day_number, _choice
                )
                try:
                    display.render_journal([line])
                except Exception:
                    pass
```

  NOTE: this block uses `events`, so it must come AFTER the first `_gather(...)` call. Place it
  immediately after the `friendship.update(...)` line that sets `familiarity`/`visit_count` in the
  initial cycle, and BEFORE `state = _render_frame(display, state)`.

- [ ] **Step 5: Thread the accent into rendering.** Change `_render_frame` to accept and pass the
  season accent, and pass the season into form selection. Replace `_render_frame` with:

```python
def _render_frame(display, state, season=None):
    """Render the current form (+ seasonal accent) and a quip. Returns updated state."""
    if not display:
        return state
    sleeping = state.mood.sleepiness >= _SLEEPY_FRAME
    ftier = friendship.tier(state.familiarity)
    frame = choose_render(state.mood, ftier, sleeping, season=season)
    tag = "bonded" if ftier >= 3 else state.expression
    quip = pick(tag) or pick(state.expression)
    accent = seasons.accent_frame(season) if season else None
    try:
        display.render_frame(frame, quip or "", accent_index=accent)
        state = evolve(state, last_seen=time.monotonic())
    except Exception:
        pass
    return state
```

  Update BOTH `_render_frame(display, state)` call sites to `_render_frame(display, state, season)`.
  In the continuous loop, compute `season` once before the loop (time doesn't change season within a
  run) and pass it; also apply `seasons.apply_bias` each cycle when a season is known by inserting,
  right after the loop's `friendship.update(...)` line:

```python
                if season:
                    state = evolve(state, mood=seasons.apply_bias(state.mood, season))
```

- [ ] **Step 6: Syntax check** `.venv/bin/python -m py_compile code.py` — expect no output.

- [ ] **Step 7: Confirm host suite unaffected** `.venv/bin/python -m pytest -q` — expect all pass (the
  `_replace` guard scans `code.py`; must find none).

- [ ] **Step 8: Lint/format** `.venv/bin/ruff check code.py && .venv/bin/black --check code.py`

- [ ] **Step 9: Commit**
```bash
git add code.py
git commit -m "feat: integrate NTP time, seasonal bias/accent, and daily journal into code.py"
```

---

## Task 12: On-device bring-up & Phase 1b verification

**Files:** none (deploy + verify only)

- [ ] **Step 1: Install the NTP library** `.venv/bin/circup --path /Volumes/CIRCUITPY install adafruit_ntp`.

- [ ] **Step 2: Create `settings.toml` on the board** (copy `settings.toml.example` to
  `/Volumes/CIRCUITPY/settings.toml`) and fill in real WiFi credentials + `TZ_OFFSET`.

- [ ] **Step 3: Deploy:**
```bash
cp slime/*.py /Volumes/CIRCUITPY/slime/
cp assets/slime.bmp assets/accents.bmp /Volumes/CIRCUITPY/assets/
cp code.py /Volumes/CIRCUITPY/
rm -rf /Volumes/CIRCUITPY/slime/__pycache__
sync
```

- [ ] **Step 4: Confirm a clean run** over serial (soft-reboot, no traceback; if "Power dipped" safe
  mode, use a powered port).

- [ ] **Step 5: Verify Phase 1b success criteria:**
  1. [ ] With valid `settings.toml`, the clock syncs: REPL
     `from slime import nettime; print(nettime.sync())` prints an epoch int (~1.7e9).
  2. [ ] Offline resilience: temporarily rename `settings.toml` → it still boots and runs (no crash);
     `nettime.sync()` returns `None`.
  3. [ ] Season + accent: the panel shows the seasonal form (in calm mood) with the corner accent for
     the current month.
  4. [ ] Journal: force a new-day entry by setting `last_journal_day_ordinal` low — REPL:
     `import microcontroller; from slime.persistence import load, save, BLOB_SIZE; from slime.state import evolve; s=load(); save(evolve(s, last_journal_day_ordinal=0))` then soft-reboot; a journal screen should appear, and the ring grows (`from slime import journal; print(len(journal.entries(journal.load_ring())))`).
  5. [ ] Migration: a board upgrading from a v2 blob keeps familiarity/boops (check before/after).
  6. [ ] Host suite green: `.venv/bin/python -m pytest --cov` ≥80% pure layer.

- [ ] **Step 6: Commit the milestone**
```bash
git commit --allow-empty -m "chore: Phase 1b verified on device"
```

---

## Notes for the implementer

- **Pure vs adapter:** `timekeeping`, `seasons`, `journal` (pack/ring/generate), `forms`, `state`,
  `persistence` (pack/unpack) must not import hardware. `journal.save_ring/load_ring` and
  `nettime.sync` import hardware lazily / are device-only.
- **Offline-first:** if `nettime.sync()` returns `None`, `season` is `None` → no bias, no accent, no
  journal that cycle. The slime must run exactly as in Phase 1a. Verify by removing `settings.toml`.
- **NVM layout:** state blob at `[0:BLOB_SIZE]`; journal ring at a 16-byte-aligned offset just after
  it (`journal.save_ring` computes it from `persistence.BLOB_SIZE`). They must not overlap.
- **No fabricated time:** never default to a fake date when offline — gate all journal/season work on
  a successful sync this power-cycle.
```
