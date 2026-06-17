# Local Soul MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a living, breathing, offline slime pet on an Adafruit MagTag — mood-driven pixel-art on E-Ink, breathing NeoPixels, accelerometer interactions, and persistent memory — using only the MagTag's built-in hardware.

**Architecture:** A clean split between **pure logic** (no hardware imports; runs and tests under desktop CPython) and **thin hardware adapters** (device-only). Pure modules carry the personality (mood, interactions, quips, visuals, state, persistence packing). Adapters (`sensors`, `pixels`, `display`, `power`) wrap CircuitPython hardware libs and import the pure logic. `code.py` orchestrates one sense→think→show→persist→sleep cycle.

**Tech Stack:** CircuitPython 9.x on ESP32-S2; `displayio`, `neopixel`, `adafruit_lis3dh`, `adafruit_display_text`, `alarm`, `microcontroller`, `supervisor`. Host testing: Python 3 + `pytest` + `pytest-cov`. Asset generation: Pillow.

---

## File Structure

```
slime-pet/
  code.py                  # device entry: one cycle, then loop (USB) or deep-sleep (battery)
  slime/
    __init__.py
    state.py               # PURE: Mood + State namedtuples, defaults, clamping
    mood.py                # PURE: Inputs, step(), derive_expression(), derive_behavior()
    interactions.py        # PURE: accelerometer → gesture events (tap/double/shake/pickup/setdown/flip)
    quips.py               # PURE: quip pools + pick()
    visuals.py             # PURE: mood→rgb, breathing curve, pose mapping, refresh policy, run-mode
    persistence.py         # PURE pack()/unpack() + hardware save()/load() (NVM)
    sensors.py             # ADAPTER: battery, USB sense, light, LIS3DH
    pixels.py              # ADAPTER: NeoPixel breathing
    display.py             # ADAPTER: displayio pose bitmap + quip label
    power.py               # ADAPTER: deep-sleep via `alarm`
  assets/
    make_assets.py         # host script: generates slime.bmp sprite sheet (placeholder poses)
    slime.bmp              # generated indexed sprite sheet
  sim/
    simulator.py           # host: run the mood loop over scripted inputs ("day in the life")
  tests/
    test_state.py
    test_mood.py
    test_interactions.py
    test_quips.py
    test_visuals.py
    test_persistence.py
    test_simulator.py
  pyproject.toml
  README.md
```

Pure modules tested on host: `state`, `mood`, `interactions`, `quips`, `visuals`, `persistence` (pack/unpack), plus `sim/simulator`. Adapters and `code.py` are verified on the device.

---

## Task 1: Project scaffolding & test harness

**Files:**
- Create: `pyproject.toml`
- Create: `slime/__init__.py`
- Create: `tests/__init__.py`
- Create: `README.md`

- [ ] **Step 1: Install host test tooling**

Run:
```bash
pip3 install pytest pytest-cov pillow
```
Expected: pytest and pillow install successfully.

- [ ] **Step 2: Create `pyproject.toml`**

```toml
[tool.pytest.ini_options]
pythonpath = ["."]
testpaths = ["tests"]
addopts = "-q"

[tool.coverage.run]
source = ["slime", "sim"]
omit = ["slime/sensors.py", "slime/pixels.py", "slime/display.py", "slime/power.py", "code.py"]
```

(The omit list excludes hardware adapters from coverage — they are verified on-device, not in pytest.)

- [ ] **Step 3: Create empty package markers**

`slime/__init__.py`:
```python
```

`tests/__init__.py`:
```python
```

- [ ] **Step 4: Create `README.md`**

```markdown
# Slime Pet — Local Soul (Phase 0)

A calm, offline ambient companion for the Adafruit MagTag. See
`docs/superpowers/specs/2026-06-17-local-soul-mvp-design.md` for the design.

## Develop

```bash
pip3 install pytest pytest-cov pillow
pytest                 # run host-side unit tests
python3 sim/simulator.py   # watch a "day in the life"
python3 assets/make_assets.py   # regenerate the sprite sheet
```

## Deploy to the MagTag

1. Flash CircuitPython 9.x (MagTag UF2) — double-tap reset → drag the .uf2 to the bootloader drive.
2. `circup install adafruit_lis3dh neopixel adafruit_display_text`
3. Copy `code.py`, the `slime/` package, and `assets/slime.bmp` to the `CIRCUITPY` drive.
```

- [ ] **Step 5: Verify pytest runs (no tests yet)**

Run: `pytest`
Expected: "no tests ran" (exit 5) — confirms discovery works.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml slime/__init__.py tests/__init__.py README.md
git commit -m "chore: scaffold project and host test harness"
```

---

## Task 2: `slime/state.py` — types, defaults, clamping (PURE)

**Files:**
- Create: `slime/state.py`
- Test: `tests/test_state.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_state.py`:
```python
from slime.state import Mood, State, clamp, clamp_mood, default_state, MOOD_FIELDS


def test_mood_has_five_named_drives():
    assert MOOD_FIELDS == ("energy", "comfort", "curiosity", "sleepiness", "affection")
    m = Mood(1, 2, 3, 4, 5)
    assert m.energy == 1 and m.affection == 5


def test_clamp_bounds_values_to_0_100():
    assert clamp(-10) == 0.0
    assert clamp(150) == 100.0
    assert clamp(42) == 42.0


def test_clamp_mood_clamps_every_drive():
    m = clamp_mood(Mood(-5, 200, 50, 50, 50))
    assert m.energy == 0.0
    assert m.comfort == 100.0
    assert m.curiosity == 50.0


def test_default_state_is_reasonable_and_immutable():
    s = default_state(now=100.0)
    assert isinstance(s.mood, Mood)
    assert s.total_boops == 0
    assert s.first_boot == 100.0
    assert s.last_seen == 100.0
    assert s.expression == "content"
    assert s.behavior == "idle"
    # namedtuple is immutable; _replace returns a new copy
    s2 = s._replace(total_boops=1)
    assert s.total_boops == 0 and s2.total_boops == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_state.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'slime.state'`.

- [ ] **Step 3: Implement `slime/state.py`**

```python
"""Pure value types for the slime's soul. No hardware imports."""
from collections import namedtuple

MOOD_FIELDS = ("energy", "comfort", "curiosity", "sleepiness", "affection")
Mood = namedtuple("Mood", MOOD_FIELDS)

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
    ),
)


def clamp(value, lo=0.0, hi=100.0):
    """Clamp a drive value into [lo, hi] as a float."""
    return float(min(hi, max(lo, value)))


