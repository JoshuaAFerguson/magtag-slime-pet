# Phase 1a — Richer Offline Behaviors Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deepen the offline slime — body forms, a visit-based friendship bond that unlocks content, piezo sound motifs, and nightly dreams that yield collectible artifacts — while preserving Phase-0 progress.

**Architecture:** Extends the Phase-0 pure/adapter split. New pure modules (`friendship`, `forms`, `dreams`, `motifs`) and extensions (`state`, `visuals`, `quips`, `persistence`) are host-tested; new/extended adapters (`sound`, `display`) and `code.py` are verified on-device. State stays NVM-only; the struct bumps v1→v2 with migration so existing pets keep their memories.

**Tech Stack:** CircuitPython 10.x (ESP32-S2); `pwmio` (piezo tones); existing `displayio`/`neopixel`/`adafruit_lis3dh`. Host testing: pytest (run via `.venv/bin/python -m pytest`), ruff, black.

**Conventions:** Always run Python via `.venv/bin/python`. Pure modules must NOT import hardware libs. Never use `namedtuple._replace` (use `state.evolve`). After each task, the changed code must pass `.venv/bin/ruff check .` and `.venv/bin/black --check .` (line length 100).

---

## File Structure

```
slime/
  state.py        # MODIFY: add familiarity, visit_count, artifacts; extend evolve/default_state
  friendship.py   # NEW (pure): visit-based familiarity, tiers, unlock gates
  forms.py        # NEW (pure): choose render frame from mood + tier + sleeping
  motifs.py       # NEW (pure): tone-sequence data + selection
  dreams.py       # NEW (pure): dream assembly, artifacts, should_dream
  quips.py        # MODIFY: add quips + a tier-gated "bonded" pool
  visuals.py      # MODIFY: extend POSE_INDEX with 5 form frames
  persistence.py  # MODIFY: NVM struct v2 + v1->v2 migration
  sound.py        # NEW (adapter): play a motif on the piezo
  display.py      # MODIFY: render_frame() + render_dream()
sim/simulator.py  # MODIFY: multi-day run exercising familiarity/forms/dream
assets/make_assets.py  # MODIFY: 12-frame sprite sheet
code.py           # MODIFY: integrate forms, friendship, sound, dream-on-wake; fix gap tracking
```

Pure modules tested on host: `state`, `friendship`, `forms`, `motifs`, `dreams`, `quips`,
`visuals`, `persistence`, `sim/simulator`.

---

## Task 1: Extend `slime/state.py` with friendship + artifacts fields

**Files:** Modify `slime/state.py`; Modify `tests/test_state.py`

- [ ] **Step 1: Add the failing tests** — append to `tests/test_state.py`:

```python
def test_state_has_friendship_and_artifact_fields():
    s = default_state(now=0.0)
    assert s.familiarity == 0.0
    assert s.visit_count == 0
    assert s.artifacts == 0


def test_evolve_updates_new_fields():
    s = default_state(now=0.0)
    s2 = evolve(s, familiarity=12.0, visit_count=3, artifacts=5)
    assert s2.familiarity == 12.0
    assert s2.visit_count == 3
    assert s2.artifacts == 5
    assert s.familiarity == 0.0  # original unchanged
```

- [ ] **Step 2: Run** `.venv/bin/python -m pytest tests/test_state.py -v` — expect FAIL (`AttributeError`/unexpected kwarg).

- [ ] **Step 3: Modify `slime/state.py`.** Replace the `State` namedtuple, `default_state`, and `evolve`:

```python
State = namedtuple(
    "State",
    (
        "mood",             # Mood
        "last_seen",        # float seconds (monotonic-based)
        "total_boops",      # int
        "longest_absence",  # float seconds
        "first_boot",       # float seconds
        "expression",       # str
        "behavior",         # str
        "familiarity",      # float 0..100, only ever rises
        "visit_count",      # int
        "artifacts",        # int bitmask of collected dream artifacts
    ),
)
```

```python
def default_state(now=0.0):
    """A gentle starting personality: comfortable, mildly curious, awake."""
    return State(
        mood=Mood(energy=60.0, comfort=70.0, curiosity=50.0, sleepiness=30.0, affection=40.0),
        last_seen=now,
        total_boops=0,
        longest_absence=0.0,
        first_boot=now,
        expression="content",
        behavior="idle",
        familiarity=0.0,
        visit_count=0,
        artifacts=0,
    )
```

```python
def evolve(state, **changes):
    """Return a new State with the given fields changed (CircuitPython-safe; no _replace)."""
    return State(
        mood=changes.get("mood", state.mood),
        last_seen=changes.get("last_seen", state.last_seen),
        total_boops=changes.get("total_boops", state.total_boops),
        longest_absence=changes.get("longest_absence", state.longest_absence),
        first_boot=changes.get("first_boot", state.first_boot),
        expression=changes.get("expression", state.expression),
        behavior=changes.get("behavior", state.behavior),
        familiarity=changes.get("familiarity", state.familiarity),
        visit_count=changes.get("visit_count", state.visit_count),
        artifacts=changes.get("artifacts", state.artifacts),
    )
```

- [ ] **Step 4: Run** `.venv/bin/python -m pytest tests/test_state.py -v` — expect PASS.

- [ ] **Step 5: Lint/format** `.venv/bin/ruff check slime/state.py tests/test_state.py && .venv/bin/black slime/state.py tests/test_state.py`

- [ ] **Step 6: Commit**
```bash
git add slime/state.py tests/test_state.py
git commit -m "feat: extend State with familiarity, visit_count, artifacts"
```

---

## Task 2: `slime/friendship.py` — visit-based familiarity (PURE)

**Files:** Create `slime/friendship.py`; Test `tests/test_friendship.py`

- [ ] **Step 1: Write the failing tests** — `tests/test_friendship.py`:

