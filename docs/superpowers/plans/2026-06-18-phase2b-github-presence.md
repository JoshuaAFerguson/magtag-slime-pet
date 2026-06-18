# Phase 2b-i — GitHub Presence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fold a privacy-safe GitHub "coding rhythm" signal into the existing `/oracle`, and have the MagTag blend it into mood (independent-but-proud when busy, attentive after a quiet gap) plus a "you seemed busy" journal touch — degrading to plain Phase 2a behavior with no token.

**Architecture:** Extends the Phase 2a oracle on both tiers, no new endpoint. The server adds `app/github.py` (PAT fetch + pure `summarize`) and folds a `presence` block into `/oracle`. The device extends `slime/oracle.py` (Oracle gains `coding_rhythm` + `hours_since_push`, blended `mood_bias`, presence quips, busy helper) and `slime/journal.py` (busy flag). PAT and all content stay server-side.

**Tech Stack:** Server: Python 3.12, FastAPI, httpx. Device: CircuitPython pure modules. Host testing: pytest/ruff/black (line length 100).

**Conventions:** Server tests run from `server/`; device tests from repo root. Pure modules: no hardware imports; no `namedtuple._replace`. Run via `.venv/bin/...`.

---

## File Structure

```
server/app/config.py     # MODIFY: + GITHUB_USER, GITHUB_TOKEN
server/app/github.py      # NEW: fetch_events(client) + summarize(events, now) [pure]
server/app/oracle.py      # MODIFY: build() gains presence
server/app/main.py        # MODIFY: derive presence, fold into /oracle
slime/oracle.py           # MODIFY: Oracle +coding_rhythm/+hours_since_push; parse/mood_bias/quip_tag/is_busy/pack
slime/quips.py            # MODIFY: busy + quiet pools
slime/journal.py          # MODIFY: busy flag (bit1) + entry phrase
code.py                   # MODIFY: set journal busy flag from presence
```

---

# TIER 1 — SERVER

## Task S1: `server/app/github.py` — fetch + summarize

**Files:** Modify `server/app/config.py`; Create `server/app/github.py`; Test `server/tests/test_github.py`

- [ ] **Step 1: Add to `server/app/config.py`** (append):
```python
GITHUB_USER = os.getenv("GITHUB_USER", "")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
```

- [ ] **Step 2: Write the failing tests** — `server/tests/test_github.py`:
```python
from datetime import datetime, timezone

from app.github import summarize

NOW = datetime(2026, 6, 18, 15, 0, tzinfo=timezone.utc)


def _push(hours_ago, size):
    created = NOW.timestamp() - hours_ago * 3600
    iso = datetime.fromtimestamp(created, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {"type": "PushEvent", "created_at": iso, "payload": {"size": size}}


def test_idle_when_no_recent_pushes():
    out = summarize([_push(48, 3)], NOW)  # 48h ago -> outside 24h window
    assert out["coding_rhythm"] == "idle"


def test_light_then_heavy_by_commit_count():
    light = summarize([_push(2, 2)], NOW)
    assert light["coding_rhythm"] == "light"
    heavy = summarize([_push(1, 6), _push(3, 6)], NOW)  # 12 commits in 24h
    assert heavy["coding_rhythm"] == "heavy"


def test_hours_since_push_from_newest():
    out = summarize([_push(5, 1), _push(2, 1)], NOW)
    assert 1.9 <= out["hours_since_push"] <= 2.1


def test_no_pushes_gives_none_hours():
    out = summarize([{"type": "WatchEvent", "created_at": "2026-06-18T14:00:00Z"}], NOW)
    assert out["coding_rhythm"] == "idle"
    assert out["hours_since_push"] is None
```

- [ ] **Step 2b: Run** `cd server && ../.venv/bin/python -m pytest tests/test_github.py -v` — expect FAIL.

