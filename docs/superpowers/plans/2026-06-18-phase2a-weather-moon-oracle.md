# Phase 2a — Weather + Moon Oracle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A FastAPI "home oracle" on the Orange Pi serving weather (Open-Meteo, Phoenix) + computed moon phase, and a MagTag client that fetches it on the daily WiFi sync, caches it in NVM, and reacts (mood bias, weather forms, weather/moon quips, moon-flavored dreams) — fully offline-safe.

**Architecture:** Two tiers in one repo. `server/` is a standalone CPython FastAPI service (host-tested, Dockerized) built first. The device side extends the existing pure/adapter `slime/` package: pure effects logic + a thin `netoracle` HTTP adapter, with the cached oracle in its own NVM slot (state stays v3).

**Tech Stack:** Server: Python 3.12, FastAPI, uvicorn, httpx. Device: CircuitPython 10.x, `adafruit_requests`. Host testing: pytest/ruff/black (line length 100).

**Conventions:** Device code (`slime/`, `code.py`) keeps the rules: no hardware imports in pure modules, no `namedtuple._replace` (use `state.evolve`). Server code is ordinary CPython. Run device tests from repo root (`.venv/bin/python -m pytest`); run server tests from `server/` (`.venv/bin/python -m pytest`, with fastapi/httpx installed in `.venv`).

---

## File Structure

```
server/                      # Tier 1 — home API (standalone CPython)
  app/__init__.py
  app/config.py              # env: SLIME_LAT/LON/TZ (default Phoenix), ORACLE_TOKEN
  app/moon.py                # PURE: moon phase + illumination from a date
  app/weather.py             # fetch_raw(httpx) + normalize(pure) -> feeling tags
  app/oracle.py              # assemble the /oracle payload
  app/main.py                # FastAPI: GET /oracle, GET /health, optional bearer auth
  tests/test_moon.py
  tests/test_weather.py
  tests/test_oracle.py
  tests/test_main.py
  requirements.txt
  pyproject.toml             # pytest config for the server
  Dockerfile
  docker-compose.yml
slime/                       # Tier 2 — device client
  oracle.py                  # PURE: parse/effects/cache pack-unpack; device save/load (lazy)
  netoracle.py               # ADAPTER: HTTP GET /oracle over WiFi
  visuals.py                 # MODIFY: POSE_INDEX += melting/hiding; ACCENT_MOON
  forms.py                   # MODIFY: choose_render gains weather param
  quips.py                   # MODIFY: weather/moon quip pools
  dreams.py                  # MODIFY: generate() accepts extra_refs
assets/make_assets.py        # MODIFY: melting/hiding forms + moon accent
code.py                      # MODIFY: fetch+cache oracle, apply effects
.github/workflows/ci.yml     # MODIFY: add a server test job
```

Host-tested: all `server/app/*` (HTTP mocked) and the device pure modules (`slime/oracle`, `forms`,
`quips`, `dreams`).

---

# TIER 1 — HOME API (build first)

## Task S1: Server scaffolding

**Files:** Create `server/app/__init__.py`, `server/app/config.py`, `server/tests/__init__.py`,
`server/requirements.txt`, `server/pyproject.toml`

- [ ] **Step 1: Install server deps into the venv**