def clamp_mood(mood):
    """Return a new Mood with every drive clamped to [0, 100]."""
    return Mood(*(clamp(v) for v in mood))


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
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_state.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add slime/state.py tests/test_state.py
git commit -m "feat: add pure state types, clamping, and defaults"
```

---

## Task 3: `slime/mood.py` — the mood engine (PURE)

**Files:**
- Create: `slime/mood.py`
- Test: `tests/test_mood.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_mood.py`:
```python
from slime.state import Mood, default_state
from slime.mood import Inputs, step, derive_expression, derive_behavior


def idle_inputs(**kw):
    base = dict(light=0.5, battery=0.8, on_usb=True, seconds_since_interaction=10.0, events=())
    base.update(kw)
    return Inputs(**base)


def test_darkness_increases_sleepiness_over_time():
    s = default_state(now=0.0)
    s2 = step(s, idle_inputs(light=0.02), dt=60.0)
    assert s2.mood.sleepiness > s.mood.sleepiness


def test_bright_light_wakes_the_slime():
    s = default_state(now=0.0)._replace(mood=Mood(50, 70, 50, 80, 40))
    s2 = step(s, idle_inputs(light=0.95), dt=60.0)
    assert s2.mood.sleepiness < 80


def test_low_battery_lowers_energy():
    s = default_state(now=0.0)
    s2 = step(s, idle_inputs(battery=0.05), dt=60.0)
    assert s2.mood.energy < s.mood.energy


def test_double_tap_event_raises_affection_and_curiosity():
    s = default_state(now=0.0)
    s2 = step(s, idle_inputs(events=("double_tap",)), dt=1.0)
    assert s2.mood.affection > s.mood.affection
    assert s2.mood.curiosity > s.mood.curiosity


def test_long_absence_makes_it_contemplative_not_sad():
    s = default_state(now=0.0)
    s2 = step(s, idle_inputs(seconds_since_interaction=86400.0), dt=60.0)
    # comfort drifts toward a calm baseline, never below 0
    assert 0.0 <= s2.mood.comfort <= 100.0
    assert s2.expression in ("contemplative", "sleepy", "content")


def test_step_returns_clamped_new_state_without_mutating_input():
    s = default_state(now=0.0)
    s2 = step(s, idle_inputs(events=("double_tap", "double_tap", "double_tap")), dt=1.0)
    for v in s2.mood:
        assert 0.0 <= v <= 100.0
    assert s.mood.affection == 40.0  # original unchanged


def test_derive_expression_maps_dominant_drive():
    assert derive_expression(Mood(50, 50, 50, 95, 30)) == "sleepy"
    assert derive_expression(Mood(50, 50, 95, 20, 30)) == "curious"
    assert derive_expression(Mood(90, 60, 50, 10, 85)) == "happy"
    assert derive_expression(Mood(60, 80, 40, 20, 40)) == "content"


def test_derive_behavior_prioritizes_events():
    assert derive_behavior(Mood(60, 70, 50, 30, 40), ("flip",)) == "dizzy"
    assert derive_behavior(Mood(60, 70, 50, 30, 40), ("double_tap",)) == "greeting"
    assert derive_behavior(Mood(60, 70, 50, 30, 40), ()) == "idle"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_mood.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'slime.mood'`.

- [ ] **Step 3: Implement `slime/mood.py`**

```python
"""Pure mood engine. Inputs -> new State. No hardware imports."""
from collections import namedtuple
from slime.state import Mood, clamp_mood

Inputs = namedtuple(
    "Inputs",
    (
        "light",                      # 0.0 (dark) .. 1.0 (bright)
        "battery",                    # 0.0 .. 1.0
        "on_usb",                     # bool
        "seconds_since_interaction",  # float
        "events",                     # tuple[str, ...]
    ),
)

# Tuning constants (per-minute influence rates, scaled by dt).
_DAY_LIGHT = 0.35          # light level above which it's "daytime"
_SLEEP_GAIN = 8.0          # sleepiness change per minute in full dark/light
_ENERGY_DRAIN = 6.0        # energy lost per minute at empty battery
_COMFORT_BASELINE = 65.0   # comfort drifts toward this when alone
_DRIFT = 3.0               # generic drift per minute toward baseline
_LONELY_AFTER = 3600.0     # seconds alone before curiosity starts to fade

_EVENT_DELTAS = {
    "double_tap": {"affection": 12.0, "curiosity": 8.0, "sleepiness": -6.0},
    "tap": {"affection": 3.0, "curiosity": 3.0},
    "pickup": {"curiosity": 14.0, "sleepiness": -10.0, "energy": 4.0},
    "setdown": {"comfort": 6.0, "curiosity": -4.0},
    "shake": {"comfort": -8.0, "curiosity": 6.0},
    "flip": {"comfort": -10.0, "curiosity": 4.0},
}


def _apply_events(values, events):
    for ev in events:
        for drive, delta in _EVENT_DELTAS.get(ev, {}).items():
            values[drive] += delta
    return values


def step(state, inputs, dt):
    """Advance the mood by `dt` seconds given `inputs`. Returns a new State."""
    minutes = dt / 60.0
    m = state.mood
    values = {
        "energy": m.energy,
        "comfort": m.comfort,
        "curiosity": m.curiosity,
        "sleepiness": m.sleepiness,
        "affection": m.affection,
    }

    # Light drives the sleep cycle.
    if inputs.light < _DAY_LIGHT:
        values["sleepiness"] += _SLEEP_GAIN * minutes
    else:
        values["sleepiness"] -= _SLEEP_GAIN * minutes

    # Battery drives energy; low battery saps it, full battery slowly restores.
    values["energy"] += (inputs.battery - 0.5) * 2.0 * _ENERGY_DRAIN * minutes

    # Gentle drift of comfort toward a calm baseline (never punished into sadness).
    if state.mood.comfort < _COMFORT_BASELINE:
        values["comfort"] += _DRIFT * minutes
    else:
        values["comfort"] -= _DRIFT * minutes * 0.5

    # Long solitude makes it contemplative: curiosity quietly fades.
    if inputs.seconds_since_interaction > _LONELY_AFTER:
        values["curiosity"] -= _DRIFT * minutes

    # Interaction events.
    values = _apply_events(values, inputs.events)

    mood = clamp_mood(
        Mood(
            energy=values["energy"],
            comfort=values["comfort"],
            curiosity=values["curiosity"],
            sleepiness=values["sleepiness"],
            affection=values["affection"],
        )
    )
    return state._replace(
        mood=mood,
        expression=derive_expression(mood),
        behavior=derive_behavior(mood, inputs.events),
    )


def derive_expression(mood):
    """Pick the visible expression from the dominant drive."""
    if mood.sleepiness >= 75.0:
        return "sleepy"
    if mood.affection >= 75.0 and mood.energy >= 50.0:
        return "happy"
    if mood.curiosity >= 70.0:
        return "curious"
    if mood.curiosity <= 30.0 and mood.energy <= 40.0:
        return "contemplative"
    return "content"