```python
from slime.friendship import (
    update, tier, unlocked_forms, personal_dreams_unlocked, VISIT_GAP,
)


def test_positive_event_raises_familiarity():
    fam, visits = update(10.0, 0, ("double_tap",), gap=5.0)
    assert fam > 10.0
    assert visits == 0  # short gap -> not a new visit


def test_return_after_long_gap_counts_as_visit():
    fam, visits = update(10.0, 2, ("tap",), gap=VISIT_GAP + 1.0)
    assert visits == 3
    assert fam > 10.0 + 1.5  # got the larger visit bonus too


def test_no_events_no_change():
    fam, visits = update(30.0, 4, (), gap=99999.0)
    assert fam == 30.0 and visits == 4


def test_familiarity_never_exceeds_100():
    fam, _ = update(99.5, 0, ("double_tap", "pickup"), gap=VISIT_GAP + 1)
    assert fam == 100.0


def test_tiers_increase_with_familiarity():
    assert tier(0.0) == 0
    assert tier(25.0) == 1
    assert tier(45.0) == 2
    assert tier(65.0) == 3
    assert tier(85.0) == 4


def test_form_unlocks_by_tier():
    assert "explorer" not in unlocked_forms(0)
    assert "explorer" in unlocked_forms(1)
    assert "crowned" not in unlocked_forms(2)
    assert "crowned" in unlocked_forms(3)


def test_personal_dreams_unlock_at_tier_2():
    assert personal_dreams_unlocked(1) is False
    assert personal_dreams_unlocked(2) is True
```

- [ ] **Step 2: Run** `.venv/bin/python -m pytest tests/test_friendship.py -v` — expect FAIL (no module).

- [ ] **Step 3: Implement `slime/friendship.py`:**

```python
"""Pure friendship/familiarity model. Grows from interaction + visits; never falls."""

PER_EVENT = 1.5      # familiarity gained per positive interaction
PER_VISIT = 6.0      # extra gained when activity resumes after a long quiet gap
VISIT_GAP = 1800.0   # seconds of quiet before a return counts as a new visit
_POSITIVE = ("double_tap", "tap", "pickup")
_TIER_THRESHOLDS = (20.0, 40.0, 60.0, 80.0)  # -> tiers 0,1,2,3,4


def update(familiarity, visit_count, events, gap):
    """Return (familiarity, visit_count) after applying events. Never decreases familiarity."""
    has_positive = any(e in _POSITIVE for e in events)
    if has_positive:
        familiarity += PER_EVENT
    if events and gap >= VISIT_GAP:
        familiarity += PER_VISIT
        visit_count += 1
    if familiarity > 100.0:
        familiarity = 100.0
    return familiarity, visit_count


def tier(familiarity):
    """Integer band 0..4 from familiarity."""
    band = 0
    for threshold in _TIER_THRESHOLDS:
        if familiarity >= threshold:
            band += 1
    return band


def unlocked_forms(tier_level):
    """Forms unlocked at a tier. Explorer at >=1, crowned at >=3."""
    forms = ()
    if tier_level >= 1:
        forms += ("explorer",)
    if tier_level >= 3:
        forms += ("crowned",)
    return forms


def personal_dreams_unlocked(tier_level):
    """Personal dream references unlock at tier 2+."""
    return tier_level >= 2
```

- [ ] **Step 4: Run** `.venv/bin/python -m pytest tests/test_friendship.py -v` — expect PASS (7 passed).

- [ ] **Step 5: Lint/format** `.venv/bin/ruff check slime/friendship.py tests/test_friendship.py && .venv/bin/black slime/friendship.py tests/test_friendship.py`

- [ ] **Step 6: Commit**
```bash
git add slime/friendship.py tests/test_friendship.py
git commit -m "feat: add pure visit-based friendship model with tiers and unlocks"
```

---

## Task 3: Form frames + `slime/forms.py` (PURE)

**Files:** Modify `slime/visuals.py`; Create `slime/forms.py`; Test `tests/test_forms.py`

- [ ] **Step 1: Extend `POSE_INDEX` in `slime/visuals.py`** — replace the `POSE_INDEX` dict:

```python
POSE_INDEX = {
    "content": 0,
    "sleepy": 1,
    "curious": 2,
    "happy": 3,
    "contemplative": 4,
    "dizzy": 5,
    "resting": 6,
    "puddle": 7,
    "loaf": 8,
    "explorer": 9,
    "crowned": 10,
    "wisp": 11,
}
```

- [ ] **Step 2: Write the failing tests** — `tests/test_forms.py`:

```python
from slime.state import Mood
from slime.visuals import POSE_INDEX
from slime.forms import choose_render


def test_sleeping_renders_loaf():
    assert choose_render(Mood(50, 60, 40, 90, 40), tier=4, sleeping=True) == POSE_INDEX["loaf"]


def test_very_low_energy_renders_puddle():
    assert choose_render(Mood(8, 60, 40, 40, 40), tier=4, sleeping=False) == POSE_INDEX["puddle"]


def test_explorer_requires_tier_unlock():
    eager = Mood(80, 60, 85, 20, 40)
    # tier 0: not unlocked -> falls through to the curious face
    assert choose_render(eager, tier=0, sleeping=False) == POSE_INDEX["curious"]
    # tier 1: explorer unlocked
    assert choose_render(eager, tier=1, sleeping=False) == POSE_INDEX["explorer"]


def test_crowned_requires_high_tier_and_affection():
    bonded = Mood(70, 70, 40, 20, 90)
    assert choose_render(bonded, tier=2, sleeping=False) != POSE_INDEX["crowned"]
    assert choose_render(bonded, tier=3, sleeping=False) == POSE_INDEX["crowned"]


def test_long_quiet_low_drive_renders_wisp():
    quiet = Mood(30, 60, 15, 40, 40)
    assert choose_render(quiet, tier=0, sleeping=False) == POSE_INDEX["wisp"]


def test_default_falls_back_to_expression_face():
    calm = Mood(60, 80, 50, 30, 40)  # derive_expression -> content
    assert choose_render(calm, tier=4, sleeping=False) == POSE_INDEX["content"]
```

