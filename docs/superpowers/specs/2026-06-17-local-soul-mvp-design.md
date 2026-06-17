# Slime Pet — Local Soul MVP (Phase 0) Design

**Date:** 2026-06-17
**Status:** Approved (design)
**Scope:** Phase 0 of the MagTag Slime Pet v2 vision — the offline-first "Local Soul."

---

## Context

The MagTag Slime Pet is a calm, ambient desk companion: a small creature that lives on
an Adafruit MagTag (ESP32-S2), notices the world, and never punishes absence. The full
vision spans many subsystems and a two-tier architecture (a local soul on the device, a
cloud "dreamscape" on an Orange Pi cluster). That is too much for one spec.

### Roadmap (decomposition)

The vision is split into four phases, each its own spec → plan → build cycle:

1. **Phase 0 — Local Soul MVP** *(this spec)*. Fully offline; uses only the MagTag's
   built-in hardware. The heartbeat everything else builds on.
2. **Phase 1 — Richer offline behaviors.** Morphology/forms, journal, expanded quips,
   sound (piezo), friendship/familiarity, seasonal & time-of-day behavior, local dreams + lore.
3. **Phase 2 — Cloud dreamscape.** Orange Pi home API as an optional oracle (weather, moon,
   calendar/email/GitHub summaries, dream generation, long-term memory), plus a MagTag WiFi
   client with graceful offline fallback.
4. **Phase 3 — Hardware add-ons.** Capacitive touch (petting), RTC (reliable time), environmental
   sensor (BME280/680/SHT40), microphone (room awareness), better speaker. Each = a driver plus a
   mood-engine input, folded in as parts arrive.

Phase 0 must not assume any add-on hardware exists.

## Design Decisions (locked)

| Decision | Choice | Rationale |
|---|---|---|
| Firmware stack | **CircuitPython** | First-class MagTag support (displayio, neopixel, adafruit_lis3dh, alarm); fastest iteration by editing files on `CIRCUITPY`. |
| Power & presence | **Adaptive** | Detect USB vs. battery and switch behavior: USB → always breathing; battery → bursty motion-wake + deep sleep. Most lifelike; honors "always present" and "never punish absence." |
| Art direction | **Dithered pixel art** | Renders crisply on grayscale E-Ink; easy to author/store as indexed bitmaps; maximum "tiny creature" charm. |
| Screen layout | **Creature + occasional quip** | The body fills the panel; a single line surfaces now and then as the creature's *voice* (not a stat). |

## Hardware Used (Phase 0)

Only built-in MagTag hardware: 2.9" grayscale E-Ink (296×128), 4 NeoPixels, LIS3DH
accelerometer, light sensor, battery/USB sense. **No** touch, RTC, environmental sensor,
microphone, or external speaker in this phase.

---

## Architecture

A clean split between **pure logic** (no hardware imports; testable on desktop CPython) and
**thin hardware adapters** (talk to the MagTag). This is what makes the soul offline-first
and unit-testable.

```
code.py                  # entry: boot, run loop (USB) or wake-cycle (battery)
boot.py                  # remount filesystem writable when untethered (future-proofing persistence)
slime/
  state.py               # the creature's state; immutable updates → new state
  mood.py                # PURE: inputs → mood vector → expression + behavior
  interactions.py        # PURE: accel data → tap/double-tap/shake/pickup/setdown/flip
  quips.py               # PURE: pick a quip from mood/context
  persistence.py         # load/save core state to microcontroller NVM
  sensors.py             # adapter: battery, USB sense, light, LIS3DH
  display.py             # adapter: displayio pose bitmap + quip text, refresh policy
  pixels.py              # adapter: NeoPixel "breathing" engine
  power.py               # adapter: detect USB/battery, deep-sleep via `alarm`
assets/
  slime.bmp              # indexed pixel sprite sheet (poses)
  font.bdf               # bitmap font for quips
```

The four `PURE` modules (`state`, `mood`, `interactions`, `quips`) have no hardware
dependencies — the personality lives there, and tests run there.

### Data flow (one cycle)

```
wake/boot
  → persistence.load() from NVM
  → sensors.read() (battery, USB, light, accelerometer)
  → interactions.interpret(accel) → events
  → mood.step(state, inputs, dt) → new state (expression + behavior)
  → display.maybe_refresh(state)        # only if pose changed / scheduled / significant event
  → pixels.set_target(state)            # mood hue + breathing rate
  → persistence.save(new state) to NVM
  → power: USB → continue loop (breathe); battery → arm alarms, deep sleep
```