def derive_behavior(mood, events):
    """Events take priority over steady-state behavior."""
    if "flip" in events or "shake" in events:
        return "dizzy"
    if "double_tap" in events:
        return "greeting"
    if "pickup" in events:
        return "attentive"
    if "setdown" in events:
        return "settling"
    return "idle"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_mood.py -v`
Expected: PASS (8 passed).

- [ ] **Step 5: Commit**

```bash
git add slime/mood.py tests/test_mood.py
git commit -m "feat: add pure mood engine with five drives and event influences"
```

---

## Task 4: `slime/interactions.py` — gesture detection (PURE)

**Files:**
- Create: `slime/interactions.py`
- Test: `tests/test_interactions.py`

The LIS3DH reports acceleration in m/s² and hardware tap flags. This module turns raw
readings (plus the previous reading via a `Detector`) into gesture event strings.

- [ ] **Step 1: Write the failing tests**

`tests/test_interactions.py`:
```python
from slime.interactions import (
    AccelReading, Detector, new_detector, detect,
    TAP, DOUBLE_TAP, SHAKE, PICKUP, SETDOWN, FLIP,
)

# Gravity ~9.8 m/s^2. "At rest, upright" => z ~ +9.8, small x/y.
REST = AccelReading(x=0.0, y=0.0, z=9.8, tapped=False, double_tapped=False)


def test_double_tap_flag_yields_double_tap_event():
    events, _ = detect(new_detector(), REST._replace(double_tapped=True))
    assert DOUBLE_TAP in events


def test_single_tap_flag_yields_tap_event():
    events, _ = detect(new_detector(), REST._replace(tapped=True))
    assert TAP in events


def test_flip_detected_when_z_inverts():
    flipped = AccelReading(x=0.0, y=0.0, z=-9.8, tapped=False, double_tapped=False)
    events, _ = detect(new_detector(), flipped)
    assert FLIP in events


def test_shake_detected_on_high_magnitude():
    shaken = AccelReading(x=22.0, y=18.0, z=9.8, tapped=False, double_tapped=False)
    events, _ = detect(new_detector(), shaken)
    assert SHAKE in events


def test_pickup_then_setdown_transitions():
    d = new_detector()
    # establish "still at rest" baseline
    _, d = detect(d, REST)
    _, d = detect(d, REST)
    # motion onset = pickup
    moving = AccelReading(x=3.0, y=3.0, z=11.0, tapped=False, double_tapped=False)
    events, d = detect(d, moving)
    assert PICKUP in events
    # settle back to rest = setdown
    _, d = detect(d, REST)
    events, d = detect(d, REST)
    assert SETDOWN in events


def test_rest_produces_no_events():
    d = new_detector()
    _, d = detect(d, REST)
    events, _ = detect(d, REST)
    assert events == ()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_interactions.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'slime.interactions'`.

- [ ] **Step 3: Implement `slime/interactions.py`**

```python
"""Pure gesture detection from accelerometer readings. No hardware imports."""
import math
from collections import namedtuple

TAP = "tap"
DOUBLE_TAP = "double_tap"
SHAKE = "shake"
PICKUP = "pickup"
SETDOWN = "setdown"
FLIP = "flip"

AccelReading = namedtuple("AccelReading", ("x", "y", "z", "tapped", "double_tapped"))

# Detector remembers whether the slime was moving and how long it has been still.
Detector = namedtuple("Detector", ("was_moving", "still_count"))

_GRAVITY = 9.8
_SHAKE_MAGNITUDE = 16.0   # m/s^2 total; brisk shake clears this
_MOVE_DELTA = 2.5         # deviation from 1g that counts as "moving"
_FLIP_Z = -6.0            # z this negative means upside-down
_STILL_FOR_SETDOWN = 1    # consecutive still reads after motion => setdown


def new_detector():
    return Detector(was_moving=False, still_count=0)


def _magnitude(r):
    return math.sqrt(r.x * r.x + r.y * r.y + r.z * r.z)


def detect(detector, reading):
    """Return (events_tuple, new_detector) for a single reading."""
    events = []

    if reading.double_tapped:
        events.append(DOUBLE_TAP)
    elif reading.tapped:
        events.append(TAP)

    if reading.z <= _FLIP_Z:
        events.append(FLIP)

    magnitude = _magnitude(reading)
    moving = abs(magnitude - _GRAVITY) > _MOVE_DELTA

    if magnitude >= _SHAKE_MAGNITUDE:
        events.append(SHAKE)

    if moving and not detector.was_moving:
        events.append(PICKUP)

    if not moving and detector.was_moving:
        # just stopped moving -> begin settling
        new = Detector(was_moving=False, still_count=1)
        return tuple(events), new

    if not moving and detector.still_count == _STILL_FOR_SETDOWN:
        events.append(SETDOWN)
        return tuple(events), Detector(was_moving=False, still_count=detector.still_count + 1)

    next_still = 0 if moving else detector.still_count + 1
    return tuple(events), Detector(was_moving=moving, still_count=next_still)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_interactions.py -v`
Expected: PASS (6 passed).

- [ ] **Step 5: Commit**

```bash
git add slime/interactions.py tests/test_interactions.py
git commit -m "feat: add pure accelerometer gesture detection"
```

---

## Task 5: `slime/quips.py` — the creature's voice (PURE)

**Files:**
- Create: `slime/quips.py`
- Test: `tests/test_quips.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_quips.py`:
```python
from slime.quips import pick, QUIPS


def test_every_expression_and_behavior_tag_has_quips():
    for tag in ("content", "sleepy", "curious", "happy", "contemplative", "greeting"):
        assert tag in QUIPS
        assert len(QUIPS[tag]) >= 2


def test_pick_returns_a_string_from_the_tag_pool():
    chosen = pick("sleepy", choice=lambda seq: seq[0])
    assert chosen == QUIPS["sleepy"][0]


def test_pick_unknown_tag_returns_none():
    assert pick("nonsense", choice=lambda seq: seq[0]) is None


def test_pick_is_deterministic_with_injected_choice():
    chosen = pick("greeting", choice=lambda seq: seq[-1])
    assert chosen == QUIPS["greeting"][-1]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_quips.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'slime.quips'`.

- [ ] **Step 3: Implement `slime/quips.py`**

```python
"""Pure quip selection. The slime's occasional one-line voice. No hardware imports."""
try:
    from random import choice as _default_choice
except ImportError:  # pragma: no cover
    def _default_choice(seq):
        return seq[0]