- [ ] **Step 3: Run** `.venv/bin/python -m pytest tests/test_forms.py -v` — expect FAIL (no module).

- [ ] **Step 4: Implement `slime/forms.py`:**

```python
"""Pure body-form selection: mood + familiarity tier + sleep -> sprite frame index."""
from slime.friendship import unlocked_forms
from slime.mood import derive_expression
from slime.visuals import POSE_INDEX


def choose_render(mood, tier, sleeping):
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
    return POSE_INDEX[derive_expression(mood)]
```

> Note on priority: `loaf` and `puddle` come before `explorer`/`crowned`, and `wisp` (low-drive
> contemplative) is checked after the unlocked active forms so an eager bonded slime still gets
> explorer/crowned. The test cases pin these boundaries.

- [ ] **Step 5: Run** `.venv/bin/python -m pytest tests/test_forms.py tests/test_visuals.py -v` — expect PASS.

- [ ] **Step 6: Lint/format** `.venv/bin/ruff check slime/forms.py slime/visuals.py tests/test_forms.py && .venv/bin/black slime/forms.py slime/visuals.py tests/test_forms.py`

- [ ] **Step 7: Commit**
```bash
git add slime/forms.py slime/visuals.py tests/test_forms.py
git commit -m "feat: add form selection and extend sprite frame index"
```

---

## Task 4: `slime/motifs.py` — tone sequences (PURE)

**Files:** Create `slime/motifs.py`; Test `tests/test_motifs.py`

- [ ] **Step 1: Write the failing tests** — `tests/test_motifs.py`:

```python
from slime.motifs import pick_motif, MOTIFS


def test_known_contexts_return_tone_sequences():
    for context in ("greeting", "wake", "dizzy", "sleepy", "dream"):
        motif = pick_motif(context)
        assert motif and all(len(step) == 2 for step in motif)  # (freq, ms) pairs


def test_unknown_context_returns_none():
    assert pick_motif("nonsense") is None


def test_high_tier_greeting_is_richer():
    base = pick_motif("greeting", tier=0)
    bonded = pick_motif("greeting", tier=3)
    assert bonded != base
    assert len(bonded) >= len(base)
```

- [ ] **Step 2: Run** `.venv/bin/python -m pytest tests/test_motifs.py -v` — expect FAIL (no module).

- [ ] **Step 3: Implement `slime/motifs.py`:**

```python
"""Pure tone-sequence data + selection. Each motif is a tuple of (freq_hz, duration_ms)."""

MOTIFS = {
    "greeting": ((660, 90), (880, 120)),
    "wake": ((523, 80), (659, 90)),
    "dizzy": ((420, 70), (300, 70), (420, 70)),
    "sleepy": ((440, 130), (330, 170)),
    "dream": ((784, 70), (988, 90), (1319, 140)),
}

# A warmer greeting unlocked once the bond is deep (tier 3+).
_BONDED_GREETING = ((660, 90), (880, 90), (1047, 150))


def pick_motif(context, tier=0):
    """Return the (freq, ms) sequence for a context, or None if unknown."""
    if context == "greeting" and tier >= 3:
        return _BONDED_GREETING
    return MOTIFS.get(context)
```

- [ ] **Step 4: Run** `.venv/bin/python -m pytest tests/test_motifs.py -v` — expect PASS (3 passed).

- [ ] **Step 5: Lint/format** `.venv/bin/ruff check slime/motifs.py tests/test_motifs.py && .venv/bin/black slime/motifs.py tests/test_motifs.py`

- [ ] **Step 6: Commit**
```bash
git add slime/motifs.py tests/test_motifs.py
git commit -m "feat: add pure piezo tone-motif data and selection"
```

---

## Task 5: `slime/dreams.py` — dream assembly + artifacts (PURE)

**Files:** Create `slime/dreams.py`; Test `tests/test_dreams.py`

- [ ] **Step 1: Write the failing tests** — `tests/test_dreams.py`:

```python
from slime.dreams import (
    generate, should_dream, artifact_name, add_artifact, has_artifact, ARTIFACTS,
)


def first(seq):
    return seq[0]


def test_should_dream_only_after_long_sleep():
    assert should_dream(slept=True, sleep_seconds=1200.0) is True
    assert should_dream(slept=True, sleep_seconds=10.0) is False
    assert should_dream(slept=False, sleep_seconds=9999.0) is False


def test_generate_is_deterministic_with_injected_choice():
    line1, art1 = generate(tier=0, artifacts_mask=0, choice=first)
    line2, art2 = generate(tier=0, artifacts_mask=0, choice=first)
    assert line1 == line2 and art1 == art2
    assert isinstance(line1, str) and line1.endswith(".")


def test_personal_reference_only_at_tier_2_plus():
    line_low, _ = generate(tier=1, artifacts_mask=0, choice=first)
    line_high, _ = generate(tier=2, artifacts_mask=0, choice=first)
    assert len(line_high) > len(line_low)


def test_generate_can_find_an_uncollected_artifact():
    # choice=first makes the "find?" gate pick its first (truthy) option and the first uncollected id
    _, art = generate(tier=0, artifacts_mask=0, choice=first)
    assert art == 0  # first uncollected artifact


def test_artifact_bitmask_helpers():
    mask = add_artifact(0, 2)
    assert has_artifact(mask, 2) is True
    assert has_artifact(mask, 1) is False
    assert artifact_name(2) == ARTIFACTS[2]
```