Run: `.venv/bin/pip install fastapi "uvicorn[standard]" httpx`
Expected: installs successfully (httpx powers both the weather client and FastAPI's TestClient).

- [ ] **Step 2: Create `server/requirements.txt`**
```text
fastapi==0.115.6
uvicorn[standard]==0.34.0
httpx==0.28.1
```

- [ ] **Step 3: Create `server/pyproject.toml`** (includes black/ruff config at line-length 100 so
  the CI server job — which runs from inside `server/` — matches the rest of the repo):
```toml
[tool.pytest.ini_options]
pythonpath = ["."]
testpaths = ["tests"]
addopts = "-q"

[tool.coverage.run]
source = ["app"]
omit = ["app/main.py"]

[tool.black]
line-length = 100

[tool.ruff]
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "I"]
```

- [ ] **Step 4: Create empty markers** `server/app/__init__.py` (empty) and
  `server/tests/__init__.py` (empty).

- [ ] **Step 5: Create `server/app/config.py`**
```python
"""Server configuration from environment variables."""
import os

LAT = float(os.getenv("SLIME_LAT", "33.4484"))   # Phoenix
LON = float(os.getenv("SLIME_LON", "-112.0740"))
TZ = os.getenv("SLIME_TZ", "America/Phoenix")
ORACLE_TOKEN = os.getenv("ORACLE_TOKEN", "")      # empty -> no auth on the LAN
```

- [ ] **Step 6: Verify pytest discovers (no tests yet)**

Run: `cd server && ../.venv/bin/python -m pytest`
Expected: "no tests ran" (exit 5).

- [ ] **Step 7: Commit**
```bash
git add server/app/__init__.py server/app/config.py server/tests/__init__.py server/requirements.txt server/pyproject.toml
git commit -m "chore: scaffold home oracle FastAPI server"
```

---

## Task S2: `server/app/moon.py` — moon phase (PURE)

**Files:** Create `server/app/moon.py`; Test `server/tests/test_moon.py`

- [ ] **Step 1: Write the failing tests** — `server/tests/test_moon.py`:
```python
from app.moon import moon


def test_new_moon_2000():
    m = moon(2000, 1, 6)  # ~new moon
    assert m["phase"] == 0
    assert m["illum"] < 0.1
    assert m["name"] == "new"


def test_full_moon_2000():
    m = moon(2000, 1, 21)  # ~full moon
    assert m["phase"] == 4
    assert m["illum"] > 0.9
    assert m["name"] == "full"


def test_illumination_and_phase_bounds():
    for day in range(1, 29):
        m = moon(2026, 6, day)
        assert 0 <= m["phase"] <= 7
        assert 0.0 <= m["illum"] <= 1.0
```

- [ ] **Step 2: Run** `cd server && ../.venv/bin/python -m pytest tests/test_moon.py -v` — expect FAIL (no module).

- [ ] **Step 3: Implement `server/app/moon.py`**
```python
"""Pure moon-phase math from a civil date. No external dependencies."""
import math

_SYNODIC = 29.53058867          # mean synodic month, days
_REF_NEW_MOON_JD = 2451550.1    # JD of the 2000-01-06 new moon
_NAMES = (
    "new",
    "waxing crescent",
    "first quarter",
    "waxing gibbous",
    "full",
    "waning gibbous",
    "last quarter",
    "waning crescent",
)


def _julian_day(year, month, day):
    if month <= 2:
        year -= 1
        month += 12
    a = year // 100
    b = 2 - a + a // 4
    return int(365.25 * (year + 4716)) + int(30.6001 * (month + 1)) + day + b - 1524.5


def phase_fraction(year, month, day):
    """Position in the lunar cycle, 0.0 (new) .. ~0.5 (full) .. 1.0 (new again)."""
    days = _julian_day(year, month, day) - _REF_NEW_MOON_JD
    return (days / _SYNODIC) % 1.0


def moon(year, month, day):
    """Return {phase: 0-7, name: str, illum: 0..1} for the date."""
    frac = phase_fraction(year, month, day)
    illum = (1.0 - math.cos(2.0 * math.pi * frac)) / 2.0
    phase = int(round(frac * 8)) % 8
    return {"phase": phase, "name": _NAMES[phase], "illum": round(illum, 3)}
```

- [ ] **Step 4: Run** `cd server && ../.venv/bin/python -m pytest tests/test_moon.py -v` — expect PASS.

- [ ] **Step 5: Lint/format** `.venv/bin/ruff check server/app/moon.py server/tests/test_moon.py && .venv/bin/black server/app/moon.py server/tests/test_moon.py`

- [ ] **Step 6: Commit**
```bash
git add server/app/moon.py server/tests/test_moon.py
git commit -m "feat: pure moon-phase computation"
```

---

## Task S3: `server/app/weather.py` — Open-Meteo fetch + normalize

**Files:** Create `server/app/weather.py`; Test `server/tests/test_weather.py`

- [ ] **Step 1: Write the failing tests** — `server/tests/test_weather.py`:
```python
from app.weather import normalize

# Minimal Open-Meteo-shaped payloads.
def _payload(temp, humidity, precip, precip_prob, sunset="2026-06-18T19:42"):
    return {
        "current": {
            "temperature_2m": temp,
            "relative_humidity_2m": humidity,
            "precipitation": precip,
            "weather_code": 0,
            "time": "2026-06-18T15:00",
        },
        "daily": {"precipitation_probability_max": [precip_prob], "sunset": [sunset]},
    }


def test_extreme_heat_tag():
    out = normalize(_payload(43, 10, 0, 0), now_iso="2026-06-18T15:00")
    assert "extreme_heat" in out["tags"]
    assert out["temp_c"] == 43


def test_storm_incoming_on_high_precip_probability():
    out = normalize(_payload(30, 60, 0, 80), now_iso="2026-06-18T15:00")
    assert "storm_incoming" in out["tags"]


def test_rain_when_currently_precipitating():
    out = normalize(_payload(24, 80, 1.2, 90), now_iso="2026-06-18T15:00")
    assert "rain" in out["tags"]


def test_cold_tag():
    out = normalize(_payload(2, 40, 0, 0), now_iso="2026-01-05T07:00")
    assert "cold" in out["tags"]


def test_clear_default():
    out = normalize(_payload(28, 15, 0, 5), now_iso="2026-06-18T11:00")
    assert out["tags"] == ["clear"]


def test_sunset_soon_flag():
    out = normalize(_payload(35, 15, 0, 0, sunset="2026-06-18T19:42"), now_iso="2026-06-18T19:20")
    assert out["sunset_soon"] is True
    out2 = normalize(_payload(35, 15, 0, 0, sunset="2026-06-18T19:42"), now_iso="2026-06-18T12:00")
    assert out2["sunset_soon"] is False
```

- [ ] **Step 2: Run** `cd server && ../.venv/bin/python -m pytest tests/test_weather.py -v` — expect FAIL (no module).

- [ ] **Step 3: Implement `server/app/weather.py`**
```python
"""Open-Meteo fetch + normalization to desert 'feeling' tags."""
from datetime import datetime

from .config import LAT, LON, TZ

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

_EXTREME_HEAT_C = 40.0
_COLD_C = 5.0
_HIGH_PRECIP_PROB = 70
_STORM_PRECIP_PROB = 60
_MONSOON_HUMIDITY = 50
_SUNSET_WINDOW_MIN = 30


def fetch_raw(client):
    """Fetch current + daily weather for the configured location. `client` is an httpx.Client."""
    params = {
        "latitude": LAT,
        "longitude": LON,
        "timezone": TZ,
        "current": "temperature_2m,relative_humidity_2m,precipitation,weather_code",
        "daily": "precipitation_probability_max,sunset",
        "forecast_days": 1,
    }
    resp = client.get(OPEN_METEO_URL, params=params)
    resp.raise_for_status()
    return resp.json()


def _minutes(iso):
    """Minutes-since-midnight from an ISO 'YYYY-MM-DDTHH:MM' string."""
    t = datetime.fromisoformat(iso)
    return t.hour * 60 + t.minute


def normalize(data, now_iso):
    """Map an Open-Meteo payload to {tags, temp_c, code, sunset_soon}. Pure."""
    cur = data.get("current", {})
    daily = data.get("daily", {})
    temp = cur.get("temperature_2m")
    humidity = cur.get("relative_humidity_2m", 0)
    precip = cur.get("precipitation", 0) or 0
    prob_list = daily.get("precipitation_probability_max") or [0]
    prob = prob_list[0] or 0
    month = datetime.fromisoformat(now_iso).month

    tags = []
    if temp is not None and temp >= _EXTREME_HEAT_C:
        tags.append("extreme_heat")
    if temp is not None and temp <= _COLD_C:
        tags.append("cold")
    if precip > 0:
        tags.append("rain")
    if prob >= _STORM_PRECIP_PROB and "rain" not in tags:
        tags.append("storm_incoming")
    if 6 <= month <= 9 and humidity >= _MONSOON_HUMIDITY and prob >= _STORM_PRECIP_PROB:
        tags.append("monsoon")
    if not tags:
        tags.append("clear")

    sunset_soon = False
    sunset_list = daily.get("sunset") or []
    if sunset_list:
        delta = _minutes(sunset_list[0]) - _minutes(now_iso)
        sunset_soon = 0 <= delta <= _SUNSET_WINDOW_MIN

    return {
        "tags": tags,
        "temp_c": temp,
        "code": cur.get("weather_code", 0),
        "sunset_soon": sunset_soon,
    }
```

- [ ] **Step 4: Run** `cd server && ../.venv/bin/python -m pytest tests/test_weather.py -v` — expect PASS.

- [ ] **Step 5: Lint/format** `.venv/bin/ruff check server/app/weather.py server/tests/test_weather.py && .venv/bin/black server/app/weather.py server/tests/test_weather.py`

- [ ] **Step 6: Commit**
```bash
git add server/app/weather.py server/tests/test_weather.py
git commit -m "feat: Open-Meteo weather fetch and desert tag normalization"
```

---

## Task S4: `server/app/oracle.py` — assemble payload

**Files:** Create `server/app/oracle.py`; Test `server/tests/test_oracle.py`

- [ ] **Step 1: Write the failing tests** — `server/tests/test_oracle.py`:
```python
from app.oracle import build


def test_build_shapes_payload():
    weather = {"tags": ["extreme_heat"], "temp_c": 43, "code": 0, "sunset_soon": False}
    mooninfo = {"phase": 4, "name": "full", "illum": 0.98}
    out = build(weather, mooninfo, ts=1718900000)
    assert out["weather"]["tags"] == ["extreme_heat"]
    assert out["moon"]["phase"] == 4
    assert out["ts"] == 1718900000
```

- [ ] **Step 2: Run** `cd server && ../.venv/bin/python -m pytest tests/test_oracle.py -v` — expect FAIL.

- [ ] **Step 3: Implement `server/app/oracle.py`**
```python
"""Assemble the /oracle payload from weather + moon."""


def build(weather, moon, ts):
    """Return the compact oracle payload served to the device."""
    return {"weather": weather, "moon": moon, "ts": ts}
```

- [ ] **Step 4: Run** `cd server && ../.venv/bin/python -m pytest tests/test_oracle.py -v` — expect PASS.

- [ ] **Step 5: Lint/format** `.venv/bin/ruff check server/app/oracle.py server/tests/test_oracle.py && .venv/bin/black server/app/oracle.py server/tests/test_oracle.py`

- [ ] **Step 6: Commit**
```bash
git add server/app/oracle.py server/tests/test_oracle.py
git commit -m "feat: assemble oracle payload"
```

---

## Task S5: `server/app/main.py` — FastAPI endpoints + auth

**Files:** Create `server/app/main.py`; Test `server/tests/test_main.py`

- [ ] **Step 1: Write the failing tests** — `server/tests/test_main.py`:
```python
import app.main as main_mod
from fastapi.testclient import TestClient

SAMPLE = {
    "current": {
        "temperature_2m": 43,
        "relative_humidity_2m": 10,
        "precipitation": 0,
        "weather_code": 0,
        "time": "2026-06-18T15:00",
    },
    "daily": {"precipitation_probability_max": [0], "sunset": ["2026-06-18T19:42"]},
}


def _client(monkeypatch, fetch=None):
    if fetch is None:
        def fetch(_client):
            return SAMPLE
    monkeypatch.setattr(main_mod.weather, "fetch_raw", fetch)
    return TestClient(main_mod.app)


def test_health(monkeypatch):
    assert _client(monkeypatch).get("/health").json() == {"ok": True}


def test_oracle_returns_weather_and_moon(monkeypatch):
    r = _client(monkeypatch).get("/oracle")
    assert r.status_code == 200
    body = r.json()
    assert "extreme_heat" in body["weather"]["tags"]
    assert 0 <= body["moon"]["phase"] <= 7
    assert "ts" in body


def test_oracle_degrades_to_moon_only_on_weather_failure(monkeypatch):
    def boom(_client):
        raise RuntimeError("open-meteo down")

    body = _client(monkeypatch, fetch=boom).get("/oracle").json()
    assert body["weather"]["tags"] == []
    assert 0 <= body["moon"]["phase"] <= 7


def test_oracle_requires_token_when_configured(monkeypatch):
    monkeypatch.setattr(main_mod.config, "ORACLE_TOKEN", "sekret")
    c = _client(monkeypatch)
    assert c.get("/oracle").status_code == 401
    assert c.get("/oracle", headers={"Authorization": "Bearer sekret"}).status_code == 200
```

- [ ] **Step 2: Run** `cd server && ../.venv/bin/python -m pytest tests/test_main.py -v` — expect FAIL (no module).

- [ ] **Step 3: Implement `server/app/main.py`**
```python
"""FastAPI home oracle: GET /oracle (weather + moon), GET /health."""
import time
from datetime import datetime

import httpx
from fastapi import FastAPI, Header, HTTPException

from . import config, moon, oracle, weather

app = FastAPI(title="Slime Oracle")


def _check_auth(authorization):
    token = config.ORACLE_TOKEN
    if not token:
        return
    if authorization != "Bearer " + token:
        raise HTTPException(status_code=401, detail="bad token")


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/oracle")
def get_oracle(authorization: str = Header(default="")):
    _check_auth(authorization)
    now = datetime.now()
    mooninfo = moon.moon(now.year, now.month, now.day)
    try:
        with httpx.Client(timeout=10) as client:
            raw = weather.fetch_raw(client)
        w = weather.normalize(raw, now_iso=now.isoformat(timespec="minutes"))
    except Exception:
        w = {"tags": [], "temp_c": None, "code": 0, "sunset_soon": False}
    return oracle.build(w, mooninfo, ts=int(time.time()))
```

- [ ] **Step 4: Run** `cd server && ../.venv/bin/python -m pytest tests/test_main.py -v` — expect PASS.

- [ ] **Step 5: Full server suite** `cd server && ../.venv/bin/python -m pytest -q` — expect all pass.

- [ ] **Step 6: Lint/format** `.venv/bin/ruff check server/app/main.py server/tests/test_main.py && .venv/bin/black server/app/main.py server/tests/test_main.py`

- [ ] **Step 7: Commit**
```bash
git add server/app/main.py server/tests/test_main.py
git commit -m "feat: FastAPI /oracle and /health endpoints with optional bearer auth"
```

---

## Task S6: Docker packaging + local run

**Files:** Create `server/Dockerfile`, `server/docker-compose.yml`

- [ ] **Step 1: Create `server/Dockerfile`**
```dockerfile
FROM python:3.12-slim
WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
EXPOSE 8080
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
```

- [ ] **Step 2: Create `server/docker-compose.yml`**
```yaml
services:
  oracle:
    build: .
    image: slime-oracle:latest
    container_name: slime-oracle
    restart: unless-stopped
    ports:
      - "8080:8080"
    environment:
      SLIME_LAT: "33.4484"
      SLIME_LON: "-112.0740"
      SLIME_TZ: "America/Phoenix"
      # ORACLE_TOKEN: "set-a-shared-token-to-require-auth"
```

- [ ] **Step 3: Run it locally and curl** (host has Docker):
```bash
cd server && docker compose up -d --build
sleep 3
curl -s localhost:8080/health
curl -s localhost:8080/oracle
```
Expected: `{"ok":true}` and a JSON `/oracle` body with `weather` (real Phoenix tags) + `moon` + `ts`.

- [ ] **Step 4: Tear down** `cd server && docker compose down`

- [ ] **Step 5: Commit**
```bash
git add server/Dockerfile server/docker-compose.yml
git commit -m "feat: Dockerize the home oracle service"
```

---

## Task S7: Extend CI with a server job

**Files:** Modify `.github/workflows/ci.yml`

- [ ] **Step 1: Add a second job to `.github/workflows/ci.yml`** (append under `jobs:`, keeping the
  existing `check` job unchanged):
```yaml
  server:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: server
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Install
        run: pip install -r requirements.txt pytest "ruff==0.15.17" "black==26.5.1"
      - name: Lint
        run: ruff check . && black --check .
      - name: Tests
        run: pytest
```

- [ ] **Step 2: Validate YAML locally** `.venv/bin/python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"` — expect no error (install pyyaml first if needed: `.venv/bin/pip install pyyaml`).

- [ ] **Step 3: Commit**
```bash
git add .github/workflows/ci.yml
git commit -m "ci: add server test+lint job"
```

---

# TIER 2 — MAGTAG CLIENT

## Task C1: Weather form frames + moon accent index

**Files:** Modify `slime/visuals.py`; Modify `tests/test_visuals.py`

- [ ] **Step 1: Add to `POSE_INDEX` in `slime/visuals.py`** (after `"winter_form": 15,`):
```python
    "melting": 16,
    "hiding": 17,
```
  And add below `POSE_INDEX`:
```python
ACCENT_MOON = 4  # frame index of the moon accent in accents.bmp
```

- [ ] **Step 2: Add the failing test** — append to `tests/test_visuals.py`:
```python
def test_weather_and_moon_frame_indices():
    assert POSE_INDEX["melting"] == 16
    assert POSE_INDEX["hiding"] == 17
    from slime.visuals import ACCENT_MOON

    assert ACCENT_MOON == 4
```

- [ ] **Step 3: Run** `.venv/bin/python -m pytest tests/test_visuals.py -v` — expect FAIL then (after Step 1 done) PASS. Run to confirm PASS.

- [ ] **Step 4: Lint/format** `.venv/bin/ruff check slime/visuals.py tests/test_visuals.py && .venv/bin/black slime/visuals.py tests/test_visuals.py`

- [ ] **Step 5: Commit**
```bash
git add slime/visuals.py tests/test_visuals.py
git commit -m "feat: add weather form frames and moon accent index"
```

---

## Task C2: `slime/oracle.py` — parse, effects, NVM cache (PURE)

**Files:** Create `slime/oracle.py`; Test `tests/test_oracle_client.py`

- [ ] **Step 1: Write the failing tests** — `tests/test_oracle_client.py`:
```python
from slime.state import Mood
from slime.oracle import (
    Oracle, dream_refs, form_override, mood_bias, pack, parse, quip_tag, unpack,
)


def _payload(tags, phase=4, illum=0.98, sunset=False, temp=43.0):
    return {
        "weather": {"tags": tags, "temp_c": temp, "sunset_soon": sunset},
        "moon": {"phase": phase, "illum": illum},
    }


def test_parse_picks_dominant_tag_by_priority():
    o = parse(_payload(["clear", "storm_incoming"]))
    assert o.weather_tag == "storm_incoming"  # storm outranks clear


def test_parse_handles_missing_payload():
    assert parse(None) is None
    assert parse({}) is not None  # tolerant: empty -> clear/none


def test_form_override():
    assert form_override(parse(_payload(["extreme_heat"]))) == "melting"
    assert form_override(parse(_payload(["storm_incoming"]))) == "hiding"
    assert form_override(parse(_payload(["clear"]))) is None


def test_quip_tag():
    assert quip_tag(parse(_payload(["rain"]))) == "rain"
    assert quip_tag(parse(_payload(["clear"], phase=4))) == "full_moon"
    assert quip_tag(parse(_payload(["clear"], phase=0))) == "new_moon"
    assert quip_tag(parse(_payload(["clear"], phase=2))) is None


def test_mood_bias_extreme_heat_drains_energy():
    o = parse(_payload(["extreme_heat"]))
    biased = mood_bias(Mood(80, 60, 50, 30, 40), o)
    assert biased.energy < 80


def test_dream_refs_full_moon():
    refs = dream_refs(parse(_payload(["clear"], phase=4)))
    assert any("moon" in r for r in refs)


def test_cache_roundtrip():
    o = parse(_payload(["storm_incoming"], phase=4, illum=0.98, sunset=True, temp=30.0))
    o2 = unpack(pack(o))
    assert o2.weather_tag == "storm_incoming"
    assert o2.moon_phase == 4
    assert o2.sunset_soon is True
```

- [ ] **Step 2: Run** `.venv/bin/python -m pytest tests/test_oracle_client.py -v` — expect FAIL (no module).

- [ ] **Step 3: Implement `slime/oracle.py`**
```python
"""Pure oracle parsing + behavioral effects + NVM cache. Device save/load import lazily."""
import struct
from collections import namedtuple

from slime.state import MOOD_FIELDS, Mood, clamp_mood

Oracle = namedtuple("Oracle", ("weather_tag", "temp_c", "moon_phase", "moon_illum", "sunset_soon"))

# Single dominant weather tag, highest priority first.
_TAG_PRIORITY = ("storm_incoming", "extreme_heat", "rain", "monsoon", "cold", "clear")
_TAG_IDS = ("clear", "storm_incoming", "extreme_heat", "rain", "monsoon", "cold")

# Gentle mood targets per weather tag (seasonal-style nudge).
_WEATHER_TARGETS = {
    "storm_incoming": {"comfort": 80.0, "sleepiness": 55.0},  # cozy, hiding
    "extreme_heat": {"energy": 20.0},                         # drained, melting
    "rain": {"curiosity": 75.0, "energy": 65.0},              # excited
    "cold": {"comfort": 70.0},
}
_FORM = {"extreme_heat": "melting", "storm_incoming": "hiding"}
_QUIP = {"extreme_heat": "heat", "rain": "rain", "storm_incoming": "storm", "monsoon": "storm"}


def parse(payload):
    """Map an /oracle dict to an Oracle, or None if there's nothing usable."""
    if payload is None:
        return None
    w = payload.get("weather", {})
    m = payload.get("moon", {})
    tags = w.get("tags", []) or []
    tag = "clear"
    for candidate in _TAG_PRIORITY:
        if candidate in tags:
            tag = candidate
            break
    return Oracle(
        weather_tag=tag,
        temp_c=w.get("temp_c"),
        moon_phase=m.get("phase", 0),
        moon_illum=m.get("illum", 0.0),
        sunset_soon=bool(w.get("sunset_soon", False)),
    )


def mood_bias(mood, oracle, rate=0.05):
    """Nudge mood toward the weather's tendency + a small full-moon dreaminess. New Mood."""
    if oracle is None:
        return mood
    vals = {field: getattr(mood, field) for field in MOOD_FIELDS}
    for drive, target in _WEATHER_TARGETS.get(oracle.weather_tag, {}).items():
        vals[drive] += (target - vals[drive]) * rate
    if oracle.sunset_soon:
        vals["affection"] += (70.0 - vals["affection"]) * rate  # admiring
    if oracle.moon_phase == 4:
        vals["curiosity"] += (65.0 - vals["curiosity"]) * rate  # dreamy
    return clamp_mood(Mood(**vals))


def form_override(oracle):
    """Weather form name (melting/hiding) or None."""
    if oracle is None:
        return None
    return _FORM.get(oracle.weather_tag)


def quip_tag(oracle):
    """Weather/moon quip pool tag, or None."""
    if oracle is None:
        return None
    if oracle.weather_tag in _QUIP:
        return _QUIP[oracle.weather_tag]
    if oracle.sunset_soon:
        return "sunset"
    if oracle.moon_phase == 4:
        return "full_moon"
    if oracle.moon_phase == 0:
        return "new_moon"
    return None


def dream_refs(oracle):
    """Lore fragments to weave into dreams from weather/moon."""
    if oracle is None:
        return ()
    refs = []
    if oracle.moon_phase == 4:
        refs.append("beneath the full moon")
    elif oracle.moon_phase == 0:
        refs.append("under a dark new-moon sky")
    if oracle.weather_tag == "extreme_heat":
        refs.append("the desert stayed warm")
    elif oracle.weather_tag in ("rain", "storm_incoming", "monsoon"):
        refs.append("rain was coming")
    return tuple(refs)


_FMT = "<BBBff"  # tag_id, moon_phase, sunset, temp_c, moon_illum
SIZE = struct.calcsize(_FMT)


def pack(oracle):
    tag_id = _TAG_IDS.index(oracle.weather_tag) if oracle.weather_tag in _TAG_IDS else 0
    temp = oracle.temp_c if oracle.temp_c is not None else -999.0
    return struct.pack(_FMT, tag_id, oracle.moon_phase, 1 if oracle.sunset_soon else 0,
                       temp, oracle.moon_illum)


def unpack(blob):
    tag_id, phase, sunset, temp, illum = struct.unpack(_FMT, blob[:SIZE])
    return Oracle(
        weather_tag=_TAG_IDS[tag_id] if tag_id < len(_TAG_IDS) else "clear",
        temp_c=None if temp < -900.0 else temp,
        moon_phase=phase,
        moon_illum=illum,
        sunset_soon=bool(sunset),
    )


_NVM_OFFSET = 512  # a fixed slot safely past the journal ring (state + journal end well before this)


def save_cache(oracle):
    """Persist the oracle to its NVM slot. Device-only."""
    import microcontroller

    microcontroller.nvm[_NVM_OFFSET:_NVM_OFFSET + SIZE] = pack(oracle)


def load_cache():
    """Read the cached oracle from NVM, or None if absent/invalid. Device-only."""
    import microcontroller

    try:
        blob = bytes(microcontroller.nvm[_NVM_OFFSET:_NVM_OFFSET + SIZE])
        o = unpack(blob)
        if o.moon_phase > 7:  # uninitialized/garbage sanity check
            return None
        return o
    except Exception:
        return None
```

- [ ] **Step 4: Run** `.venv/bin/python -m pytest tests/test_oracle_client.py -v` — expect PASS.

- [ ] **Step 5: Confirm host import clean** `.venv/bin/python -c "import slime.oracle"` (no module-level
  `microcontroller`).

- [ ] **Step 6: Lint/format** `.venv/bin/ruff check slime/oracle.py tests/test_oracle_client.py && .venv/bin/black slime/oracle.py tests/test_oracle_client.py`

- [ ] **Step 7: Commit**
```bash
git add slime/oracle.py tests/test_oracle_client.py
git commit -m "feat: pure oracle parse/effects/cache for the device"
```

---

## Task C3: `forms.choose_render` gains `weather`

**Files:** Modify `slime/forms.py`; Modify `tests/test_forms.py`

- [ ] **Step 1: Add the failing tests** — append to `tests/test_forms.py`:
```python
def test_weather_form_overrides_mood_face():
    calm = Mood(60, 80, 50, 30, 40)
    assert choose_render(calm, tier=4, sleeping=False, weather="melting") == POSE_INDEX["melting"]
    assert choose_render(calm, tier=4, sleeping=False, weather="hiding") == POSE_INDEX["hiding"]


def test_sleep_still_wins_over_weather():
    sleepy = Mood(50, 60, 40, 90, 40)
    assert choose_render(sleepy, tier=4, sleeping=True, weather="melting") == POSE_INDEX["loaf"]
```

- [ ] **Step 2: Run** `.venv/bin/python -m pytest tests/test_forms.py -v` — expect FAIL.

- [ ] **Step 3: Modify `slime/forms.py`** — add the `weather` parameter and a branch just below the
  `loaf` check. Replace the function with:
```python
def choose_render(mood, tier, sleeping, season=None, weather=None):
    """Return the sprite frame index to display, in priority order."""
    forms_ok = unlocked_forms(tier)

    if sleeping or mood.sleepiness >= 85.0:
        return POSE_INDEX["loaf"]
    if weather == "melting":
        return POSE_INDEX["melting"]
    if weather == "hiding":
        return POSE_INDEX["hiding"]
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
        return form_frame(season)
    return POSE_INDEX[expression]
```

- [ ] **Step 4: Run** `.venv/bin/python -m pytest tests/test_forms.py -v` — expect PASS.

- [ ] **Step 5: Lint/format** `.venv/bin/ruff check slime/forms.py tests/test_forms.py && .venv/bin/black slime/forms.py tests/test_forms.py`

- [ ] **Step 6: Commit**
```bash
git add slime/forms.py tests/test_forms.py
git commit -m "feat: weather form override in forms.choose_render"
```

---

## Task C4: Weather/moon quip pools (PURE)

**Files:** Modify `slime/quips.py`; Modify `tests/test_quips.py`

- [ ] **Step 1: Add the failing test** — append to `tests/test_quips.py`:
```python
def test_weather_moon_quip_pools_exist():
    for tag in ("heat", "rain", "storm", "sunset", "full_moon", "new_moon"):
        assert tag in QUIPS
        assert len(QUIPS[tag]) >= 2
```

- [ ] **Step 2: Run** `.venv/bin/python -m pytest tests/test_quips.py -v` — expect FAIL.

- [ ] **Step 3: Add these entries to the `QUIPS` dict in `slime/quips.py`**:
```python
    "heat": (
        "the air shimmers",
        "i am melting, slowly",
        "too warm to move",
    ),
    "rain": (
        "i smell the rain",
        "everything drinks",
        "petrichor",
    ),
    "storm": (
        "something is coming",
        "i will hide a while",
        "the sky feels heavy",
    ),
    "sunset": (
        "look at that light",
        "the day bows out",
        "gold on everything",
    ),
    "full_moon": (
        "the moon is full tonight",
        "bright even with eyes closed",
        "a night for wandering dreams",
    ),
    "new_moon": (
        "the sky is deep and dark",
        "the moon is hiding too",
        "quiet under no moon",
    ),
```

- [ ] **Step 4: Run** `.venv/bin/python -m pytest tests/test_quips.py -v` — expect PASS.

- [ ] **Step 5: Lint/format** `.venv/bin/ruff check slime/quips.py tests/test_quips.py && .venv/bin/black slime/quips.py tests/test_quips.py`

- [ ] **Step 6: Commit**
```bash
git add slime/quips.py tests/test_quips.py
git commit -m "feat: add weather and moon quip pools"
```

---

## Task C5: `dreams.generate` accepts extra refs (PURE)

**Files:** Modify `slime/dreams.py`; Modify `tests/test_dreams.py`

- [ ] **Step 1: Add the failing test** — append to `tests/test_dreams.py`:
```python
def test_generate_weaves_extra_ref_when_provided():
    line, _ = generate(tier=0, artifacts_mask=0, choice=lambda s: s[0],
                       extra_refs=("beneath the full moon",))
    assert "beneath the full moon" in line
```

- [ ] **Step 2: Run** `.venv/bin/python -m pytest tests/test_dreams.py -v` — expect FAIL (unexpected kwarg).

- [ ] **Step 3: Modify `generate` in `slime/dreams.py`** to accept `extra_refs=()` and weave one in.
  Change the signature and append a chosen extra ref before the artifact logic:
```python
def generate(tier, artifacts_mask, choice, extra_refs=()):
    """Assemble one dream line and maybe an artifact id. `choice(seq)` picks from a sequence."""
    line = choice(_ACTS) + " " + choice(_PLACES) + "."
    if tier >= 2:
        line += " " + choice(_PERSONAL) + "."
    if extra_refs:
        line += " " + choice(tuple(extra_refs)) + "."

    artifact_id = None
    if choice((True, False, False, False)):
        uncollected = [i for i in range(len(ARTIFACTS)) if not has_artifact(artifacts_mask, i)]
        if uncollected:
            artifact_id = choice(uncollected)
    return line, artifact_id
```

- [ ] **Step 4: Run** `.venv/bin/python -m pytest tests/test_dreams.py -v` — expect PASS.

- [ ] **Step 5: Lint/format** `.venv/bin/ruff check slime/dreams.py tests/test_dreams.py && .venv/bin/black slime/dreams.py tests/test_dreams.py`

- [ ] **Step 6: Commit**
```bash
git add slime/dreams.py tests/test_dreams.py
git commit -m "feat: dreams.generate can weave weather/moon refs"
```

---

## Task C6: Weather forms + moon accent assets

**Files:** Modify `assets/make_assets.py`; regenerate `assets/slime.bmp`, `assets/accents.bmp`

- [ ] **Step 1: Read `assets/make_assets.py`** to confirm helper signatures (`_blob`, `_eyes`).

- [ ] **Step 2: Add the weather forms to `POSES`** (after `"winter_form"`):
```python
    "melting", "hiding",
```

- [ ] **Step 3: Add these branches in `draw_pose` before the final `else:  # content`**:
```python
    elif pose == "melting":
        d.rectangle([ox + 12, 40, ox + 52, 58], fill=BLACK)
        d.rectangle([ox + 14, 42, ox + 50, 56], fill=GRAY)
        d.rectangle([ox + 20, 56, ox + 24, 62], fill=GRAY)  # drips
        d.rectangle([ox + 40, 56, ox + 44, 62], fill=GRAY)
        d.rectangle([ox + 26, 48, ox + 32, 51], fill=BLACK)
        d.rectangle([ox + 36, 48, ox + 42, 51], fill=BLACK)
    elif pose == "hiding":
        d.rectangle([ox + 16, 30, ox + 48, 58], fill=BLACK)
        d.rectangle([ox + 18, 32, ox + 46, 56], fill=GRAY)
        d.rectangle([ox + 22, 44, ox + 42, 50], fill=BLACK)  # peeking slit
        d.rectangle([ox + 28, 46, ox + 32, 49], fill=GRAY)
        d.rectangle([ox + 34, 46, ox + 38, 49], fill=GRAY)
```

- [ ] **Step 4: Add a moon accent (frame 4) to the accents sheet.** In `main()`, change the accents
  image width to 5 frames and draw the moon. Replace the `accents = Image.new(...)` line with:
```python
    accents = Image.new("P", (28 * 5, 28), WHITE)
```
  and add, just before `accents.save("assets/accents.bmp")`:
```python
    # frame 4: moon (a crescent: full disc minus an offset disc)
    ad.ellipse([112 + 6, 4, 112 + 22, 20], fill=GRAY, outline=BLACK)
    ad.ellipse([112 + 11, 2, 112 + 27, 18], fill=WHITE)
```
  and update its print line:
```python
    print("wrote assets/accents.bmp (%dx%d, 5 frames)" % (accents.width, accents.height))
```

- [ ] **Step 5: Regenerate** `.venv/bin/python assets/make_assets.py` — expect
  `wrote assets/slime.bmp (1152x64, 18 frames)` and `wrote assets/accents.bmp (140x28, 5 frames)`.

- [ ] **Step 6: Verify** `.venv/bin/python -c "from PIL import Image; print(Image.open('assets/slime.bmp').size, Image.open('assets/accents.bmp').size)"` — expect `(1152, 64) (140, 28)`.

- [ ] **Step 7: Lint/format** `.venv/bin/ruff check assets/make_assets.py && .venv/bin/black assets/make_assets.py`

- [ ] **Step 8: Commit**
```bash
git add assets/make_assets.py assets/slime.bmp assets/accents.bmp
git commit -m "feat: add melting/hiding weather forms and a moon accent"
```

---

## Task C7: `slime/netoracle.py` — HTTP adapter (DEVICE)

**Files:** Create `slime/netoracle.py`

- [ ] **Step 1: Implement `slime/netoracle.py`**
```python
"""Hardware adapter: fetch /oracle over WiFi. Device-only. Never raises into the loop.

Assumes WiFi is already connected (nettime.sync connects it at boot). ORACLE_HOST is the
Pi's mDNS name or IP:port from settings.toml, e.g. "slime-oracle.local:8080" or "192.168.0.50:8080".
"""
import os


def fetch():
    """GET http://<ORACLE_HOST>/oracle. Returns the parsed dict, or None on any failure."""
    try:
        import adafruit_requests
        import socketpool
        import ssl
        import wifi

        host = os.getenv("ORACLE_HOST")
        if not host:
            return None
        pool = socketpool.SocketPool(wifi.radio)
        session = adafruit_requests.Session(pool, ssl.create_default_context())
        headers = {}
        token = os.getenv("ORACLE_TOKEN")
        if token:
            headers["Authorization"] = "Bearer " + token
        resp = session.get("http://" + host + "/oracle", headers=headers, timeout=10)
        data = resp.json()
        resp.close()
        return data
    except Exception:
        return None
```

- [ ] **Step 2: Verify host import** `.venv/bin/python -c "import slime.netoracle"` — succeeds
  (`os` only at module level).

- [ ] **Step 3: Lint/format** `.venv/bin/ruff check slime/netoracle.py && .venv/bin/black slime/netoracle.py`

- [ ] **Step 4: Commit**
```bash
git add slime/netoracle.py
git commit -m "feat: add WiFi oracle HTTP adapter"
```

---

## Task C8: Integrate the oracle in `code.py` (DEVICE)

**Files:** Modify `code.py`

- [ ] **Step 1: Add imports** at the top of `code.py` (with the other `from slime import ...`):
```python
from slime import netoracle, oracle as oracle_mod
from slime.visuals import ACCENT_MOON
```

- [ ] **Step 2: Add an oracle bootstrap** helper near the other helpers:
```python
def _load_oracle(on_usb):
    """Fetch the oracle on USB (and cache it); otherwise use the cached one. Returns Oracle|None."""
    if on_usb:
        payload = netoracle.fetch()
        parsed = oracle_mod.parse(payload)
        if parsed is not None:
            oracle_mod.save_cache(parsed)
            return parsed
    return oracle_mod.load_cache()
```

- [ ] **Step 3: In `main()`**, after the `season = _current_season(...)` block (and its
  `apply_bias`), load the oracle and apply its bias. Insert:
```python
    on_usb_now = sensors.on_usb() if sensors else True
    oracle = _load_oracle(on_usb_now)
    if oracle is not None:
        state = evolve(state, mood=oracle_mod.mood_bias(state.mood, oracle))
    weather_form = oracle_mod.form_override(oracle)
```

- [ ] **Step 4: Thread weather into rendering.** Change `_render_frame` to take and use the oracle:
```python
def _render_frame(display, state, season=None, weather=None, oracle=None):
    """Render the current form (+ seasonal/moon accent) and a quip. Returns updated state."""
    if not display:
        return state
    sleeping = state.mood.sleepiness >= _SLEEPY_FRAME
    ftier = friendship.tier(state.familiarity)
    frame = choose_render(state.mood, ftier, sleeping, season=season, weather=weather)
    # Quip: weather/moon voice first, then bonded, then expression.
    otag = oracle_mod.quip_tag(oracle) if oracle is not None else None
    tag = otag or ("bonded" if ftier >= 3 else state.expression)
    quip = pick(tag) or pick(state.expression)
    # Accent: a notable moon takes the corner, else the season.
    if oracle is not None and oracle.moon_phase in (0, 4):
        accent = ACCENT_MOON
    else:
        accent = seasons.accent_frame(season) if season else None
    try:
        display.render_frame(frame, quip or "", accent_index=accent)
        state = evolve(state, last_seen=time.monotonic())
    except Exception:
        pass
    return state
```
  Update BOTH `_render_frame(display, state, season)` call sites to
  `_render_frame(display, state, season, weather_form, oracle)`.

- [ ] **Step 5: Feed oracle refs into the wake dream.** Change the `_dream_on_wake` signature to
  accept the oracle and pass its refs to `dreams.generate`:
```python
def _dream_on_wake(display, sound, state, oracle=None):
    """Generate and show a dream + maybe an artifact. Returns updated state."""
    fam_tier = friendship.tier(state.familiarity)
    refs = oracle_mod.dream_refs(oracle) if oracle is not None else ()
    line, artifact_id = dreams.generate(fam_tier, state.artifacts, _choice, extra_refs=refs)
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
```
  Update the `_dream_on_wake(display, sound, state)` call site to
  `_dream_on_wake(display, sound, state, oracle)`. (The oracle must be loaded before that call —
  ensure Step 3's oracle block runs before the `woke_deep` dream block; move the oracle block above
  the `woke_deep = power.woke_from_deep_sleep()` line if needed.)

- [ ] **Step 6: Apply oracle bias in the continuous loop too.** In the loop's `if events:` block,
  right after the seasonal `apply_bias` line, add:
```python
                if oracle is not None:
                    state = evolve(state, mood=oracle_mod.mood_bias(state.mood, oracle))
```

- [ ] **Step 7: Syntax check** `.venv/bin/python -m py_compile code.py` — expect no output.

- [ ] **Step 8: Confirm host suite unaffected** `.venv/bin/python -m pytest -q` — expect all pass
  (the `_replace` guard scans `code.py`).

- [ ] **Step 9: Lint/format** `.venv/bin/ruff check code.py && .venv/bin/black --check code.py`

- [ ] **Step 10: Commit**
```bash
git add code.py
git commit -m "feat: fetch/cache the oracle and apply weather/moon effects in code.py"
```

---

## Task C9: On-device bring-up & verification

**Files:** none (deploy + verify only)

- [ ] **Step 1: Run the oracle server reachable from the LAN** (on the Pi, or locally for the test):
  `cd server && docker compose up -d --build`, and confirm `curl http://<host>:8080/oracle` works.

- [ ] **Step 2: Configure the device.** Add to `/Volumes/CIRCUITPY/settings.toml`:
```toml
ORACLE_HOST = "192.168.0.50:8080"   # or "slime-oracle.local:8080"
# ORACLE_TOKEN = "..."              # only if the server sets ORACLE_TOKEN
```

- [ ] **Step 3: Install the HTTP lib + deploy**:
```bash
.venv/bin/circup --path /Volumes/CIRCUITPY install adafruit_requests
cp slime/*.py /Volumes/CIRCUITPY/slime/
cp assets/slime.bmp assets/accents.bmp /Volumes/CIRCUITPY/assets/
cp code.py /Volumes/CIRCUITPY/
rm -rf /Volumes/CIRCUITPY/slime/__pycache__
sync
```

- [ ] **Step 4: Confirm a clean run** over serial (soft-reboot, no traceback; "Wi-Fi: <IP>" then
  silent loop).

- [ ] **Step 5: Verify Phase 2a success criteria:**
  1. [ ] REPL: `from slime import netoracle, oracle; print(oracle.parse(netoracle.fetch()))` returns
     an `Oracle(...)` with the current weather tag + moon phase (WiFi must be connected).
  2. [ ] Offline cache: with the server stopped, `from slime import oracle; print(oracle.load_cache())`
     returns the last cached Oracle (not None) and the slime still runs.
  3. [ ] Effect visible: in real weather, the panel shows the matching form/quip (e.g. `melting` +
     "the air shimmers" on an extreme-heat day) or moon accent on a full/new moon. (May require a
     real weather condition; otherwise inspect via REPL: `oracle.form_override(...)`.)
  4. [ ] Server tests + device tests green: `cd server && ../.venv/bin/python -m pytest -q` and
     `.venv/bin/python -m pytest -q`.

- [ ] **Step 6: Commit the milestone**
```bash
git commit --allow-empty -m "chore: Phase 2a verified (server + device oracle)"
```

---

## Notes for the implementer

- **Server first:** S1–S7 are a standalone deliverable — you can `curl` the oracle before touching
  the device. They run in `server/` with its own pytest config.
- **Offline-first:** if `netoracle.fetch()` returns None and there's no cache, `oracle` is None and
  every effect is a no-op — the slime behaves exactly as Phase 1b. Verify by removing `ORACLE_HOST`.
- **NVM layout:** the oracle cache lives at a fixed offset (512), safely past the state blob (~57 B)
  and the journal ring (ends ~452 B). State is NOT migrated.
- **Pure vs adapter:** `slime/oracle.py` pure functions + lazy-`microcontroller` cache; `netoracle`
  is device-only. No hardware imports in `oracle`, `forms`, `quips`, `dreams`.
- **`name` parameter shadowing:** in `code.py`, the local variable is `oracle` and the module is
  imported as `oracle_mod` to avoid collision — keep that distinction.
```