QUIPS = {
    "content": (
        "warm light today",
        "the desk is calm",
        "i am here",
    ),
    "sleepy": (
        "soft and slow",
        "almost dreaming",
        "the dark is gentle",
    ),
    "curious": (
        "what was that?",
        "something moved",
        "i wonder",
    ),
    "happy": (
        "you came back",
        "good to see you",
        "a fine moment",
    ),
    "contemplative": (
        "the silver pond is quiet",
        "i remember the seventh moon",
        "time passes softly",
    ),
    "greeting": (
        "oh! hello",
        "there you are",
        "hi hi",
    ),
}


def pick(tag, choice=_default_choice):
    """Return one quip for `tag`, or None if the tag is unknown."""
    pool = QUIPS.get(tag)
    if not pool:
        return None
    return choice(pool)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_quips.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add slime/quips.py tests/test_quips.py
git commit -m "feat: add pure quip pools and selection"
```

---

## Task 6: `slime/visuals.py` — presentation & power decisions (PURE)

**Files:**
- Create: `slime/visuals.py`
- Test: `tests/test_visuals.py`

All *decisions* about color, breathing, which pose to show, when to refresh, and which run
mode to use are pure logic here. The adapters just execute them.

- [ ] **Step 1: Write the failing tests**

`tests/test_visuals.py`:
```python
from slime.state import Mood
from slime.visuals import (
    expression_to_pose, mood_to_rgb, breath_brightness,
    should_refresh, choose_run_mode, POSE_INDEX,
)


def test_expression_to_pose_maps_known_expressions():
    assert expression_to_pose("content") == POSE_INDEX["content"]
    assert expression_to_pose("sleepy") == POSE_INDEX["sleepy"]


def test_expression_to_pose_unknown_falls_back_to_resting():
    assert expression_to_pose("???") == POSE_INDEX["resting"]


def test_mood_to_rgb_returns_byte_triple():
    r, g, b = mood_to_rgb(Mood(60, 70, 50, 30, 40))
    for c in (r, g, b):
        assert 0 <= c <= 255


def test_sleepy_mood_is_dim_blue_ish():
    r, g, b = mood_to_rgb(Mood(20, 60, 30, 95, 30))
    assert b >= r and b >= g


def test_breath_brightness_oscillates_within_bounds():
    vals = [breath_brightness(t, rate=0.25, lo=0.05, hi=0.5) for t in range(0, 40)]
    assert min(vals) >= 0.05 - 1e-9
    assert max(vals) <= 0.5 + 1e-9
    assert max(vals) - min(vals) > 0.1  # it actually moves


def test_should_refresh_on_significant_event_even_if_recent():
    assert should_refresh(now=10.0, last_refresh=9.0, pose_changed=False,
                           significant_event=True, min_interval=180.0,
                           scheduled_interval=21600.0) is True


def test_should_refresh_blocks_rapid_pose_flicker():
    assert should_refresh(now=10.0, last_refresh=9.0, pose_changed=True,
                          significant_event=False, min_interval=180.0,
                          scheduled_interval=21600.0) is False


def test_should_refresh_allows_pose_change_after_min_interval():
    assert should_refresh(now=200.0, last_refresh=10.0, pose_changed=True,
                          significant_event=False, min_interval=180.0,
                          scheduled_interval=21600.0) is True


def test_should_refresh_scheduled_update_when_stale():
    assert should_refresh(now=30000.0, last_refresh=0.0, pose_changed=False,
                          significant_event=False, min_interval=180.0,
                          scheduled_interval=21600.0) is True


def test_choose_run_mode():
    assert choose_run_mode(on_usb=True, battery=0.9) == "continuous"
    assert choose_run_mode(on_usb=False, battery=0.9) == "wake_cycle"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_visuals.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'slime.visuals'`.

- [ ] **Step 3: Implement `slime/visuals.py`**

```python
"""Pure presentation & power-mode decisions. No hardware imports."""
import math
from slime.mood import derive_expression

# Sprite-sheet frame index per expression/behavior. Authored to match assets/slime.bmp.
POSE_INDEX = {
    "content": 0,
    "sleepy": 1,
    "curious": 2,
    "happy": 3,
    "contemplative": 4,
    "dizzy": 5,
    "resting": 6,
}

# Mood-tinted NeoPixel colors (R, G, B), 0..255.
_EXPRESSION_RGB = {
    "content": (0, 110, 110),       # calm teal
    "sleepy": (10, 20, 90),         # dim blue
    "curious": (150, 90, 0),        # amber
    "happy": (140, 40, 90),         # rose
    "contemplative": (40, 30, 90),  # dusk violet
    "resting": (30, 30, 30),        # near-dark
}

CONTINUOUS = "continuous"
WAKE_CYCLE = "wake_cycle"


def expression_to_pose(expression):
    """Map an expression name to a sprite-sheet frame index."""
    return POSE_INDEX.get(expression, POSE_INDEX["resting"])


def mood_to_rgb(mood):
    """Pick a NeoPixel color triple from the dominant mood (shares mood.derive_expression)."""
    return _EXPRESSION_RGB[derive_expression(mood)]


def breath_brightness(t, rate=0.25, lo=0.05, hi=0.5):
    """Sine breathing curve in [lo, hi]. `rate` is cycles per second, `t` in seconds."""
    phase = math.sin(2.0 * math.pi * rate * t)
    return lo + (hi - lo) * (phase * 0.5 + 0.5)


def should_refresh(now, last_refresh, pose_changed, significant_event,
                   min_interval, scheduled_interval):
    """Decide whether to repaint the slow E-Ink panel."""
    age = now - last_refresh
    if significant_event:
        return True
    if pose_changed and age >= min_interval:
        return True
    if age >= scheduled_interval:
        return True
    return False


def choose_run_mode(on_usb, battery):
    """USB -> always breathing; battery -> motion-wake bursts."""
    return CONTINUOUS if on_usb else WAKE_CYCLE
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_visuals.py -v`
Expected: PASS (10 passed).

- [ ] **Step 5: Commit**

```bash
git add slime/visuals.py tests/test_visuals.py
git commit -m "feat: add pure visuals — color, breathing, pose, refresh policy, run mode"
```

---

## Task 7: `slime/persistence.py` — NVM pack/unpack + load/save

**Files:**
- Create: `slime/persistence.py`
- Test: `tests/test_persistence.py`

`pack`/`unpack` are pure (`struct` only) and tested on host. `save`/`load` import
`microcontroller` lazily (inside the functions) so the module imports cleanly on the desktop.

- [ ] **Step 1: Write the failing tests**

`tests/test_persistence.py`:
```python
from slime.state import Mood, default_state
from slime.persistence import pack, unpack, NVM_VERSION, BLOB_SIZE