- [ ] **Step 2: Run** `.venv/bin/python -m pytest tests/test_dreams.py -v` — expect FAIL (no module).

- [ ] **Step 3: Implement `slime/dreams.py`:**

```python
"""Pure dream assembly + collectible artifacts. Deterministic via an injected choice()."""

ARTIFACTS = (
    "Moon Pebble",
    "Purple Sand",
    "Tiny Crown",
    "Bent Key",
    "Star Feather",
    "Silver Leaf",
    "Glass Bead",
    "Owl Feather",
)

_ACTS = ("I crossed", "I floated over", "I waited at", "I drifted past", "I remembered")
_PLACES = (
    "a desert beneath a purple moon",
    "the Silver Pond",
    "the edge of the Quiet Sea",
    "a field of slow clouds",
    "the Hall of the Owl King",
)
_PERSONAL = ("You were there, watching", "I looked for you", "I carried your warmth")

_MIN_SLEEP = 900.0  # seconds asleep before a dream forms


def should_dream(slept, sleep_seconds):
    """A dream forms only on waking from a sufficiently long sleep."""
    return bool(slept) and sleep_seconds >= _MIN_SLEEP


def generate(tier, artifacts_mask, choice):
    """Assemble one dream line and maybe an artifact id. `choice(seq)` picks from a sequence."""
    line = choice(_ACTS) + " " + choice(_PLACES) + "."
    if tier >= 2:
        line += " " + choice(_PERSONAL) + "."

    artifact_id = None
    # ~1-in-4 chance to find something, decided via the injected choice for testability.
    if choice((True, False, False, False)):
        uncollected = [i for i in range(len(ARTIFACTS)) if not has_artifact(artifacts_mask, i)]
        if uncollected:
            artifact_id = choice(uncollected)
    return line, artifact_id


def artifact_name(artifact_id):
    return ARTIFACTS[artifact_id]


def has_artifact(mask, artifact_id):
    return bool((mask >> artifact_id) & 1)


def add_artifact(mask, artifact_id):
    return mask | (1 << artifact_id)
```

- [ ] **Step 4: Run** `.venv/bin/python -m pytest tests/test_dreams.py -v` — expect PASS (5 passed).

- [ ] **Step 5: Lint/format** `.venv/bin/ruff check slime/dreams.py tests/test_dreams.py && .venv/bin/black slime/dreams.py tests/test_dreams.py`

- [ ] **Step 6: Commit**
```bash
git add slime/dreams.py tests/test_dreams.py
git commit -m "feat: add pure dream assembly and artifact memory"
```

---

## Task 6: Extend `slime/quips.py` with a tier-gated pool (PURE)

**Files:** Modify `slime/quips.py`; Modify `tests/test_quips.py`

- [ ] **Step 1: Add the failing test** — append to `tests/test_quips.py`:

```python
def test_bonded_pool_exists_for_high_tier_personal_quips():
    assert "bonded" in QUIPS
    assert len(QUIPS["bonded"]) >= 2
    assert pick("bonded", choice=lambda seq: seq[0]) == QUIPS["bonded"][0]
```

- [ ] **Step 2: Run** `.venv/bin/python -m pytest tests/test_quips.py -v` — expect FAIL (`bonded` missing).

- [ ] **Step 3: Modify `slime/quips.py`** — add a `"bonded"` entry to the `QUIPS` dict (insert before the closing brace):

```python
    "bonded": (
        "i kept your warmth",
        "you again — good",
        "our quiet is the best quiet",
    ),
```

- [ ] **Step 4: Run** `.venv/bin/python -m pytest tests/test_quips.py -v` — expect PASS.

- [ ] **Step 5: Lint/format** `.venv/bin/ruff check slime/quips.py tests/test_quips.py && .venv/bin/black slime/quips.py tests/test_quips.py`

- [ ] **Step 6: Commit**
```bash
git add slime/quips.py tests/test_quips.py
git commit -m "feat: add tier-gated bonded quip pool"
```

---

## Task 7: `slime/persistence.py` — NVM v2 with v1 migration

**Files:** Modify `slime/persistence.py`; Modify `tests/test_persistence.py`

- [ ] **Step 1: Add the failing tests** — append to `tests/test_persistence.py`:

```python
import struct

from slime.persistence import _FORMAT_V1, pack


def test_v2_roundtrip_includes_new_fields():
    s = default_state(now=1.0)
    s2 = evolve(s, familiarity=42.0, visit_count=5, artifacts=9)
    out = unpack(pack(s2))
    assert out.familiarity == 42.0
    assert out.visit_count == 5
    assert out.artifacts == 9


def test_v1_blob_migrates_preserving_core_progress():
    # Build a legacy v1 blob by hand: version 1, mood(5f), last_seen, longest_absence,
    # first_boot, total_boops — and confirm unpack keeps it and defaults the new fields.
    blob = struct.pack(_FORMAT_V1, 1, 11.0, 22.0, 33.0, 44.0, 55.0, 100.0, 7.0, 1.0, 9)
    out = unpack(blob)
    assert tuple(out.mood) == (11.0, 22.0, 33.0, 44.0, 55.0)
    assert out.total_boops == 9
    assert out.last_seen == 100.0
    # new fields default
    assert out.familiarity == 0.0 and out.visit_count == 0 and out.artifacts == 0


def test_unpack_rejects_unknown_version():
    blob = bytearray(pack(default_state()))
    blob[0] = 99
    try:
        unpack(bytes(blob))
        assert False, "expected ValueError"
    except ValueError:
        pass
```

(The existing `evolve`/`default_state` import line at the top of `tests/test_persistence.py` must
include `evolve`; update it to `from slime.state import Mood, default_state, evolve`.)

- [ ] **Step 2: Run** `.venv/bin/python -m pytest tests/test_persistence.py -v` — expect FAIL.

