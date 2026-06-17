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