def test_pack_roundtrips_state():
    s = default_state(now=123.0)._replace(
        mood=Mood(11, 22, 33, 44, 55), total_boops=7, longest_absence=900.0, last_seen=500.0
    )
    blob = pack(s)
    assert len(blob) == BLOB_SIZE
    s2 = unpack(blob)
    assert tuple(s2.mood) == (11.0, 22.0, 33.0, 44.0, 55.0)
    assert s2.total_boops == 7
    assert s2.longest_absence == 900.0
    assert s2.last_seen == 500.0
    assert s2.first_boot == 123.0


def test_unpack_recomputes_expression_and_behavior():
    s = default_state(now=0.0)._replace(mood=Mood(20, 60, 30, 95, 30))
    s2 = unpack(pack(s))
    assert s2.expression == "sleepy"
    assert s2.behavior == "idle"


def test_unpack_rejects_wrong_version():
    blob = bytearray(pack(default_state()))
    blob[0] = NVM_VERSION + 9
    try:
        unpack(bytes(blob))
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_unpack_rejects_garbage_length():
    try:
        unpack(b"\x00\x00")
        assert False, "expected ValueError"
    except ValueError:
        pass
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_persistence.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'slime.persistence'`.

- [ ] **Step 3: Implement `slime/persistence.py`**

```python
"""Persist core state to microcontroller NVM. pack/unpack are pure; save/load touch hardware."""
import struct
from slime.state import Mood, State, default_state
from slime import mood as mood_engine

NVM_VERSION = 1
# version(B) + 5 mood floats + last_seen + longest_absence + first_boot (f) + total_boops (I)
_FORMAT = "<B5ffffI"
BLOB_SIZE = struct.calcsize(_FORMAT)


def pack(state):
    """Serialize the durable parts of a State to bytes (expression/behavior are recomputed)."""
    m = state.mood
    return struct.pack(
        _FORMAT,
        NVM_VERSION,
        m.energy, m.comfort, m.curiosity, m.sleepiness, m.affection,
        state.last_seen, state.longest_absence, state.first_boot,
        state.total_boops,
    )


def unpack(blob):
    """Deserialize bytes to a State, recomputing expression/behavior. Raises ValueError on bad data."""
    if len(blob) < BLOB_SIZE:
        raise ValueError("nvm blob too short")
    fields = struct.unpack(_FORMAT, blob[:BLOB_SIZE])
    version = fields[0]
    if version != NVM_VERSION:
        raise ValueError("nvm version mismatch")
    mood = Mood(*fields[1:6])
    last_seen, longest_absence, first_boot, total_boops = fields[6:10]
    return State(
        mood=mood,
        last_seen=last_seen,
        total_boops=total_boops,
        longest_absence=longest_absence,
        first_boot=first_boot,
        expression=mood_engine.derive_expression(mood),
        behavior="idle",
    )


def save(state):
    """Write state to NVM. Device-only."""
    import microcontroller
    microcontroller.nvm[0:BLOB_SIZE] = pack(state)


def load(now=0.0):
    """Read state from NVM; return a fresh default_state on any problem. Device-only."""
    import microcontroller
    try:
        return unpack(bytes(microcontroller.nvm[0:BLOB_SIZE]))
    except Exception:
        return default_state(now)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_persistence.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add slime/persistence.py tests/test_persistence.py
git commit -m "feat: add NVM persistence with pure pack/unpack"
```

---

## Task 8: `sim/simulator.py` — a "day in the life" (PURE)

**Files:**
- Create: `sim/__init__.py`
- Create: `sim/simulator.py`
- Test: `tests/test_simulator.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_simulator.py`:
```python
from sim.simulator import run_day, Tick


def test_run_day_returns_a_timeline():
    timeline = run_day()
    assert len(timeline) > 0
    assert all(isinstance(t, Tick) for t in timeline)


def test_night_segment_makes_it_sleepy_by_morning():
    timeline = run_day()
    # Find the deepest-night tick (lowest light) and assert sleepiness rose meaningfully.
    darkest = min(timeline, key=lambda t: t.light)
    assert darkest.mood.sleepiness > 40.0


def test_interaction_tick_records_greeting_behavior():
    timeline = run_day()
    assert any(t.behavior == "greeting" for t in timeline)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_simulator.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'sim.simulator'`.

- [ ] **Step 3: Implement the simulator**

`sim/__init__.py`:
```python
```

`sim/simulator.py`:
```python
"""Run the pure mood loop over a scripted day. No hardware. Run: python3 sim/simulator.py"""
from collections import namedtuple
from slime.state import default_state
from slime.mood import Inputs, step
from slime.quips import pick

Tick = namedtuple("Tick", ("hour", "light", "mood", "expression", "behavior", "quip"))

# A scripted 24-hour arc: (hour, light 0..1, events).
_SCRIPT = [
    (0, 0.02, ()), (2, 0.01, ()), (4, 0.01, ()), (6, 0.15, ()),
    (7, 0.6, ("double_tap",)), (9, 0.8, ()), (12, 0.95, ("pickup",)),
    (14, 0.85, ()), (17, 0.7, ("tap",)), (19, 0.4, ("setdown",)),
    (21, 0.2, ()), (23, 0.05, ()),
]
_STEP_SECONDS = 3600.0


def run_day():
    """Return a list of Tick across the scripted day."""
    state = default_state(now=0.0)
    timeline = []
    last_interaction = 0.0
    for hour, light, events in _SCRIPT:
        secs_since = hour * 3600.0 - last_interaction
        if events:
            last_interaction = hour * 3600.0
        inputs = Inputs(
            light=light, battery=0.8, on_usb=True,
            seconds_since_interaction=max(0.0, secs_since), events=events,
        )
        state = step(state, inputs, dt=_STEP_SECONDS)
        quip = pick(state.behavior if state.behavior == "greeting" else state.expression,
                    choice=lambda seq: seq[0])
        timeline.append(Tick(hour, light, state.mood, state.expression, state.behavior, quip))
    return timeline


def main():
    for t in run_day():
        bar = "#" * int(t.mood.sleepiness / 5)
        print(f"{t.hour:02d}:00  light={t.light:0.2f}  {t.expression:<13} "
              f"{t.behavior:<10} sleepy|{bar:<20}|  \"{t.quip}\"")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_simulator.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Watch the day**

Run: `python3 sim/simulator.py`
Expected: A printed 24-hour timeline; sleepiness bar grows at night, a "greeting" line at 07:00.

- [ ] **Step 6: Confirm coverage of pure modules ≥ 80%**

Run: `pytest --cov`
Expected: PASS; total coverage for `slime` + `sim` (excluding adapters) ≥ 80%.

- [ ] **Step 7: Commit**

```bash
git add sim/ tests/test_simulator.py
git commit -m "feat: add day-in-the-life simulator over the pure mood loop"
```

---

## Task 9: `assets/make_assets.py` — placeholder sprite sheet