- [ ] **Step 3: Implement `server/app/github.py`**
```python
"""GitHub activity -> a privacy-safe coding-rhythm signal. summarize() is pure."""
from datetime import datetime, timezone

from . import config

GITHUB_EVENTS_URL = "https://api.github.com/users/{}/events"
_HEAVY_COMMITS = 10
_LIGHT_COMMITS = 1


def fetch_events(client):
    """GET the configured user's recent events using the PAT. `client` is an httpx.Client."""
    headers = {"Accept": "application/vnd.github+json"}
    if config.GITHUB_TOKEN:
        headers["Authorization"] = "token " + config.GITHUB_TOKEN
    resp = client.get(GITHUB_EVENTS_URL.format(config.GITHUB_USER), headers=headers)
    resp.raise_for_status()
    return resp.json()


def _parse_dt(iso):
    if not iso:
        return None
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return None


def summarize(events, now):
    """Pure: events list + tz-aware `now` -> {coding_rhythm, hours_since_push}."""
    commits = 0
    last_push = None
    for ev in events:
        if ev.get("type") != "PushEvent":
            continue
        created = _parse_dt(ev.get("created_at"))
        if created is None:
            continue
        age_h = (now - created).total_seconds() / 3600.0
        if age_h <= 24:
            commits += ev.get("payload", {}).get("size", 0)
        if last_push is None or created > last_push:
            last_push = created

    if commits >= _HEAVY_COMMITS:
        rhythm = "heavy"
    elif commits >= _LIGHT_COMMITS:
        rhythm = "light"
    else:
        rhythm = "idle"
    hours = None if last_push is None else round((now - last_push).total_seconds() / 3600.0, 2)
    return {"coding_rhythm": rhythm, "hours_since_push": hours}
```

- [ ] **Step 4: Run** `cd server && ../.venv/bin/python -m pytest tests/test_github.py -v` — expect PASS.

- [ ] **Step 5: Lint/format** `.venv/bin/ruff check server/app/github.py server/app/config.py server/tests/test_github.py && .venv/bin/black server/app/github.py server/app/config.py server/tests/test_github.py`

- [ ] **Step 6: Commit**
```bash
git add server/app/github.py server/app/config.py server/tests/test_github.py
git commit -m "feat: GitHub events fetch and pure coding-rhythm summary"
```

---

## Task S2: Fold `presence` into `/oracle`

**Files:** Modify `server/app/oracle.py`; Modify `server/app/main.py`; Modify `server/tests/test_oracle.py`, `server/tests/test_main.py`

- [ ] **Step 1: Update `server/tests/test_oracle.py`** — replace the existing test with one that includes presence:
```python
from app.oracle import build


def test_build_shapes_payload():
    weather = {"tags": ["extreme_heat"], "temp_c": 43, "code": 0, "sunset_soon": False}
    mooninfo = {"phase": 4, "name": "full", "illum": 0.98}
    presence = {"coding_rhythm": "heavy", "hours_since_push": 1.5}
    out = build(weather, mooninfo, presence, ts=1718900000)
    assert out["weather"]["tags"] == ["extreme_heat"]
    assert out["moon"]["phase"] == 4
    assert out["presence"]["coding_rhythm"] == "heavy"
    assert out["ts"] == 1718900000
```

- [ ] **Step 2: Run** `cd server && ../.venv/bin/python -m pytest tests/test_oracle.py -v` — expect FAIL.

- [ ] **Step 3: Update `server/app/oracle.py`**
```python
"""Assemble the /oracle payload from weather + moon + presence."""


def build(weather, moon, presence, ts):
    """Return the compact oracle payload served to the device."""
    return {"weather": weather, "moon": moon, "presence": presence, "ts": ts}
```

- [ ] **Step 4: Update `server/app/main.py`** — import github, add a `_presence()` helper, and pass it
  to `build`. Replace the `from . import config, moon, oracle, weather` line with:
```python
from . import config, github, moon, oracle, weather
```
  Add this helper above `get_oracle`:
```python
def _presence():
    """Derive the GitHub presence signal; idle on missing token or any failure."""
    if not config.GITHUB_USER:
        return {"coding_rhythm": "idle", "hours_since_push": None}
    try:
        with httpx.Client(timeout=10) as client:
            events = github.fetch_events(client)
        return github.summarize(events, datetime.now(timezone.utc))
    except Exception:
        return {"coding_rhythm": "idle", "hours_since_push": None}
```
  Change the `datetime` import at the top to include `timezone`:
```python
from datetime import datetime, timezone
```
  And change the final return in `get_oracle` to:
```python
    return oracle.build(w, mooninfo, _presence(), ts=int(time.time()))
```

- [ ] **Step 5: Update `server/tests/test_main.py`** — append a presence test (the existing tests
  still pass because `config.GITHUB_USER` defaults to `""` → idle presence):
```python
def test_oracle_includes_presence_when_github_configured(monkeypatch):
    monkeypatch.setattr(main_mod.config, "GITHUB_USER", "octocat")
    monkeypatch.setattr(
        main_mod.github, "fetch_events",
        lambda client: [
            {"type": "PushEvent", "created_at": "2026-06-18T14:30:00Z", "payload": {"size": 12}}
        ],
    )
    body = _client(monkeypatch).get("/oracle").json()
    assert body["presence"]["coding_rhythm"] == "heavy"


def test_oracle_presence_idle_without_token(monkeypatch):
    body = _client(monkeypatch).get("/oracle").json()  # GITHUB_USER defaults to ""
    assert body["presence"]["coding_rhythm"] == "idle"
```

- [ ] **Step 6: Run the full server suite** `cd server && ../.venv/bin/python -m pytest -q` — expect all pass.

- [ ] **Step 7: Lint/format** `.venv/bin/ruff check server/app/oracle.py server/app/main.py server/tests/test_oracle.py server/tests/test_main.py && .venv/bin/black server/app/oracle.py server/app/main.py server/tests/test_oracle.py server/tests/test_main.py`

- [ ] **Step 8: Commit**
```bash
git add server/app/oracle.py server/app/main.py server/tests/test_oracle.py server/tests/test_main.py
git commit -m "feat: fold GitHub presence into the /oracle payload"
```

---

# TIER 2 — DEVICE

## Task C1: Extend `slime/oracle.py` with presence

**Files:** Modify `slime/oracle.py`; Modify `tests/test_oracle_client.py`

- [ ] **Step 1: Add the failing tests** — append to `tests/test_oracle_client.py`:
```python
def _with_presence(rhythm, hours):
    return {
        "weather": {"tags": ["clear"], "temp_c": 25.0, "sunset_soon": False},
        "moon": {"phase": 2, "illum": 0.5},
        "presence": {"coding_rhythm": rhythm, "hours_since_push": hours},
    }


def test_parse_reads_presence():
    o = parse(_with_presence("heavy", 1.5))
    assert o.coding_rhythm == "heavy"
    assert o.hours_since_push == 1.5


def test_parse_defaults_presence_idle_when_absent():
    o = parse(_payload(["clear"]))  # no presence block
    assert o.coding_rhythm == "idle"
    assert o.hours_since_push is None


def test_heavy_rhythm_makes_it_content_alone():
    o = parse(_with_presence("heavy", 1.0))
    biased = mood_bias(Mood(60, 50, 50, 30, 40), o)
    assert biased.comfort > 50  # content/independent


def test_long_quiet_gap_makes_it_attentive():
    o = parse(_with_presence("idle", 100.0))
    biased = mood_bias(Mood(60, 60, 40, 30, 40), o)
    assert biased.curiosity > 40  # turns toward you


def test_busy_quip_tag():
    from slime.oracle import is_busy

    o = parse(_with_presence("heavy", 1.0))
    assert quip_tag(o) == "busy"
    assert is_busy(o) is True
    assert is_busy(parse(_with_presence("idle", 1.0))) is False


def test_cache_roundtrip_preserves_presence():
    o = parse(_with_presence("light", 4.5))
    o2 = unpack(pack(o))
    assert o2.coding_rhythm == "light"
    assert abs(o2.hours_since_push - 4.5) < 0.01
```