## Mood Engine

Five drives (0–100), per the vision: **energy, comfort, curiosity, sleepiness, affection**.

`mood.step(state, inputs, dt) -> state` is pure and returns a new state (no mutation).

**Inputs (Phase 0, built-in hardware only):** battery level, USB/battery state, ambient
light, interaction events, elapsed time since last interaction.

**Outputs:** a dominant **expression** (content / sleepy / curious / happy / contemplative)
and a **behavior** (idle, greeting, dizzy, settling, …). Sound, temperature, and touch are
explicitly *not* inputs in this phase.

## Presentation

### E-Ink (the body — slow)

The dithered pixel slime in a mood expression, plus an occasional one-line quip.

Refresh policy:
- **~4 scheduled updates/day** (morning / midday / evening / night).
- **Event-driven** refreshes on meaningful moments (a greeting, a genuine mood shift, a new quip).
- **Rate-limited** to a minimum interval to protect the panel and battery.

The slow display never carries moment-to-moment liveness.

### NeoPixels (the heartbeat — live)

Breathing brightness via a sine curve.
- **Hue = dominant mood:** calm teal, curious amber, sleepy dim-blue, affectionate rose,
  energetic brighter.
- **Rate = arousal/energy:** slow when sleepy, brisk when energetic.
- **USB:** breathes continuously. **Battery:** short greeting burst on wake, then settles.

## Interactions (accelerometer)

| Gesture | Reaction |
|---|---|
| double-tap | greeting (may trigger display refresh) |
| tap | acknowledge |
| pickup | curious / attentive |
| setdown | settle |
| shake | gently dizzy |
| flip | seasick, dizzy pixels |

Each nudges the mood vector and fires an immediate NeoPixel reaction. Nothing punishes —
shake/flip are playful disorientation, not damage (Rule 1).

## Persistence & Memory

Core state lives in **`microcontroller.nvm`**: non-volatile, writable from code at any time,
survives power loss, and avoids the classic CircuitPython problem of being unable to write the
filesystem while USB is mounted on the host.

Stored: last-seen time, total boops, longest absence, first-boot, current mood vector, current
pose. **No numbers are ever shown — only behavior.** (Journal text and larger memory move to
the filesystem in Phase 1.)

## Constraints & Honest Limitations

- **No real clock (yet).** Without the RTC add-on (Phase 3), absolute time resets on full power
  loss. MVP uses **elapsed time + light-based day/night inference** instead of wall-clock.
  Behaviors needing true dates (streaks, moon phases) wait for the RTC.
- **Adaptive power is the intricate part.** Detecting USB vs. battery and running two loop modes
  (continuous breathing vs. motion-wake deep sleep) is the most complex piece of the MVP, but it
  is what makes "always present, never dies" real.

## Error Handling

- Every sensor read is wrapped; a failed/missing sensor **degrades gracefully** — the slime keeps
  living.
- Unexpected errors fall back to a calm "resting" pose, never a dead screen.
- Per Rule 1, no failure state ever punishes the creature.

## Testing

- **Host-side unit tests (desktop CPython) at ≥80% coverage** for the pure modules: `mood`,
  `interactions`, `quips`, `state`.
- A small **simulator** runs the mood loop over scripted inputs to observe a "day in the life"
  without hardware.
- Hardware adapters (`sensors`, `display`, `pixels`, `power`) are kept thin and sit behind
  interfaces so the pure core stays testable; they get a mock/simulated backend.

## Success Criteria (MVP "done")

1. Boots to a pixel slime in a mood-appropriate expression.
2. Auto-detects power; breathes continuously on USB, bursty + deep-sleep on battery.
3. Reacts to all six accelerometer gestures.
4. Mood shifts believably from light, battery, elapsed time, and interaction history.
5. Quips surface occasionally.
6. State survives resets/power loss; remembers boops & last-seen.
7. Never dies, never hard-crashes; degrades gracefully.
8. Core logic unit-tested on host ≥80%.

## Out of Scope (Phase 0)

Morphology/forms, journal, friendship unlocks, sound, seasonal/holiday behavior, dreams,
artifacts, visitors, weather/moon, lore depth, WiFi/cloud, and all add-on sensors. These belong
to later phases.