**Files:**
- Create: `assets/make_assets.py`
- Create (generated): `assets/slime.bmp`

A 7-frame horizontal sprite sheet of 64×64 indexed (grayscale) poses, ordered to match
`POSE_INDEX` (content, sleepy, curious, happy, contemplative, dizzy, resting). These are
intentionally simple placeholders — the dithered pixel style can be hand-refined later.

- [ ] **Step 1: Write the generator**

`assets/make_assets.py`:
```python
"""Generate assets/slime.bmp: a 7-frame 64x64 indexed sprite sheet. Run: python3 assets/make_assets.py"""
from PIL import Image, ImageDraw

FRAME = 64
POSES = ["content", "sleepy", "curious", "happy", "contemplative", "dizzy", "resting"]
BLACK, GRAY, LIGHT, WHITE = 0, 1, 2, 3  # palette indices


def _blob(d, ox):
    # rounded body
    d.rectangle([ox + 16, 14, ox + 48, 56], fill=BLACK)
    d.rectangle([ox + 10, 22, ox + 54, 56], fill=BLACK)
    d.rectangle([ox + 14, 20, ox + 50, 54], fill=GRAY)


def _eyes(d, ox, y, w=4, h=10, open_=True):
    for ex in (ox + 22, ox + 38):
        if open_:
            d.rectangle([ex, y, ex + w, y + h], fill=BLACK)
        else:
            d.rectangle([ex, y + h // 2, ex + w + 4, y + h // 2 + 2], fill=BLACK)


def draw_pose(d, ox, pose):
    _blob(d, ox)
    if pose == "sleepy":
        _eyes(d, ox, 36, open_=False)
        d.rectangle([ox + 30, 46, ox + 36, 49], fill=BLACK)
    elif pose == "curious":
        _eyes(d, ox, 30, h=12)
        d.rectangle([ox + 30, 46, ox + 36, 50], fill=BLACK)
    elif pose == "happy":
        d.arc([ox + 20, 28, ox + 30, 38], 180, 360, fill=BLACK, width=3)
        d.arc([ox + 36, 28, ox + 46, 38], 180, 360, fill=BLACK, width=3)
        d.arc([ox + 26, 40, ox + 42, 52], 0, 180, fill=BLACK, width=3)
    elif pose == "contemplative":
        _eyes(d, ox, 34, open_=False)
        d.rectangle([ox + 30, 47, ox + 38, 49], fill=BLACK)
    elif pose == "dizzy":
        for ex in (ox + 22, ox + 38):
            d.line([ex, 32, ex + 6, 40], fill=BLACK, width=2)
            d.line([ex + 6, 32, ex, 40], fill=BLACK, width=2)
        d.ellipse([ox + 28, 44, ox + 38, 52], outline=BLACK, width=2)
    elif pose == "resting":
        _eyes(d, ox, 38, open_=False)
    else:  # content
        _eyes(d, ox, 34)
        d.rectangle([ox + 28, 47, ox + 40, 50], fill=BLACK)


def main():
    sheet = Image.new("P", (FRAME * len(POSES), FRAME), WHITE)
    # 4-level grayscale palette (indices map to E-Ink grays)
    sheet.putpalette([0, 0, 0, 90, 90, 90, 170, 170, 170, 255, 255, 255] + [0] * (256 * 3 - 12))
    d = ImageDraw.Draw(sheet)
    for i, pose in enumerate(POSES):
        draw_pose(d, i * FRAME, pose)
    sheet.save("assets/slime.bmp")
    print(f"wrote assets/slime.bmp ({sheet.width}x{sheet.height}, {len(POSES)} frames)")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Generate the sprite sheet**

Run: `python3 assets/make_assets.py`
Expected: `wrote assets/slime.bmp (448x64, 7 frames)`.

- [ ] **Step 3: Eyeball it**

Run: `python3 -c "from PIL import Image; Image.open('assets/slime.bmp').show()"`
Expected: 7 small grayscale slime faces in a row.

- [ ] **Step 4: Commit**

```bash
git add assets/make_assets.py assets/slime.bmp
git commit -m "feat: add sprite-sheet generator and placeholder poses"
```

---

## Task 10: `slime/sensors.py` — hardware adapter (DEVICE)

**Files:**
- Create: `slime/sensors.py`

This adapter is verified on the MagTag, not in pytest. It returns normalized values the pure
`mood.Inputs` expects.

- [ ] **Step 1: Implement `slime/sensors.py`**

```python
"""Hardware adapter: battery, USB, light, accelerometer. Device-only (imports board/libs)."""
import board
import analogio
import supervisor
import adafruit_lis3dh
from slime.interactions import AccelReading

_LIGHT_MAX = 65535.0
_BATTERY_MIN_V = 3.3   # ~empty LiPo
_BATTERY_MAX_V = 4.2   # ~full LiPo


class Sensors:
    def __init__(self):
        self._light = analogio.AnalogIn(board.LIGHT)
        self._battery = analogio.AnalogIn(board.BATTERY)
        i2c = board.I2C()
        self._accel = adafruit_lis3dh.LIS3DH_I2C(i2c, address=0x19)
        self._accel.range = adafruit_lis3dh.RANGE_4_G
        # Enable single + double tap on INT1.
        self._accel.set_tap(2, 60)

    def light(self):
        """Ambient light 0.0 (dark) .. 1.0 (bright)."""
        return self._light.value / _LIGHT_MAX

    def battery(self):
        """Battery charge 0.0 .. 1.0 from the divided cell voltage."""
        volts = (self._battery.value / 65535.0) * 3.3 * 2.0
        frac = (volts - _BATTERY_MIN_V) / (_BATTERY_MAX_V - _BATTERY_MIN_V)
        return min(1.0, max(0.0, frac))

    def on_usb(self):
        """True when powered/communicating over USB."""
        return supervisor.runtime.usb_connected

    def reading(self):
        """Current AccelReading (m/s^2) with tap flags consumed from the sensor."""
        x, y, z = self._accel.acceleration
        tapped = bool(self._accel.tapped)  # True on any tap since last read
        return AccelReading(x=x, y=y, z=z, tapped=tapped, double_tapped=False)