- [ ] **Step 2: Run** `.venv/bin/python -m pytest tests/test_oracle_client.py -v` — expect FAIL.

- [ ] **Step 3: Modify `slime/oracle.py`.** Make these changes:

(a) Extend the `Oracle` namedtuple:
```python
Oracle = namedtuple(
    "Oracle",
    ("weather_tag", "temp_c", "moon_phase", "moon_illum", "sunset_soon",
     "coding_rhythm", "hours_since_push"),
)
```

(b) Add presence constants near the other tuning constants:
```python
_RHYTHM_IDS = ("idle", "light", "heavy")
_RHYTHM_TARGETS = {
    "heavy": {"comfort": 78.0, "affection": 60.0, "energy": 62.0},  # independent + proud
    "light": {"comfort": 72.0},
}
_QUIET_GAP_HOURS = 36.0
```

(c) In `parse`, read the presence block and pass the two new fields to `Oracle(...)`:
```python
    p = payload.get("presence", {})
    return Oracle(
        weather_tag=tag,
        temp_c=w.get("temp_c"),
        moon_phase=m.get("phase", 0),
        moon_illum=m.get("illum", 0.0),
        sunset_soon=bool(w.get("sunset_soon", False)),
        coding_rhythm=p.get("coding_rhythm", "idle"),
        hours_since_push=p.get("hours_since_push"),
    )
```

(d) In `mood_bias`, after the weather/moon nudges (before the final `return clamp_mood(...)`), add:
```python
    for drive, target in _RHYTHM_TARGETS.get(oracle.coding_rhythm, {}).items():
        vals[drive] += (target - vals[drive]) * rate
    if oracle.hours_since_push is not None and oracle.hours_since_push >= _QUIET_GAP_HOURS:
        vals["curiosity"] += (70.0 - vals["curiosity"]) * rate  # attentive
        vals["affection"] += (65.0 - vals["affection"]) * rate
```

(e) In `quip_tag`, add presence tags just before the final `return None`:
```python
    if oracle.coding_rhythm in ("heavy", "light"):
        return "busy"
    if oracle.hours_since_push is not None and oracle.hours_since_push >= _QUIET_GAP_HOURS:
        return "quiet"
```

(f) Add an `is_busy` helper (after `quip_tag`):
```python
def is_busy(oracle):
    """True when there's notable recent coding activity (drives the journal 'busy' flag)."""
    return oracle is not None and oracle.coding_rhythm in ("heavy", "light")
```

(g) Extend the cache format. Replace the `_FMT`/`pack`/`unpack` with:
```python
_FMT = "<BBBffBf"  # tag_id, moon_phase, sunset, temp_c, moon_illum, rhythm_id, hours_since_push
SIZE = struct.calcsize(_FMT)


def pack(oracle):
    tag_id = _TAG_IDS.index(oracle.weather_tag) if oracle.weather_tag in _TAG_IDS else 0
    temp = oracle.temp_c if oracle.temp_c is not None else -999.0
    rhythm_id = _RHYTHM_IDS.index(oracle.coding_rhythm) if oracle.coding_rhythm in _RHYTHM_IDS else 0
    hours = oracle.hours_since_push if oracle.hours_since_push is not None else -1.0
    return struct.pack(
        _FMT, tag_id, oracle.moon_phase, 1 if oracle.sunset_soon else 0, temp, oracle.moon_illum,
        rhythm_id, hours,
    )


def unpack(blob):
    tag_id, phase, sunset, temp, illum, rhythm_id, hours = struct.unpack(_FMT, blob[:SIZE])
    return Oracle(
        weather_tag=_TAG_IDS[tag_id] if tag_id < len(_TAG_IDS) else "clear",
        temp_c=None if temp < -900.0 else temp,
        moon_phase=phase,
        moon_illum=illum,
        sunset_soon=bool(sunset),
        coding_rhythm=_RHYTHM_IDS[rhythm_id] if rhythm_id < len(_RHYTHM_IDS) else "idle",
        hours_since_push=None if hours < 0.0 else hours,
    )
```

