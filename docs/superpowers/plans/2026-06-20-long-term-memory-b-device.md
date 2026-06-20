# Long-term Memory — Plan B: Device Milestones (Phase 2c-ii)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The device tracks a compact milestone bitmask in NVM (its core identity memory), occasionally voices a remembered milestone as a waking quip, and posts a day-memory to the server's episodic log each new day.

**Architecture:** State v4 adds a `milestones` int (NVM, with v3→v4 migration). A pure `milestones.py` evaluates/recalls. `code.py` evaluates milestones each cycle, surfaces a memory quip occasionally, and posts to `/remember` on a new journal day via a new `netmemory` adapter.

**Tech Stack:** CircuitPython (device), pytest (host tests for pure modules), black + ruff line-length 100.

**Spec:** `docs/superpowers/specs/2026-06-20-long-term-memory-design.md` (Plan B of two; Plan A — server episodic memory — is already merged on this branch).

**Conventions:** Pure modules import no hardware. Run device tests from repo ROOT with `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest`. `.venv` has black/ruff/pytest. Branch is `long-term-memory` (NOT main) — committing there is correct. `code.py`/`netmemory.py` are device-only (gate with `python3 -c "import ast; ..."`).

**Migration note (verified):** v3 blob is 53 bytes, v4 is 57 bytes; the journal-ring start `((BLOB_SIZE//16)+1)*16` is 64 for BOTH (53//16==57//16==3), so the journal ring + oracle cache offsets are unaffected. Persistence uses a leading version byte, so v3 blobs migrate cleanly (no trailing-garbage issue).

---

## File Structure

| File | Responsibility | Tested |
|------|----------------|--------|
| `slime/state.py` (modify) | `State` + `milestones`, `default_state`, `evolve` | `tests/test_state.py` |
| `slime/persistence.py` (modify) | v4 pack/unpack + v3→v4 migration | `tests/test_persistence.py` |
| `slime/milestones.py` (create) | pure `evaluate` + `memory_quip` | `tests/test_milestones.py` |
| `slime/netmemory.py` (create) | device adapter: POST /remember (fire-and-forget) | on-device |
| `code.py` (modify) | evaluate milestones, memory quip, post on new day | on-device |

---

## Task 1: State v4 — `milestones` field + NVM migration

**Files:**
- Modify: `slime/state.py`, `slime/persistence.py`
- Test: `tests/test_state.py`, `tests/test_persistence.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_state.py`:

```python
def test_default_state_has_zero_milestones():
    from slime.state import default_state

    assert default_state().milestones == 0


def test_evolve_sets_milestones():
    from slime.state import default_state, evolve

    s = evolve(default_state(), milestones=0b101)
    assert s.milestones == 0b101
    # other fields preserved
    assert s.familiarity == 0.0
```

Append to `tests/test_persistence.py` (create the file with this content if it does not exist):

```python
import struct

from slime import persistence
from slime.state import default_state, evolve


def test_v4_roundtrip_preserves_milestones():
    s = evolve(default_state(now=5.0), milestones=0b1011, total_boops=7)
    s2 = persistence.unpack(persistence.pack(s))
    assert s2.milestones == 0b1011
    assert s2.total_boops == 7


def test_v3_blob_migrates_milestones_to_zero():
    # Build a legacy v3 blob (version byte 3) and confirm it migrates with milestones=0.
    s = default_state(now=1.0)
    v3 = struct.pack(
        persistence._FORMAT_V3,
        3,
        s.mood.energy, s.mood.comfort, s.mood.curiosity, s.mood.sleepiness, s.mood.affection,
        s.last_seen, s.longest_absence, s.first_boot, s.total_boops,
        s.familiarity, s.visit_count, s.artifacts, s.last_journal_day_ordinal,
    )
    out = persistence.unpack(v3)
    assert out.milestones == 0
    assert out.total_boops == s.total_boops
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest tests/test_state.py tests/test_persistence.py -v`
Expected: FAIL — `State` has no `milestones`; v4 format/pack missing.

- [ ] **Step 3: Add `milestones` to `State`**

In `slime/state.py`:
- add `"milestones",  # int bitmask of reached long-term milestones` as the LAST field of the `State` namedtuple (after `last_journal_day_ordinal`).
- in `default_state`, add `milestones=0,` (after `last_journal_day_ordinal=0,`).
- in `evolve`, add to the reconstructed `State(...)` (after the `last_journal_day_ordinal=...` line):
```python
        milestones=changes.get("milestones", state.milestones),
```

- [ ] **Step 4: Bump persistence to v4**

In `slime/persistence.py`:
- change `NVM_VERSION = 3` to `NVM_VERSION = 4`.
- after the `_FORMAT_V3`/`_SIZE_V3` block add:
```python
# v4 (Phase 2c-ii): v3 fields + milestones (I).
_FORMAT_V4 = "<B5ffffIfIIII"
_SIZE_V4 = struct.calcsize(_FORMAT_V4)
```
- change `BLOB_SIZE = _SIZE_V3` to `BLOB_SIZE = _SIZE_V4`.
- in `pack`, change the format to `_FORMAT_V4`, the version arg to `NVM_VERSION` (now 4), and append `state.milestones` as the final packed field:
```python
def pack(state):
    """Serialize the durable parts of a State to a v4 NVM blob."""
    m = state.mood
    return struct.pack(
        _FORMAT_V4,
        NVM_VERSION,
        m.energy,
        m.comfort,
        m.curiosity,
        m.sleepiness,
        m.affection,
        state.last_seen,
        state.longest_absence,
        state.first_boot,
        state.total_boops,
        state.familiarity,
        state.visit_count,
        state.artifacts,
        state.last_journal_day_ordinal,
        state.milestones,
    )
```
- give `_build` a `milestones` parameter (add it to the signature as the last param) and pass it to `State(...)`:
```python
def _build(
    mood,
    last_seen,
    longest_absence,
    first_boot,
    total_boops,
    familiarity,
    visit_count,
    artifacts,
    last_journal_day_ordinal,
    milestones,
):
    """Construct a State from deserialized fields."""
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
        milestones=milestones,
    )
```
- update `unpack` to handle v4 and pass `milestones=0` for the older migrations:
```python
def unpack(blob):
    """Deserialize a v4 blob, migrating v3/v2/v1. Raises ValueError on bad data."""
    if len(blob) < 1:
        raise ValueError("nvm blob empty")
    version = blob[0]
    if version == 4:
        if len(blob) < _SIZE_V4:
            raise ValueError("nvm v4 blob too short")
        f = struct.unpack(_FORMAT_V4, blob[:_SIZE_V4])
        mood = Mood(*f[1:6])
        return _build(mood, f[6], f[7], f[8], f[9], f[10], f[11], f[12], f[13], f[14])
    if version == 3:
        if len(blob) < _SIZE_V3:
            raise ValueError("nvm v3 blob too short")
        f = struct.unpack(_FORMAT_V3, blob[:_SIZE_V3])
        mood = Mood(*f[1:6])
        return _build(mood, f[6], f[7], f[8], f[9], f[10], f[11], f[12], f[13], 0)
    if version == 2:
        if len(blob) < _SIZE_V2:
            raise ValueError("nvm v2 blob too short")
        f = struct.unpack(_FORMAT_V2, blob[:_SIZE_V2])
        mood = Mood(*f[1:6])
        return _build(mood, f[6], f[7], f[8], f[9], f[10], f[11], f[12], 0, 0)
    if version == 1:
        if len(blob) < _SIZE_V1:
            raise ValueError("nvm v1 blob too short")
        f = struct.unpack(_FORMAT_V1, blob[:_SIZE_V1])
        mood = Mood(*f[1:6])
        return _build(mood, f[6], f[7], f[8], f[9], 0.0, 0, 0, 0, 0)
    raise ValueError("nvm version unknown")
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest tests/test_state.py tests/test_persistence.py -v`
Expected: PASS (existing + new). Then the full device suite `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q` → all pass (the existing persistence/state tests still pass; v3→v4 migration keeps old blobs readable).

- [ ] **Step 6: Lint + commit**

```bash
source .venv/bin/activate
black --line-length 100 slime/state.py slime/persistence.py tests/test_state.py tests/test_persistence.py
ruff check slime/state.py slime/persistence.py tests/test_state.py tests/test_persistence.py
git add slime/state.py slime/persistence.py tests/test_state.py tests/test_persistence.py
git commit -m "feat: add milestones field to State + NVM v4 (v3->v4 migration)"
```

---

## Task 2: `milestones.py` — pure evaluate + recall

**Files:**
- Create: `slime/milestones.py`, `tests/test_milestones.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_milestones.py`:

```python
from collections import namedtuple

from slime import milestones

Ora = namedtuple("Ora", "weather_tag moon_phase")
St = namedtuple("St", "artifacts longest_absence")


def test_evaluate_sets_storm_and_full_moon():
    f = milestones.evaluate(0, Ora("storm_incoming", 4), St(0, 0.0), 0)
    assert f & milestones.FIRST_STORM
    assert f & milestones.FULL_MOON_NIGHT


def test_evaluate_bonded_collector_faithful():
    f = milestones.evaluate(0, Ora("clear", 2), St(0xFF, 7 * 24 * 3600.0), 3)
    assert f & milestones.BONDED
    assert f & milestones.COLLECTOR
    assert f & milestones.FAITHFUL


def test_evaluate_never_clears_and_tolerates_no_oracle():
    f = milestones.evaluate(milestones.FIRST_STORM, None, St(0, 0.0), 0)
    assert f & milestones.FIRST_STORM  # preserved even with no oracle and no conditions


def test_memory_quip_none_when_nothing_unlocked():
    assert milestones.memory_quip(0, lambda options: options[0]) is None


def test_memory_quip_returns_an_unlocked_line():
    line = milestones.memory_quip(milestones.BONDED, lambda options: options[0])
    assert isinstance(line, str) and "you and i" in line
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest tests/test_milestones.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'slime.milestones'`.

- [ ] **Step 3: Implement**

Create `slime/milestones.py`:

```python
"""Pure long-term milestones: notable firsts the pet has reached, as an NVM bitmask.

evaluate() never clears bits (a milestone, once reached, is remembered forever).
"""

FIRST_STORM = 0b00001
FULL_MOON_NIGHT = 0b00010
BONDED = 0b00100
COLLECTOR = 0b01000
FAITHFUL = 0b10000

_ALL_ARTIFACTS = 0xFF  # all 8 dream artifacts collected
_FAITHFUL_SECONDS = 7 * 24 * 3600.0  # a week-long absence weathered, then a return

_RECALL = (
    (FIRST_STORM, "i still remember our first storm"),
    (FULL_MOON_NIGHT, "i think of the night the moon was full"),
    (BONDED, "we have come a long way, you and i"),
    (COLLECTOR, "i kept every little treasure we found"),
    (FAITHFUL, "i waited, and you came back"),
)


def evaluate(flags, oracle, state, tier):
    """Return `flags` with any newly-met milestone bits set. Pure; never clears bits."""
    new = flags
    if oracle is not None:
        if oracle.weather_tag in ("storm_incoming", "monsoon"):
            new |= FIRST_STORM
        if oracle.moon_phase == 4:
            new |= FULL_MOON_NIGHT
    if tier >= 3:
        new |= BONDED
    if (state.artifacts & _ALL_ARTIFACTS) == _ALL_ARTIFACTS:
        new |= COLLECTOR
    if state.longest_absence >= _FAITHFUL_SECONDS:
        new |= FAITHFUL
    return new


def memory_quip(flags, choice):
    """Voice one unlocked milestone as a recall line, or None if none are unlocked. Pure."""
    unlocked = [line for bit, line in _RECALL if flags & bit]
    if not unlocked:
        return None
    return choice(unlocked)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest tests/test_milestones.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Lint + commit**

```bash
source .venv/bin/activate
black --line-length 100 slime/milestones.py tests/test_milestones.py
ruff check slime/milestones.py tests/test_milestones.py
git add slime/milestones.py tests/test_milestones.py
git commit -m "feat: add pure milestones (evaluate + memory_quip recall)"
```

---

## Task 3: Device wiring — `netmemory` + `code.py`

**Files:**
- Create: `slime/netmemory.py`
- Modify: `code.py`

Device-only. Gate: `python3 -c "import ast; ast.parse(open('code.py').read()); ast.parse(open('slime/netmemory.py').read()); print('ok')"`. READ `code.py`'s imports, `_render_frame`, `_maybe_journal`, the boot oracle load, and the scheduled-refresh block first.

- [ ] **Step 1: Create the `netmemory` adapter**

Create `slime/netmemory.py`:

```python
"""Hardware adapter: post a day-memory to the home server. Device-only. Never raises.

Mirrors netdream/netoracle: scheme-aware ORACLE_HOST, optional bearer, fire-and-forget.
"""

import os


def post(context):
    """POST `context` to <ORACLE_HOST>/remember; return True on apparent success, else False."""
    try:
        import json as _json
        import ssl

        import adafruit_requests
        import socketpool
        import wifi

        host = os.getenv("ORACLE_HOST")
        if not host:
            return False
        base = host if host.startswith(("http://", "https://")) else "http://" + host
        pool = socketpool.SocketPool(wifi.radio)
        session = adafruit_requests.Session(pool, ssl.create_default_context())
        headers = {"Content-Type": "application/json"}
        token = os.getenv("ORACLE_TOKEN")
        if token:
            headers["Authorization"] = "Bearer " + token
        resp = session.post(
            base.rstrip("/") + "/remember",
            data=_json.dumps(context),
            headers=headers,
            timeout=10,
        )
        resp.close()
        return True
    except Exception:
        return False
```

- [ ] **Step 2: Import milestones + netmemory in `code.py`**

In `code.py`'s `from slime import (...)` block, add `milestones` and `netmemory`, keeping the block alphabetical (`milestones` after `journal`, `netmemory` after `netdream`/before `netoracle`). `friendship`, `dreams`, `journal`, `evolve`, `pick` are already imported.

- [ ] **Step 3: Evaluate milestones at boot**

In `code.py` `main()`, immediately AFTER the boot oracle load and mood-bias (the line `weather_form = oracle_mod.form_override(oracle)`), add:

```python
    state = evolve(
        state,
        milestones=milestones.evaluate(
            state.milestones, oracle, state, friendship.tier(state.familiarity)
        ),
    )
```

- [ ] **Step 4: Re-evaluate milestones on the scheduled refresh**

In the USB scheduled-refresh block (inside `try:`, after `oracle = ...`/`weather_form = ...` are refreshed and before the `fields = _status_fields(...)` line), add:

```python
                    state = evolve(
                        state,
                        milestones=milestones.evaluate(
                            state.milestones, oracle, state, friendship.tier(state.familiarity)
                        ),
                    )
```

(Match the surrounding indentation of that block.)

- [ ] **Step 5: Surface a memory quip occasionally in `_render_frame`**

In `code.py` `_render_frame`, replace the quip-selection lines (currently:
```python
    otag = oracle_mod.quip_tag(oracle) if oracle is not None else None
    tag = otag or ("bonded" if ftier >= 3 else state.expression)
    quip = pick(tag) or pick(state.expression)
```
) with:

```python
    mem = None
    if _choice((False, False, False, False, True)):  # ~1 in 5 frames, voice a remembered milestone
        mem = milestones.memory_quip(state.milestones, _choice)
    otag = oracle_mod.quip_tag(oracle) if oracle is not None else None
    tag = otag or ("bonded" if ftier >= 3 else state.expression)
    quip = mem or pick(tag) or pick(state.expression)
```

(`ftier = friendship.tier(state.familiarity)` is already computed just above these lines; keep it. `_choice` is the module-level random helper.)

- [ ] **Step 6: Post a day-memory on a new journal day**

In `code.py` `_maybe_journal`, immediately AFTER `journal.save_ring(ring)` (and before `state = evolve(state, last_journal_day_ordinal=ordinal)`), add:

```python
    netmemory.post(
        dreams.dream_context(
            friendship.tier(state.familiarity),
            state.artifacts,
            journal.entries(ring),
            season,
            oracle,
        )
    )
```

(`netmemory.post` never raises; `_maybe_journal` already has `ring`, `season`, `oracle`, `state` in scope.)

- [ ] **Step 7: Offline gate + full host suite**

```bash
python3 -c "import ast; ast.parse(open('code.py').read()); ast.parse(open('slime/netmemory.py').read()); print('ok')"
source .venv/bin/activate
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q -p no:cacheprovider
```
Expected: `ok`, all host tests pass (code.py/netmemory are device-only, not imported by host tests).

- [ ] **Step 8: Lint + commit**

```bash
black --line-length 100 code.py slime/netmemory.py
ruff check code.py slime/netmemory.py
git add code.py slime/netmemory.py
git commit -m "feat: evaluate milestones, voice memory quips, post day-memories to the server"
```

- [ ] **Step 9: On-device + live-server verification**

1. With Plan A's server running (a memory volume), confirm a new day posts: `curl -s -X POST http://192.168.0.38:8080/remember -H 'content-type: application/json' -d '{"weather":"storm_incoming","moon":4}'` returns `{"ok": true}` and the log grows.
2. Deploy `code.py` + `slime/` to `CIRCUITPY`.
3. Over time confirm: milestones unlock (a storm/full-moon day, reaching the bonded tier); a "remember" quip surfaces occasionally; new days grow the server log; dreams begin referencing remembered moments (from Plan A's recall). With the server down, milestones/quips still work offline and dreams fall back.

---

## Self-Review

**Spec coverage (Plan B scope):**
- State v4 `milestones` int + v3→v4 migration + default 0 → Task 1. ✓
- Journal-ring/oracle-cache offsets unaffected (53/57 → ring start 64) → Task 1 migration note + full-suite check. ✓
- Pure `milestones.evaluate` (storm/full-moon/bonded/collector/faithful, never clears) + `memory_quip` → Task 2. ✓
- `netmemory.post` adapter (scheme-aware, fire-and-forget) → Task 3 Step 1. ✓
- Evaluate milestones each cycle (boot + scheduled refresh) + persist → Task 3 Steps 3–4 (persistence.save already runs after these in main()/the refresh block). ✓
- Waking memory quip surfaced occasionally → Task 3 Step 5. ✓
- Post day-memory on new journal day → Task 3 Step 6. ✓
- Offline-first (milestones pure/offline; netmemory never raises) → Tasks 2/3. ✓

**Placeholder scan:** No TBD/TODO; every code step has full code. The "match surrounding indentation" notes are guard instructions for exact-location edits, not placeholders (full code given). ✓

**Type consistency:** `milestones.evaluate(flags, oracle, state, tier)` and `memory_quip(flags, choice)` signatures match their `code.py` call sites; `State.milestones` added in Task 1 is read in Task 3. `dreams.dream_context(tier, artifacts_mask, journal_records, season, oracle)` (from 2c-i) is called in Task 3 Step 6 with those exact args. `netmemory.post(context)` matches. `_build(...)` gains a `milestones` param consistently used by all four `unpack` branches (v4 passes f[14], v3/v2/v1 pass 0). `_FORMAT_V4`/`_SIZE_V4`/`BLOB_SIZE` consistent. ✓