```

> Note: the LIS3DH `tapped` property reports taps since last read; distinguishing single vs.
> double in hardware is configured via `set_tap(2, ...)`. For the MVP we treat a detected tap as
> a single `tap` and rely on the gesture rules for the rest; double-tap can be refined later by
> reading the click source register. The pure `interactions.detect` already supports a
> `double_tapped` flag for when that refinement lands.

- [ ] **Step 2: Verify on device (after Task 14 bring-up, or standalone)**

Copy `slime/` to `CIRCUITPY`, then in the serial REPL:
```python
from slime.sensors import Sensors
s = Sensors()
print(s.light(), s.battery(), s.on_usb())
print(s.reading())
```
Expected: light changes when you cover the sensor; battery in 0..1; `on_usb` True on USB; reading shows ~9.8 on the up axis.

- [ ] **Step 3: Commit**

```bash
git add slime/sensors.py
git commit -m "feat: add sensors hardware adapter"
```

---

## Task 11: `slime/pixels.py` — NeoPixel breathing (DEVICE)

**Files:**
- Create: `slime/pixels.py`

- [ ] **Step 1: Implement `slime/pixels.py`**

```python
"""Hardware adapter: NeoPixel breathing. Device-only. Uses pure slime.visuals for the math."""
import board
import digitalio
import neopixel
from slime.visuals import mood_to_rgb, breath_brightness

_NUM = 4


class Pixels:
    def __init__(self):
        # MagTag gates NeoPixel power through a dedicated pin.
        self._power = digitalio.DigitalInOut(board.NEOPIXEL_POWER)
        self._power.direction = digitalio.Direction.OUTPUT
        self._power.value = True
        self._np = neopixel.NeoPixel(board.NEOPIXEL, _NUM, auto_write=False)

    def breathe(self, mood, t, rate=0.25):
        """Paint one breath frame for the current mood at time t (seconds)."""
        r, g, b = mood_to_rgb(mood)
        level = breath_brightness(t, rate=rate)
        self._np.fill((int(r * level), int(g * level), int(b * level)))
        self._np.show()

    def flash(self, rgb):
        """A brief reaction color (e.g., dizzy)."""
        self._np.fill(rgb)
        self._np.show()

    def off(self):
        self._np.fill((0, 0, 0))
        self._np.show()
        self._power.value = False
```

- [ ] **Step 2: Verify on device**

In the REPL:
```python
import time
from slime.state import default_state
from slime.pixels import Pixels
p = Pixels()
s = default_state()
for i in range(200):
    p.breathe(s.mood, i * 0.05); time.sleep(0.05)
p.off()
```
Expected: a calm teal breathing glow that brightens and dims smoothly, then off.

- [ ] **Step 3: Commit**

```bash
git add slime/pixels.py
git commit -m "feat: add NeoPixel breathing adapter"
```

---

## Task 12: `slime/display.py` — E-Ink rendering (DEVICE)

**Files:**
- Create: `slime/display.py`

- [ ] **Step 1: Implement `slime/display.py`**

```python
"""Hardware adapter: render the slime pose + optional quip on E-Ink. Device-only."""
import board
import displayio
import terminalio
from adafruit_display_text import label
from slime.visuals import expression_to_pose

_FRAME = 64
_SCALE = 2  # 64px sprite -> 128px tall, fills the panel height