- [ ] **Step 4: Run** `.venv/bin/python -m pytest tests/test_oracle_client.py -v` — expect PASS.

- [ ] **Step 5: Confirm host import clean** `.venv/bin/python -c "import slime.oracle"`.

- [ ] **Step 6: Lint/format** `.venv/bin/ruff check slime/oracle.py tests/test_oracle_client.py && .venv/bin/black slime/oracle.py tests/test_oracle_client.py`

- [ ] **Step 7: Commit**
```bash
git add slime/oracle.py tests/test_oracle_client.py
git commit -m "feat: blend GitHub presence into device oracle effects + cache"
```

---

## Task C2: Presence quip pools

**Files:** Modify `slime/quips.py`; Modify `tests/test_quips.py`

- [ ] **Step 1: Add the failing test** — append to `tests/test_quips.py`:
```python
def test_presence_quip_pools_exist():
    for tag in ("busy", "quiet"):
        assert tag in QUIPS
        assert len(QUIPS[tag]) >= 2
```

- [ ] **Step 2: Run** `.venv/bin/python -m pytest tests/test_quips.py -v` — expect FAIL.

- [ ] **Step 3: Add to the `QUIPS` dict in `slime/quips.py`**:
```python
    "busy": (
        "you've been deep in work",
        "i watched the clouds while you worked",
        "good work today",
    ),
    "quiet": (
        "it's quiet without you",
        "where did you wander?",
        "i kept your seat warm",
    ),
```

- [ ] **Step 4: Run** `.venv/bin/python -m pytest tests/test_quips.py -v` — expect PASS.

- [ ] **Step 5: Lint/format** `.venv/bin/ruff check slime/quips.py tests/test_quips.py && .venv/bin/black slime/quips.py tests/test_quips.py`

- [ ] **Step 6: Commit**
```bash
git add slime/quips.py tests/test_quips.py
git commit -m "feat: add presence (busy/quiet) quip pools"
```

---

## Task C3: Journal "busy" flag + entry phrase

**Files:** Modify `slime/journal.py`; Modify `tests/test_journal.py`

- [ ] **Step 1: Add the failing test** — append to `tests/test_journal.py`:
```python
def test_busy_flag_changes_the_entry_closing():
    busy = (100, 0, 0, 0b10, 0)  # flags bit1 = busy day
    line = generate_entry(busy, day_number=5, choice=lambda s: s[0])
    assert "you seemed busy" in line
```

- [ ] **Step 2: Run** `.venv/bin/python -m pytest tests/test_journal.py -v` — expect FAIL.

- [ ] **Step 3: Modify `generate_entry` in `slime/journal.py`** — branch on flags bit1 for the closing:
```python
def generate_entry(record, day_number, choice):
    """Regenerate the journal line for a record. `choice` picks a closing variant."""
    _, mood_dom, season, flags, _tier = record
    ambience = _SEASON_WORD.get(season, "the usual light")
    presence = "you came near" if flags & 0b1 else "a quiet day alone"
    if flags & 0b10:
        closing = "you seemed busy"
    else:
        closing = choice((_MOOD_WORD.get(mood_dom, "i watched the clouds"),))
    return "Day {} - {}. {}. {}.".format(day_number, ambience, presence, closing)
```

- [ ] **Step 4: Run** `.venv/bin/python -m pytest tests/test_journal.py -v` — expect PASS.

- [ ] **Step 5: Lint/format** `.venv/bin/ruff check slime/journal.py tests/test_journal.py && .venv/bin/black slime/journal.py tests/test_journal.py`

- [ ] **Step 6: Commit**
```bash
git add slime/journal.py tests/test_journal.py
git commit -m "feat: journal 'busy day' flag and entry phrase"
```

---

## Task C4: Set the journal busy flag from presence (`code.py`)

**Files:** Modify `code.py`