- [ ] **Step 3: Rewrite `slime/persistence.py`:**

```python
"""Persist core state to microcontroller NVM. pack/unpack pure; save/load touch hardware."""
import struct

from slime import mood as mood_engine
from slime.state import Mood, State, default_state

NVM_VERSION = 2

# v1 (Phase 0): version + 5 mood floats + last_seen + longest_absence + first_boot + total_boops.
_FORMAT_V1 = "<B5ffffI"
_SIZE_V1 = struct.calcsize(_FORMAT_V1)

# v2 (Phase 1): v1 fields + familiarity (f) + visit_count (I) + artifacts (I).
_FORMAT_V2 = "<B5ffffIfII"
_SIZE_V2 = struct.calcsize(_FORMAT_V2)

BLOB_SIZE = _SIZE_V2


def pack(state):
    """Serialize the durable parts of a State to a v2 NVM blob."""
    m = state.mood
    return struct.pack(
        _FORMAT_V2,
        NVM_VERSION,
        m.energy, m.comfort, m.curiosity, m.sleepiness, m.affection,
        state.last_seen, state.longest_absence, state.first_boot,
        state.total_boops,
        state.familiarity, state.visit_count, state.artifacts,
    )


def _build(mood, last_seen, longest_absence, first_boot, total_boops,
           familiarity, visit_count, artifacts):
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
    )


def unpack(blob):
    """Deserialize a v2 blob, migrating a v1 blob. Raises ValueError on bad data."""
    if len(blob) < 1:
        raise ValueError("nvm blob empty")
    version = blob[0]
    if version == 2:
        if len(blob) < _SIZE_V2:
            raise ValueError("nvm v2 blob too short")
        f = struct.unpack(_FORMAT_V2, blob[:_SIZE_V2])
        mood = Mood(*f[1:6])
        return _build(mood, f[6], f[7], f[8], f[9], f[10], f[11], f[12])
    if version == 1:
        if len(blob) < _SIZE_V1:
            raise ValueError("nvm v1 blob too short")
        f = struct.unpack(_FORMAT_V1, blob[:_SIZE_V1])
        mood = Mood(*f[1:6])
        # migrate: keep Phase-0 progress, default the new fields
        return _build(mood, f[6], f[7], f[8], f[9], 0.0, 0, 0)
    raise ValueError("nvm version unknown")


def save(state):
    """Write state to NVM. Device-only."""
    import microcontroller

    microcontroller.nvm[0:BLOB_SIZE] = pack(state)


def load(now=0.0):
    """Read state from NVM; return default_state on any problem. Device-only."""
    import microcontroller

    try:
        return unpack(bytes(microcontroller.nvm[0:BLOB_SIZE]))
    except Exception:
        return default_state(now)
```

- [ ] **Step 4: Run** `.venv/bin/python -m pytest tests/test_persistence.py -v` — expect PASS.

- [ ] **Step 5: Lint/format** `.venv/bin/ruff check slime/persistence.py tests/test_persistence.py && .venv/bin/black slime/persistence.py tests/test_persistence.py`

- [ ] **Step 6: Commit**
```bash
git add slime/persistence.py tests/test_persistence.py
git commit -m "feat: NVM v2 persistence with v1->v2 migration (preserves Phase-0 progress)"
```

---

## Task 8: 12-frame sprite sheet

**Files:** Modify `assets/make_assets.py`; regenerate `assets/slime.bmp`

- [ ] **Step 1: Modify `assets/make_assets.py`.** Extend the `POSES` list and add form-drawing
  branches. Replace the `POSES` line:

```python
POSES = [
    "content", "sleepy", "curious", "happy", "contemplative", "dizzy", "resting",
    "puddle", "loaf", "explorer", "crowned", "wisp",
]
```

  Then add these branches inside `draw_pose` (before the final `else:  # content`):

```python
    elif pose == "puddle":
        d.rectangle([ox + 8, 44, ox + 56, 56], fill=BLACK)
        d.rectangle([ox + 10, 46, ox + 54, 54], fill=GRAY)
        d.rectangle([ox + 24, 49, ox + 28, 51], fill=BLACK)
        d.rectangle([ox + 36, 49, ox + 40, 51], fill=BLACK)
    elif pose == "loaf":
        d.rectangle([ox + 14, 26, ox + 50, 56], fill=BLACK)
        d.rectangle([ox + 16, 28, ox + 48, 54], fill=GRAY)
        d.rectangle([ox + 24, 40, ox + 32, 42], fill=BLACK)
        d.rectangle([ox + 36, 40, ox + 44, 42], fill=BLACK)
    elif pose == "explorer":
        _blob(d, ox)
        d.rectangle([ox + 22, 8, ox + 42, 16], fill=BLACK)   # cap
        d.rectangle([ox + 18, 14, ox + 46, 18], fill=BLACK)  # brim
        _eyes(d, ox, 30, h=12)
    elif pose == "crowned":
        _blob(d, ox)
        d.polygon(
            [(ox + 22, 14), (ox + 28, 4), (ox + 32, 12), (ox + 38, 2),
             (ox + 44, 12), (ox + 50, 4), (ox + 44, 14)],
            fill=BLACK,
        )
        _eyes(d, ox, 32)
    elif pose == "wisp":
        d.rectangle([ox + 18, 16, ox + 46, 48], fill=LIGHT)
        d.rectangle([ox + 20, 18, ox + 44, 46], fill=GRAY)
        for wx in (ox + 20, ox + 30, ox + 40):
            d.rectangle([wx, 50, wx + 6, 54], fill=GRAY)
        d.rectangle([ox + 26, 30, ox + 30, 36], fill=BLACK)
        d.rectangle([ox + 36, 30, ox + 40, 36], fill=BLACK)
```

