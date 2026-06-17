# Contributing

Thanks for your interest in the MagTag Slime Pet! This is a small, calm hobby project, but
contributions are welcome.

## Development setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install pytest pytest-cov pillow ruff black
pytest                     # run the host test suite
python sim/simulator.py    # watch a scripted day
```

No hardware is needed to develop or test the pure logic.

## The one architectural rule

Keep the **pure / adapter split** intact:

- **Pure modules** (`slime/state.py`, `mood.py`, `interactions.py`, `quips.py`, `visuals.py`,
  `persistence.py`) must **not** import hardware libraries (`board`, `neopixel`, `displayio`,
  `microcontroller`, `alarm`, `analogio`, `digitalio`, `adafruit_*`, `supervisor`). They run on a
  desktop and are unit-tested there.
- **Adapters** (`slime/sensors.py`, `pixels.py`, `display.py`, `power.py`) and `code.py` may import
  hardware libraries and are verified on-device.

A guard test (`tests/test_state.py::test_production_modules_avoid_namedtuple_replace`) enforces a
related CircuitPython gotcha: don't use `namedtuple._replace()` (CircuitPython lacks it) — use
`state.evolve()` instead.

## Before opening a PR

```bash
ruff check .
black --check .
pytest
```

All three must pass — CI runs exactly these. New behavior in a pure module should come with tests
(the project targets ≥80% coverage on the pure layer). For hardware adapters, describe how you
verified on the device.

## Style

- PEP 8, formatted with `black` (line length 100) and linted with `ruff`.
- Many small, focused files over large ones.
- Stay true to the philosophy: the slime never punishes, never nags, and stays calm.