- [ ] **Step 1: Thread the oracle into `_maybe_journal`.** Change its signature and the `flags`
  computation. Replace the `_maybe_journal` definition's signature line and the `flags=` line:

Signature (add `oracle`):
```python
def _maybe_journal(display, state, season, synced_epoch, mono_at_sync, tz, ring, events, oracle):
```
Inside, replace the `record = journal.pack_record(...)` block's flags argument. The current call
passes `0b1 if "double_tap" in events else 0` as the 4th argument; change that argument to:
```python
        (0b1 if "double_tap" in events else 0)
        | (0b10 if oracle_mod.is_busy(oracle) else 0),
```

- [ ] **Step 2: Update the `_maybe_journal` call site** in `main()` to pass `oracle`:
```python
    state, ring = _maybe_journal(
        display, state, season, synced_epoch, mono_at_sync, tz, ring, events, oracle
    )
```
(The `oracle` local is already loaded earlier in `main()` by `_load_oracle`, before this call.)

- [ ] **Step 3: Syntax check** `.venv/bin/python -m py_compile code.py` — expect no output.

- [ ] **Step 4: Confirm host suite unaffected** `.venv/bin/python -m pytest -q` — expect all pass
  (the `_replace` guard scans `code.py`).

- [ ] **Step 5: Lint/format** `.venv/bin/ruff check code.py && .venv/bin/black --check code.py`

- [ ] **Step 6: Commit**
```bash
git add code.py
git commit -m "feat: set the journal busy flag from GitHub presence"
```

---

## Task C5: On-device verification

**Files:** none (deploy + verify only)

- [ ] **Step 1: Configure the server with a GitHub PAT.** On the machine running the oracle container,
  set `GITHUB_USER` and `GITHUB_TOKEN` (a fine-grained or classic PAT with `read:user`/public scope)
  in `server/docker-compose.yml` under `environment:` (or an `.env`), then restart:
  `cd server && docker compose up -d --build`. Confirm presence appears:
  `curl -s localhost:8080/oracle` → the JSON now has a `"presence"` block with a real `coding_rhythm`.

- [ ] **Step 2: Deploy the device code** (mounted at `/Volumes/CIRCUITPY`):
```bash
cp slime/oracle.py slime/quips.py slime/journal.py /Volumes/CIRCUITPY/slime/
cp code.py /Volumes/CIRCUITPY/
rm -rf /Volumes/CIRCUITPY/slime/__pycache__
sync
```

- [ ] **Step 3: Reboot and verify** over serial:
  1. [ ] Clean run (no traceback).
  2. [ ] After a boot fetch, REPL: `from slime import oracle; print(oracle.load_cache())` shows an
     `Oracle(...)` with the live `coding_rhythm` and `hours_since_push` populated.
  3. [ ] `from slime import oracle; o=oracle.load_cache(); print(oracle.quip_tag(o), oracle.is_busy(o))`
     reflects your real recent activity.
  4. [ ] Privacy check: confirm the `/oracle` JSON (and the device cache) contain **no** repo names or
     commit messages — only `coding_rhythm` + `hours_since_push`.

- [ ] **Step 4: Commit the milestone**
```bash
git commit --allow-empty -m "chore: Phase 2b-i verified (GitHub presence end-to-end)"
```

---

## Notes for the implementer

- **Privacy:** the PAT and all event detail stay in the server. `summarize` deliberately returns
  only a level + hours; never add repo/message fields to the payload, cache, or render path.
- **Offline-first:** `idle`/absent presence is a no-op on the device — the slime behaves as Phase 2a.
- **Cache format change is safe:** the oracle cache is its own ephemeral NVM slot; a stale
  smaller blob fails `struct.unpack`/the sanity check in `load_cache` and is simply re-fetched. State
  stays v3 — no migration.
- **`oracle` vs `oracle_mod`:** in `code.py` the module is imported as `oracle_mod`; the local Oracle
  instance is `oracle`. Keep that distinction (e.g. `oracle_mod.is_busy(oracle)`).
```