class Display:
    def __init__(self, sheet_path="/assets/slime.bmp"):
        self._display = board.DISPLAY
        self._bitmap = displayio.OnDiskBitmap(sheet_path)
        self._tile = displayio.TileGrid(
            self._bitmap,
            pixel_shader=self._bitmap.pixel_shader,
            width=1, height=1,
            tile_width=_FRAME, tile_height=_FRAME,
        )
        self._group = displayio.Group(scale=_SCALE)
        self._group.append(self._tile)
        # Position the sprite group (scaled coords).
        self._group.x = 20
        self._group.y = 0
        self._root = displayio.Group()
        self._root.append(self._group)
        self._quip = label.Label(terminalio.FONT, text="", color=0x000000, scale=1)
        self._quip.anchor_point = (0.5, 1.0)
        self._quip.anchored_position = (self._display.width // 2, self._display.height - 6)
        self._root.append(self._quip)

    def render(self, expression, quip_text=""):
        """Set the pose frame + quip and refresh the panel (blocking, slow)."""
        self._tile[0] = expression_to_pose(expression)
        self._quip.text = quip_text or ""
        self._display.root_group = self._root
        # Respect the panel's mandated minimum refresh interval.
        while self._display.time_to_refresh > 0:
            pass
        self._display.refresh()
```

- [ ] **Step 2: Verify on device**

In the REPL (sprite sheet must be copied to `/assets/slime.bmp`):
```python
from slime.display import Display
d = Display()
d.render("happy", "you came back")
```
Expected: a slime face appears on the panel with the quip line beneath it after a slow refresh.

- [ ] **Step 3: Commit**

```bash
git add slime/display.py
git commit -m "feat: add E-Ink display adapter"
```

---

## Task 13: `slime/power.py` — deep-sleep / wake (DEVICE)

**Files:**
- Create: `slime/power.py`

- [ ] **Step 1: Implement `slime/power.py`**

```python
"""Hardware adapter: deep-sleep and wake sources. Device-only."""
import alarm
import time
import board


def woke_from_deep_sleep():
    """True if this run began by waking from deep sleep."""
    return alarm.wake_alarm is not None


def nap(seconds, motion_pin=board.ACCELEROMETER_INTERRUPT):
    """Enter deep sleep until `seconds` elapse OR the accelerometer signals motion.

    Returns control to a fresh boot on wake (deep sleep restarts code.py); NVM persists.
    """
    time_alarm = alarm.time.TimeAlarm(monotonic_time=time.monotonic() + seconds)
    try:
        pin_alarm = alarm.pin.PinAlarm(pin=motion_pin, value=True, pull=True)
        alarm.exit_and_deep_sleep_until_alarms(time_alarm, pin_alarm)
    except (ValueError, AttributeError):
        # If the INT pin isn't wake-capable on this board revision, fall back to time only.
        alarm.exit_and_deep_sleep_until_alarms(time_alarm)
```

> Note: `board.ACCELEROMETER_INTERRUPT` is the LIS3DH INT pin on the MagTag. If a board
> revision lacks it, the fallback uses a timed nap only. The accelerometer must be configured to
> raise INT on tap/motion (done in `Sensors.__init__` via `set_tap`).

- [ ] **Step 2: Verify on device**

In the REPL:
```python
from slime.power import nap
nap(15)   # device sleeps; wakes after 15s or when you tap it. The REPL session ends (deep sleep restarts).
```
Expected: the board powers down (NeoPixels off, REPL disconnects) and restarts within 15s or on tap.

- [ ] **Step 3: Commit**

```bash
git add slime/power.py
git commit -m "feat: add deep-sleep power adapter with motion + time wake"
```

---

## Task 14: `code.py` — orchestration (DEVICE)

**Files:**
- Create: `code.py`

One cycle: load → sense → interpret → think → maybe refresh display → set pixels → persist →
then either breathe in a loop (USB) or deep-sleep (battery).

- [ ] **Step 1: Implement `code.py`**

```python
"""Slime Pet — Local Soul entry point. Runs on the MagTag under CircuitPython."""
import time
from slime import persistence
from slime.mood import Inputs, step
from slime.interactions import new_detector, detect
from slime.quips import pick
from slime.visuals import should_refresh, choose_run_mode, CONTINUOUS
from slime.sensors import Sensors
from slime.pixels import Pixels
from slime.display import Display
from slime import power

# Refresh policy constants.
_MIN_REFRESH = 180.0       # seconds; protect the panel from flicker
_SCHEDULED = 21600.0       # seconds (~4x/day) for an unconditional refresh
_NAP_SECONDS = 1800.0      # battery nap length between wake cycles
_TICK = 0.05               # breathing frame period (USB loop)


def _gather(sensors, detector):
    reading = sensors.reading()
    events, detector = detect(detector, reading)
    inputs = Inputs(
        light=sensors.light(),
        battery=sensors.battery(),
        on_usb=sensors.on_usb(),
        seconds_since_interaction=0.0 if events else 60.0,
        events=events,
    )
    return inputs, events, detector


def main():
    now = time.monotonic()
    state = persistence.load(now)
    sensors = Sensors()
    pixels = Pixels()
    display = Display()
    detector = new_detector()

    # First thought of this wake.
    inputs, events, detector = _gather(sensors, detector)
    prev_expression = state.expression
    state = step(state, inputs, 1.0)
    if events:
        state = state._replace(total_boops=state.total_boops + (1 if "double_tap" in events else 0))

    quip = pick(state.behavior if state.behavior == "greeting" else state.expression)
    if should_refresh(time.monotonic(), state.last_seen,
                      pose_changed=(state.expression != prev_expression),
                      significant_event=bool(events),
                      min_interval=_MIN_REFRESH, scheduled_interval=_SCHEDULED):
        try:
            display.render(state.expression, quip or "")
            state = state._replace(last_seen=time.monotonic())
        except Exception:
            pass  # never let a render failure kill the creature

    persistence.save(state)

    if choose_run_mode(inputs.on_usb, inputs.battery) == CONTINUOUS:
        # Always-breathing desk mode.
        t0 = time.monotonic()
        while True:
            inputs, events, detector = _gather(sensors, detector)
            if events:
                prev = state.expression
                state = step(state, inputs, 1.0)
                if "double_tap" in events:
                    state = state._replace(total_boops=state.total_boops + 1)
                if state.behavior == "dizzy":
                    pixels.flash((120, 0, 0))
                    time.sleep(0.4)
                if should_refresh(time.monotonic(), state.last_seen,
                                  pose_changed=(state.expression != prev),
                                  significant_event=True,
                                  min_interval=_MIN_REFRESH, scheduled_interval=_SCHEDULED):
                    try:
                        display.render(state.expression, pick(
                            state.behavior if state.behavior == "greeting" else state.expression) or "")
                        state = state._replace(last_seen=time.monotonic())
                    except Exception:
                        pass
                persistence.save(state)
            rate = 0.12 + (state.mood.energy / 100.0) * 0.35  # brisker when energetic
            pixels.breathe(state.mood, time.monotonic() - t0, rate=rate)
            time.sleep(_TICK)
    else:
        # Battery: a short greeting breath, then nap.
        t0 = time.monotonic()
        while time.monotonic() - t0 < 4.0:
            pixels.breathe(state.mood, time.monotonic() - t0, rate=0.2)
            time.sleep(_TICK)
        pixels.off()
        power.nap(_NAP_SECONDS)


main()
```

- [ ] **Step 2: Commit**

```bash
git add code.py
git commit -m "feat: orchestrate one sense-think-show-persist cycle with adaptive power"
```

---

## Task 15: On-device bring-up & success-criteria verification

**Files:** none (verification only)

- [ ] **Step 1: Flash CircuitPython**

Double-tap the MagTag reset to enter the bootloader (`MAGTAGBOOT` drive mounts). Drag the
CircuitPython 9.x MagTag `.uf2` onto it. The board reboots and mounts `CIRCUITPY`.

- [ ] **Step 2: Install libraries**

Run:
```bash
pip3 install circup
circup install adafruit_lis3dh neopixel adafruit_display_text
```
Expected: libraries copied into `CIRCUITPY/lib`.

- [ ] **Step 3: Copy project files**

Run (adjust the mount path if different):
```bash
cp -r slime /Volumes/CIRCUITPY/
cp -r assets /Volumes/CIRCUITPY/
cp code.py /Volumes/CIRCUITPY/
```
Expected: files present on the drive; the board auto-reloads and runs `code.py`.

- [ ] **Step 4: Verify against the spec's success criteria**

Watch the device and the serial console (`screen /dev/tty.usbmodem* 115200` or the Mu/Thonny serial monitor). Confirm each:

1. [ ] Boots to a pixel slime in a mood-appropriate expression on the E-Ink panel.
2. [ ] On USB: NeoPixels breathe continuously. On battery (unplug): a short greeting breath, then deep-sleep; tapping wakes it.
3. [ ] Reacts to tap / double-tap / shake / pickup / setdown / flip (watch serial prints / pixel reactions; dizzy flash on shake/flip).
4. [ ] Mood shifts believably: cover the light sensor → it trends sleepy; interact → curiosity/affection rise.
5. [ ] A quip line appears beneath the slime on a greeting or scheduled refresh.
6. [ ] Power-cycle the board → it remembers `total_boops` and prior mood (NVM survived). Verify in REPL: `import microcontroller; from slime.persistence import unpack, BLOB_SIZE; print(unpack(bytes(microcontroller.nvm[0:BLOB_SIZE])))`.
7. [ ] Pulling a sensor (e.g., wrong I2C) does not brick it — it falls back gracefully (temporarily edit to force an error and confirm a calm resting render rather than a crash dump; then revert).
8. [ ] Host tests still green: `pytest --cov` ≥ 80%.

- [ ] **Step 5: Tag the milestone**

```bash
git tag -a phase0-mvp -m "Local Soul MVP working on hardware"
git commit --allow-empty -m "chore: Local Soul MVP verified on device"
```

---

## Notes for the implementer

- **Pure vs. adapter discipline:** never `import board` (or any hardware lib) at the top of a
  pure module. Tests import only pure modules; if a test file ever fails with a hardware
  `ImportError`, a boundary has leaked.
- **NVM is small (8 KB) but our blob is tiny (~40 bytes).** Plenty of headroom for Phase 1.
- **E-Ink is slow and refresh-limited.** Keep `_MIN_REFRESH` honest; the NeoPixels carry liveness.
- **No RTC yet:** `time.monotonic()` resets on deep-sleep/power-loss, so "scheduled" refreshes are
  uptime-relative, not wall-clock. This is expected for Phase 0 (see the spec's constraints).