- [ ] **Step 2: Regenerate** `.venv/bin/python assets/make_assets.py` — expect `wrote assets/slime.bmp (768x64, 12 frames)`.

- [ ] **Step 3: Verify** `.venv/bin/python -c "from PIL import Image; im=Image.open('assets/slime.bmp'); print(im.mode, im.size)"` — expect `P (768, 64)`.

- [ ] **Step 4: Lint/format** `.venv/bin/ruff check assets/make_assets.py && .venv/bin/black assets/make_assets.py`

- [ ] **Step 5: Commit**
```bash
git add assets/make_assets.py assets/slime.bmp
git commit -m "feat: add five form frames to the sprite sheet (12 total)"
```

---

## Task 9: Extend the simulator (PURE)

**Files:** Modify `sim/simulator.py`; Modify `tests/test_simulator.py`

- [ ] **Step 1: Add the failing test** — append to `tests/test_simulator.py`:

```python
def test_repeated_visits_grow_familiarity():
    timeline = run_day()
    assert timeline[-1].familiarity > timeline[0].familiarity
```

- [ ] **Step 2: Run** `.venv/bin/python -m pytest tests/test_simulator.py -v` — expect FAIL (`Tick` has no `familiarity`).

- [ ] **Step 3: Modify `sim/simulator.py`.** Replace the `Tick` definition and `run_day` body to
  track familiarity through the friendship model:

```python
from slime import friendship
from slime.state import default_state, evolve
from slime.mood import Inputs, step
from slime.quips import pick

Tick = namedtuple(
    "Tick", ("hour", "light", "mood", "expression", "behavior", "quip", "familiarity")
)
```

```python
def run_day():
    """Return a list of Tick across the scripted day, tracking familiarity."""
    state = default_state(now=0.0)
    timeline = []
    last_interaction = 0.0
    for hour, light, events in _SCRIPT:
        now = hour * 3600.0
        gap = now - last_interaction
        if events:
            last_interaction = now
        inputs = Inputs(
            light=light,
            battery=0.8,
            on_usb=True,
            seconds_since_interaction=gap,
            events=events,
        )
        state = step(state, inputs, dt=_STEP_SECONDS)
        fam, visits = friendship.update(state.familiarity, state.visit_count, events, gap)
        state = evolve(state, familiarity=fam, visit_count=visits)
        quip = pick(
            state.behavior if state.behavior == "greeting" else state.expression,
            choice=lambda seq: seq[0],
        )
        timeline.append(
            Tick(hour, light, state.mood, state.expression, state.behavior, quip, state.familiarity)
        )
    return timeline
```

  Also update the `print` line in `main()` to append `f"  fam={t.familiarity:0.1f}"`.

- [ ] **Step 4: Run** `.venv/bin/python -m pytest tests/test_simulator.py -v` — expect PASS.

- [ ] **Step 5: Watch** `.venv/bin/python sim/simulator.py` — familiarity rises across the day.

- [ ] **Step 6: Full suite + coverage** `.venv/bin/python -m pytest --cov` — expect PASS, pure layer ≥80%.

- [ ] **Step 7: Lint/format** `.venv/bin/ruff check sim/simulator.py tests/test_simulator.py && .venv/bin/black sim/simulator.py tests/test_simulator.py`

- [ ] **Step 8: Commit**
```bash
git add sim/simulator.py tests/test_simulator.py
git commit -m "feat: simulator tracks familiarity growth across the day"
```

---

## Task 10: `slime/sound.py` — piezo adapter (DEVICE)

**Files:** Create `slime/sound.py`

- [ ] **Step 1: Implement `slime/sound.py`:**

```python
"""Hardware adapter: play a tone motif on the MagTag piezo. Device-only."""
import time

import board
import digitalio
import pwmio


class Sound:
    def __init__(self):
        self._enable = digitalio.DigitalInOut(board.SPEAKER_ENABLE)
        self._enable.direction = digitalio.Direction.OUTPUT
        self._enable.value = True

    def play(self, motif):
        """Play a sequence of (freq_hz, duration_ms) tones. No-op on None/empty."""
        if not motif:
            return
        for freq, ms in motif:
            pwm = pwmio.PWMOut(board.SPEAKER, variable_frequency=True)
            pwm.frequency = int(freq)
            pwm.duty_cycle = 2**14  # ~25% duty: gentle, not loud
            time.sleep(ms / 1000.0)
            pwm.deinit()

    def silence(self):
        self._enable.value = False
```

- [ ] **Step 2: Verify on device** (after deploy in Task 13, or standalone). In the REPL:
```python
from slime.sound import Sound
from slime.motifs import pick_motif
Sound().play(pick_motif("greeting"))
```
Expected: a short two-note chirp from the piezo.

- [ ] **Step 3: Lint/format** `.venv/bin/ruff check slime/sound.py && .venv/bin/black slime/sound.py`

- [ ] **Step 4: Commit**
```bash
git add slime/sound.py
git commit -m "feat: add piezo sound adapter"
```

---

## Task 11: `slime/display.py` — frame + dream rendering (DEVICE)

**Files:** Modify `slime/display.py`

- [ ] **Step 1: Modify `slime/display.py`.** Replace the `render` method with `render_frame` +
  a delegating `render`, and add `render_dream`:

```python
    def render(self, expression, quip_text=""):
        """Render by expression name (maps to a frame). Kept for callers using expressions."""
        self.render_frame(expression_to_pose(expression), quip_text)

    def render_frame(self, frame_index, quip_text=""):
        """Set the sprite frame + quip and refresh the panel (blocking, slow)."""
        self._tile[0] = frame_index
        self._quip.text = quip_text or ""
        self._display.root_group = self._root
        while self._display.time_to_refresh > 0:
            time.sleep(0.05)
        self._display.refresh()

    def render_dream(self, dream_text, artifact_name=""):
        """Full-screen dream: the dream line, plus any artifact found, then a slow refresh."""
        group = displayio.Group()
        bg = displayio.Bitmap(self._display.width, self._display.height, 1)
        palette = displayio.Palette(1)
        palette[0] = 0xFFFFFF
        group.append(displayio.TileGrid(bg, pixel_shader=palette))

        dream = label.Label(terminalio.FONT, text=dream_text, color=0x000000, scale=1)
        dream.anchor_point = (0.5, 0.5)
        dream.anchored_position = (self._display.width // 2, self._display.height // 2 - 14)
        group.append(dream)

        if artifact_name:
            found = label.Label(
                terminalio.FONT, text="found: " + artifact_name, color=0x000000, scale=1
            )
            found.anchor_point = (0.5, 0.5)
            found.anchored_position = (self._display.width // 2, self._display.height // 2 + 14)
            group.append(found)

        self._display.root_group = group
        while self._display.time_to_refresh > 0:
            time.sleep(0.05)
        self._display.refresh()
```

  (`expression_to_pose`, `displayio`, `terminalio`, and `label` are already imported in this file.)

- [ ] **Step 2: Verify on device** (after deploy in Task 13). In the REPL:
```python
from slime.display import Display
d = Display()
d.render_dream("I crossed the Silver Pond.", "Moon Pebble")
```
Expected: a white panel showing the dream line and "found: Moon Pebble".

- [ ] **Step 3: Lint/format** `.venv/bin/ruff check slime/display.py && .venv/bin/black slime/display.py`

- [ ] **Step 4: Commit**
```bash
git add slime/display.py
git commit -m "feat: add frame and dream rendering to the display adapter"
```

---

## Task 12: Integrate everything in `code.py` (DEVICE)

**Files:** Modify `code.py`

- [ ] **Step 1: Replace `code.py` in full** with the integrated version below.

