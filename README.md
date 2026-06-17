# 🫧 MagTag Slime Pet

[![CI](https://github.com/JoshuaAFerguson/magtag-slime-pet/actions/workflows/ci.yml/badge.svg)](https://github.com/JoshuaAFerguson/magtag-slime-pet/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![CircuitPython](https://img.shields.io/badge/CircuitPython-10.x-5b2a86.svg)](https://circuitpython.org/)

A calm, ambient companion living on an Adafruit MagTag.

Not a Tamagotchi. Not a productivity tool. Not an AI assistant. A small creature that shares
the desk, notices the world, remembers time passing, and occasionally surprises its owner.

## Philosophy

- **Never punish absence.** The slime never dies, never gets sick, never loses progress. It may
  miss you, grow contemplative, or tell stories — but it never punishes.
- **Slow technology.** The E-Ink display is intentionally slow; the creature's body changes only
  a few times a day.
- **Living heartbeat.** The NeoPixels are always breathing — present even when the display is still.
- **Offline first.** It is fully alive without WiFi. Cloud services (a future phase) only make it
  deeper; they never define it.

## Hardware

Built on the [Adafruit MagTag](https://www.adafruit.com/product/4800) (ESP32-S2, 2.9" grayscale
E-Ink, 4 NeoPixels, LIS3DH accelerometer, light sensor, LiPo support). Later phases add optional
parts (capacitive touch, RTC, environmental sensor, microphone, better speaker).

## Architecture

A strict split keeps the soul testable on a desktop and the hardware thin:

- **Pure logic** (`slime/state.py`, `mood.py`, `interactions.py`, `quips.py`, `visuals.py`,
  `persistence.py` pack/unpack) — no hardware imports; runs and is unit-tested under desktop
  CPython.
- **Hardware adapters** (`slime/sensors.py`, `pixels.py`, `display.py`, `power.py`) — thin wrappers
  over CircuitPython libraries; verified on-device.
- **`code.py`** — orchestrates one sense → think → show → persist cycle, then breathes (on USB) or
  deep-sleeps until motion/timeout (on battery).

State persists in `microcontroller.nvm`, surviving power loss without needing a writable filesystem.

## Quickstart (development, no hardware needed)

```bash
pip install pytest pytest-cov pillow
pytest                        # host-side unit tests
python sim/simulator.py       # watch a scripted "day in the life"
python assets/make_assets.py  # regenerate the pixel sprite sheet
```

## Deploy to the MagTag

1. Flash [CircuitPython](https://circuitpython.org/board/adafruit_magtag_2.9_grayscale/) (9.x or
   10.x): double-tap RESET to mount the bootloader drive, then drag the `.uf2` onto it.
2. Install libraries:
   ```bash
   circup install adafruit_lis3dh neopixel adafruit_display_text
   ```
3. Copy `code.py`, the `slime/` package, and `assets/` to the `CIRCUITPY` drive.

> ⚡ If the board enters safe mode with "Power dipped", use a powered USB port and a known-good
> data cable — the E-Ink refresh plus NeoPixels need adequate current.

## Roadmap

- **Phase 0 — Local Soul (shipped):** offline mood engine, gesture detection, breathing NeoPixels,
  pixel-art E-Ink rendering, quips, NVM memory.
- **Phase 1 — Richer offline behaviors:** morphology/forms, sound, friendship/familiarity, local
  dreams & lore.
- **Phase 2 — Cloud dreamscape:** an optional home-API "oracle" (weather, moon, summaries, dreams)
  with graceful offline fallback.
- **Phase 3 — Hardware add-ons:** touch, RTC, environmental sensor, microphone, better speaker.

Design docs live in [`docs/superpowers/specs/`](docs/superpowers/specs/) and implementation plans
in [`docs/superpowers/plans/`](docs/superpowers/plans/).

## License

[MIT](LICENSE) © 2026 Joshua Ferguson