```python
"""Slime Pet — Local Soul entry point. Runs on the MagTag under CircuitPython."""
import time

from slime import dreams, friendship, persistence, power
from slime.forms import choose_render
from slime.interactions import detect, new_detector
from slime.mood import Inputs, step
from slime.motifs import pick_motif
from slime.quips import pick
from slime.state import evolve
from slime.visuals import CONTINUOUS, choose_run_mode, should_refresh

# Refresh / timing constants.
_MIN_REFRESH = 180.0
_SCHEDULED = 21600.0
_NAP_SECONDS = 1800.0
_TICK = 0.05
_SLEEPY_FRAME = 85.0  # sleepiness at/above which the slime counts as "sleeping" (loaf)


def _new_adapter(factory):
    """Construct a hardware adapter, returning None on failure (never kill the creature)."""
    try:
        return factory()
    except Exception:
        return None


def _gather(sensors, detector, last_event_time, now):
    """Read senses into Inputs; return (inputs, events, detector, last_event_time, gap)."""
    if sensors is None:
        return (
            Inputs(light=0.5, battery=1.0, on_usb=True, seconds_since_interaction=now - last_event_time, events=()),
            (),
            detector,
            last_event_time,
            now - last_event_time,
        )
    reading = sensors.reading()
    events, detector = detect(detector, reading)
    gap = now - last_event_time
    if events:
        last_event_time = now
    inputs = Inputs(
        light=sensors.light(),
        battery=sensors.battery(),
        on_usb=sensors.on_usb(),
        seconds_since_interaction=gap,
        events=events,
    )
    return inputs, events, detector, last_event_time, gap


def _render_frame(display, state):
    """Render the current form + an expression-appropriate quip. Returns updated state."""
    if not display:
        return state
    sleeping = state.mood.sleepiness >= _SLEEPY_FRAME
    frame = choose_render(state.mood, friendship.tier(state.familiarity), sleeping)
    tag = "bonded" if friendship.tier(state.familiarity) >= 3 else state.expression
    quip = pick(tag) or pick(state.expression)
    try:
        display.render_frame(frame, quip or "")
        state = evolve(state, last_seen=time.monotonic())
    except Exception:
        pass
    return state


def _dream_on_wake(display, sound, state):
    """Generate and show a dream + maybe an artifact. Returns updated state."""
    fam_tier = friendship.tier(state.familiarity)
    line, artifact_id = dreams.generate(fam_tier, state.artifacts, _choice)
    artifact_name = ""
    artifacts = state.artifacts
    if artifact_id is not None and not dreams.has_artifact(artifacts, artifact_id):
        artifacts = dreams.add_artifact(artifacts, artifact_id)
        artifact_name = dreams.artifact_name(artifact_id)
    if sound:
        sound.play(pick_motif("dream"))
    if display:
        try:
            display.render_dream(line, artifact_name)
        except Exception:
            pass
    return evolve(state, artifacts=artifacts, last_seen=time.monotonic())


def _choice(seq):
    """Pick a random element (CircuitPython has random.choice)."""
    import random

    return random.choice(seq)


def main():
    from slime.display import Display
    from slime.pixels import Pixels
    from slime.sensors import Sensors
    from slime.sound import Sound

    now = time.monotonic()
    state = persistence.load(now)
    sensors = _new_adapter(Sensors)
    pixels = _new_adapter(Pixels)
    display = _new_adapter(Display)
    sound = _new_adapter(Sound)
    detector = new_detector()
    last_event_time = time.monotonic()

    woke_deep = power.woke_from_deep_sleep()

    # If we woke from a long deep-sleep nap, that was a "night" — dream first.
    if woke_deep and dreams.should_dream(True, _NAP_SECONDS):
        state = _dream_on_wake(display, sound, state)
    elif not woke_deep:
        # Cold boot/reload: greet the owner with a wake chirp.
        if sound:
            sound.play(pick_motif("wake"))

    inputs, events, detector, last_event_time, gap = _gather(sensors, detector, last_event_time, now)
    state = step(state, inputs, 1.0)
    if "double_tap" in events:
        state = evolve(state, total_boops=state.total_boops + 1)
    fam, visits = friendship.update(state.familiarity, state.visit_count, events, gap)
    state = evolve(state, familiarity=fam, visit_count=visits)

    # Cold boot always paints; a deep-sleep wake (post-dream) repaints the creature too.
    state = _render_frame(display, state)
    persistence.save(state)

    if choose_run_mode(inputs.on_usb, inputs.battery) == CONTINUOUS:
        t0 = time.monotonic()
        while True:
            now = time.monotonic()
            inputs, events, detector, last_event_time, gap = _gather(
                sensors, detector, last_event_time, now
            )
            if events:
                prev = state.expression
                state = step(state, inputs, 1.0)
                if "double_tap" in events:
                    state = evolve(state, total_boops=state.total_boops + 1)
                fam, visits = friendship.update(state.familiarity, state.visit_count, events, gap)
                state = evolve(state, familiarity=fam, visit_count=visits)
                ftier = friendship.tier(state.familiarity)
                if sound:
                    if state.behavior == "dizzy":
                        sound.play(pick_motif("dizzy"))
                    elif state.behavior == "greeting":
                        sound.play(pick_motif("greeting", ftier))
                if state.behavior == "dizzy" and pixels:
                    pixels.flash((120, 0, 0))
                    time.sleep(0.4)
                if should_refresh(
                    time.monotonic(),
                    state.last_seen,
                    pose_changed=(state.expression != prev),
                    significant_event=("double_tap" in events),
                    min_interval=_MIN_REFRESH,
                    scheduled_interval=_SCHEDULED,
                ):
                    state = _render_frame(display, state)
                persistence.save(state)
            if pixels:
                rate = 0.12 + (state.mood.energy / 100.0) * 0.35
                pixels.breathe(state.mood, time.monotonic() - t0, rate=rate)
            time.sleep(_TICK)
    else:
        t0 = time.monotonic()
        while time.monotonic() - t0 < 4.0:
            if pixels:
                pixels.breathe(state.mood, time.monotonic() - t0, rate=0.2)
            time.sleep(_TICK)
        if pixels:
            pixels.off()
        if sound:
            sound.play(pick_motif("sleepy"))
        power.nap(_NAP_SECONDS)


# CircuitPython runs code.py as __main__; the guard keeps host imports from running main().
if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Syntax check** `.venv/bin/python -m py_compile code.py` — expect no output.

- [ ] **Step 3: Confirm host suite unaffected** `.venv/bin/python -m pytest -q` — expect all pass
  (the `_replace` guard test scans `code.py`; it must find none).

- [ ] **Step 4: Lint/format** `.venv/bin/ruff check code.py && .venv/bin/black --check code.py`

- [ ] **Step 5: Commit**
```bash
git add code.py
git commit -m "feat: integrate forms, friendship, sound, and dream-on-wake into code.py"
```

---

## Task 13: On-device bring-up & Phase 1 verification

**Files:** none (deploy + verify only)

- [ ] **Step 1: Deploy to the board** (mounted at `/Volumes/CIRCUITPY`):
```bash
cp slime/*.py /Volumes/CIRCUITPY/slime/
cp assets/slime.bmp /Volumes/CIRCUITPY/assets/
cp code.py /Volumes/CIRCUITPY/
rm -rf /Volumes/CIRCUITPY/slime/__pycache__
sync
```

- [ ] **Step 2: Confirm a clean run** over serial (`/dev/cu.usbmodem*`, 115200): soft-reboot (Ctrl-D)
  and confirm `code.py output:` with no traceback. If "Power dipped" safe mode appears, use a powered
  USB port / better cable.

- [ ] **Step 3: Verify Phase 1 success criteria:**
  1. [ ] Forms appear by mood + familiarity (loaf when very sleepy; puddle at low energy; wisp when
     long-quiet; explorer once unlocked + curious/energetic; crowned once bonded + happy).
  2. [ ] Double-tapping repeatedly across separated sessions raises familiarity — confirm via REPL:
     `import microcontroller; from slime.persistence import unpack, BLOB_SIZE; s=unpack(bytes(microcontroller.nvm[0:BLOB_SIZE])); print(s.familiarity, s.visit_count, s.artifacts)`.
  3. [ ] Motifs play on greeting (double-tap), dizzy (flip/shake), and wake.
  4. [ ] Force a dream render: REPL `from slime.display import Display; from slime import dreams; d=Display(); line,art=dreams.generate(2,0,__import__('random').choice); d.render_dream(line, dreams.artifact_name(art) if art is not None else "")`.
  5. [ ] **Migration:** confirm a pet that had a Phase-0 (v1) NVM blob keeps its boops after this
     upgrade (if the board already ran Phase 0, `total_boops` should be non-zero and unchanged).
  6. [ ] Host suite green: `.venv/bin/python -m pytest --cov` ≥80% pure layer.

- [ ] **Step 4: Commit the verification milestone**
```bash
git commit --allow-empty -m "chore: Phase 1a verified on device"
```

---

## Notes for the implementer

- **Pure vs adapter:** never `import board`/hardware in `friendship`, `forms`, `motifs`, `dreams`,
  `quips`, `visuals`, `state`, `persistence`, or `sim`. The guard test enforces no `._replace(`.
- **NVM migration is the delicate part:** a real device may hold a v1 blob; `unpack` must keep that
  progress. Test it (Task 7) before trusting it.
- **Sound stays gentle:** ~25% duty cycle, short motifs, only on key moments — "alive without being
  loud."
- **Dreams aren't persisted as text** — only the artifacts bitmask is. The dream line is generated
  and shown at wake, then forgotten, keeping state NVM-sized.
```
