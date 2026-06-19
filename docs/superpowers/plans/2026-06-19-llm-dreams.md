# LLM Dreams (Phase 2c-i) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** On waking from a long sleep, the pet dreams an LLM-written line (local Ollama or Anthropic, via the home server), woven from its derived context, falling back to the existing on-device template dreams when the LLM is unreachable.

**Architecture:** The home server gains a provider-agnostic `llm.py` (pure prompt/clean helpers + thin httpx provider calls) and a thin `POST /dream` endpoint that just runs `generate_dream(body)`. The device builds a compact context from its cached oracle + state (pure `dreams.dream_context`), POSTs it via a new `netdream` adapter, and uses the returned line if present else `dreams.generate(...)`. Artifacts stay 100% on-device.

**Tech Stack:** FastAPI + httpx (server, both providers via REST — no new dep), pytest (host tests), CircuitPython (device), black + ruff line-length 100.

**Spec:** `docs/superpowers/specs/2026-06-19-llm-dreams-design.md`

**Plan refinement vs spec:** to keep the on-wake dream fast (no slow re-fetch chain), the DEVICE sends the full derived context (weather/moon/rhythm/day_load/inbox from its cached oracle + fam/tones/artifacts/season). `POST /dream` does NOT re-fetch weather/presence/calendar/inbox; it just calls `generate_dream(body)`. Privacy unchanged (only derived buckets/tone-words).

**Conventions:**
- Pure functions import no hardware/network. Run host tests with `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest` (a global pydantic plugin otherwise errors at collection). `.venv` has black/ruff/pytest.
- Server tests in `server/tests/` (`from app.X import ...`, run from `server/`). Device tests in `tests/` (`from slime.X import ...`, run from repo root).
- Repo is on branch `llm-dreams` (NOT main) — committing there is correct.
- Dreams ALWAYS work: any LLM/network failure or unset provider → device uses templates.

---

## File Structure

| File | Responsibility | Tested |
|------|----------------|--------|
| `server/app/llm.py` (create) | `build_prompt`/`clean_dream` (pure) + `_ollama`/`_anthropic` (httpx) + `generate_dream` | `server/tests/test_llm.py` |
| `server/app/config.py` (modify) | DREAM_* / OLLAMA_* / ANTHROPIC_* / DREAM_MAX_CHARS | — |
| `server/app/main.py` (modify) | `POST /dream` endpoint | `server/tests/test_main.py` |
| `server/docker-compose.yml`, `server/.env.example` (modify) | pass + document LLM env | — |
| `slime/dreams.py` (modify) | pure `dream_context(...)` | `tests/test_dreams.py` |
| `slime/netdream.py` (create) | device adapter: POST /dream → line or None | on-device |
| `code.py` (modify) | `_dream_on_wake` uses netdream then template fallback | on-device |

---

## Task 1: Server — `llm.build_prompt` + `clean_dream` (pure)

**Files:**
- Create: `server/app/llm.py`, `server/tests/test_llm.py`

- [ ] **Step 1: Write the failing tests**

Create `server/tests/test_llm.py`:

```python
from app.llm import build_prompt, clean_dream


def test_build_prompt_carries_constraints_and_context():
    system, user = build_prompt(
        {"weather": "rain", "season": "summer", "fam": 3, "tones": ["busy"]}, max_chars=100
    )
    assert "100" in system
    assert "dream" in system.lower()
    assert "rain" in user and "summer" in user and "busy" in user


def test_build_prompt_tolerates_empty_context():
    system, user = build_prompt({})
    assert isinstance(system, str) and isinstance(user, str)
    assert "quiet" in user  # default tone


def test_clean_dream_collapses_and_terminates():
    assert clean_dream("  i drifted\n over the   pond  ") == "i drifted over the pond."


def test_clean_dream_strips_quotes_and_keeps_terminal_punct():
    assert clean_dream('"the moon hummed!"') == "the moon hummed!"


def test_clean_dream_truncates_at_word_boundary():
    out = clean_dream("one two three four five six seven", max_chars=12)
    assert len(out) <= 13  # <= max_chars + terminal period
    assert out.endswith(".")
    assert "fiv" not in out.rstrip(".")  # cut at a word boundary, no partial word


def test_clean_dream_empty():
    assert clean_dream("") == ""
    assert clean_dream("   \n  ") == ""
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd server && PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest tests/test_llm.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.llm'`.

- [ ] **Step 3: Implement the pure helpers**

Create `server/app/llm.py`:

```python
"""LLM dream generation. build_prompt/clean_dream are pure; provider calls use httpx.

Only derived mood buckets/tone-words go to the model; only a short dream line comes back.
"""

import httpx

from . import config


def build_prompt(context, max_chars=120):
    """Build (system, user) prompts from a derived-context dict. Pure; tolerant of missing keys."""

    def g(key, default):
        value = context.get(key, default)
        return default if value in (None, "") else value

    system = (
        "You are the dreaming inner voice of a small, calm slime companion. "
        "Write ONE short dream of at most {} characters, in 1-2 gentle, slightly surreal "
        "sentences, in a soft ambient voice. You may quietly reflect the mood hints, but "
        "NEVER invent specific people, names, real places, or facts about the human. "
        "Output only the dream line: no preamble, no quotation marks."
    ).format(max_chars)

    tones = g("tones", [])
    tones_str = ", ".join(str(t) for t in tones) if tones else "quiet"
    user = (
        "Mood hints - season: {season}; weather: {weather}; moon phase: {moon}; "
        "work rhythm: {rhythm}; day load: {day_load}; inbox: {inbox}; bond level: {fam}; "
        "recent days felt: {tones}; small treasures found: {artifacts}. "
        "Write the dream now."
    ).format(
        season=g("season", "unknown"),
        weather=g("weather", "calm"),
        moon=g("moon", "?"),
        rhythm=g("rhythm", "idle"),
        day_load=g("day_load", "unknown"),
        inbox=g("inbox", "unknown"),
        fam=g("fam", 0),
        tones=tones_str,
        artifacts=g("artifacts", 0),
    )
    return system, user


def clean_dream(text, max_chars=120):
    """Collapse whitespace, strip wrapping quotes, truncate at a word boundary, terminate."""
    if not text:
        return ""
    s = " ".join(text.split()).strip().strip("\"'").strip()
    if not s:
        return ""
    if len(s) > max_chars:
        cut = s[:max_chars]
        if " " in cut:
            cut = cut[: cut.rfind(" ")]
        s = cut.rstrip(",;:- ")
    if s and s[-1] not in ".!?":
        s += "."
    return s
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd server && PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest tests/test_llm.py -v`
Expected: PASS (6 tests).

- [ ] **Step 5: Lint + commit**

```bash
source .venv/bin/activate
black --line-length 100 server/app/llm.py server/tests/test_llm.py
ruff check server/app/llm.py server/tests/test_llm.py
git add server/app/llm.py server/tests/test_llm.py
git commit -m "feat: add llm.build_prompt + clean_dream (pure dream prompt helpers)"
```

---

## Task 2: Server — providers + `generate_dream` + config

**Files:**
- Modify: `server/app/llm.py`, `server/app/config.py`
- Test: `server/tests/test_llm.py`

- [ ] **Step 1: Write the failing tests**

Append to `server/tests/test_llm.py`:

```python
from app import config, llm


def test_generate_dream_none_when_unconfigured(monkeypatch):
    monkeypatch.setattr(config, "DREAM_PROVIDER", "")
    assert llm.generate_dream({"weather": "rain"}) is None


def test_generate_dream_cleans_provider_output(monkeypatch):
    monkeypatch.setattr(config, "DREAM_PROVIDER", "ollama")
    monkeypatch.setattr(llm, "_ollama", lambda s, u, url, m: "  i floated\nover the sea  ")
    assert llm.generate_dream({"weather": "rain"}) == "i floated over the sea."


def test_generate_dream_none_when_provider_raises(monkeypatch):
    monkeypatch.setattr(config, "DREAM_PROVIDER", "anthropic")

    def boom(s, u, k, m):
        raise RuntimeError("api down")

    monkeypatch.setattr(llm, "_anthropic", boom)
    assert llm.generate_dream({"weather": "rain"}) is None


def test_generate_dream_none_for_unknown_provider(monkeypatch):
    monkeypatch.setattr(config, "DREAM_PROVIDER", "mystery")
    assert llm.generate_dream({}) is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd server && PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest tests/test_llm.py -v`
Expected: FAIL — `llm` has no `generate_dream`/`_ollama`/`_anthropic`; `config` has no `DREAM_PROVIDER`.

- [ ] **Step 3: Add config vars**

In `server/app/config.py`, after the IMAP block add:

```python
DREAM_PROVIDER = os.getenv("DREAM_PROVIDER", "")  # "" | "ollama" | "anthropic"
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5")
DREAM_MAX_CHARS = int(os.getenv("DREAM_MAX_CHARS", "120"))
```

- [ ] **Step 4: Implement providers + `generate_dream`**

Append to `server/app/llm.py`:

```python
def _ollama(system, user, url, model):
    """Call a local Ollama /api/generate. Returns raw text; raises on HTTP error."""
    with httpx.Client(timeout=25) as client:
        resp = client.post(
            url.rstrip("/") + "/api/generate",
            json={"model": model, "system": system, "prompt": user, "stream": False},
        )
        resp.raise_for_status()
        return resp.json().get("response", "")


def _anthropic(system, user, key, model):
    """Call the Anthropic Messages REST API. Returns raw text; raises on HTTP error."""
    with httpx.Client(timeout=25) as client:
        resp = client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": model,
                "max_tokens": 200,
                "system": system,
                "messages": [{"role": "user", "content": user}],
            },
        )
        resp.raise_for_status()
        parts = resp.json().get("content", [])
        return "".join(p.get("text", "") for p in parts if p.get("type") == "text")


def generate_dream(context):
    """Generate a cleaned dream line for the context, or None (unconfigured/empty/any error)."""
    provider = config.DREAM_PROVIDER
    if not provider:
        return None
    try:
        system, user = build_prompt(context, config.DREAM_MAX_CHARS)
        if provider == "ollama":
            raw = _ollama(system, user, config.OLLAMA_URL, config.OLLAMA_MODEL)
        elif provider == "anthropic":
            raw = _anthropic(system, user, config.ANTHROPIC_API_KEY, config.ANTHROPIC_MODEL)
        else:
            return None
        return clean_dream(raw, config.DREAM_MAX_CHARS) or None
    except Exception:
        return None
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd server && PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest tests/test_llm.py -v`
Expected: PASS (10 tests).

- [ ] **Step 6: Lint + commit**

```bash
source .venv/bin/activate
black --line-length 100 server/app/llm.py server/app/config.py server/tests/test_llm.py
ruff check server/app/llm.py server/app/config.py server/tests/test_llm.py
git add server/app/llm.py server/app/config.py server/tests/test_llm.py
git commit -m "feat: add generate_dream + ollama/anthropic providers + config"
```

---

## Task 3: Server — `POST /dream` endpoint + compose/.env

**Files:**
- Modify: `server/app/main.py`, `server/docker-compose.yml`, `server/.env.example`
- Test: `server/tests/test_main.py`

- [ ] **Step 1: Write the failing tests**

Append to `server/tests/test_main.py`:

```python
def test_dream_returns_line(monkeypatch):
    monkeypatch.setattr(main_mod.llm, "generate_dream", lambda ctx: "i drifted past slow clouds.")
    c = _client(monkeypatch)
    r = c.post("/dream", json={"fam": 3, "tones": ["quiet"], "weather": "rain"})
    assert r.status_code == 200
    assert r.json()["dream"] == "i drifted past slow clouds."


def test_dream_returns_none_when_unconfigured(monkeypatch):
    monkeypatch.setattr(main_mod.llm, "generate_dream", lambda ctx: None)
    r = _client(monkeypatch).post("/dream", json={})
    assert r.status_code == 200
    assert r.json()["dream"] is None


def test_dream_requires_token_when_configured(monkeypatch):
    monkeypatch.setattr(main_mod.config, "ORACLE_TOKEN", "sekret")
    monkeypatch.setattr(main_mod.llm, "generate_dream", lambda ctx: "x.")
    c = _client(monkeypatch)
    assert c.post("/dream", json={}).status_code == 401
    assert c.post("/dream", json={}, headers={"Authorization": "Bearer sekret"}).status_code == 200
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd server && PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest tests/test_main.py -v`
Expected: FAIL — no `/dream` route (404); `main_mod.llm` doesn't exist.

- [ ] **Step 3: Add the endpoint**

In `server/app/main.py`, add `llm` to the imports line (keep alphabetical):

```python
from . import calendar, config, github, inbox, llm, moon, oracle, weather
```

Add `Body` to the FastAPI import:

```python
from fastapi import Body, FastAPI, Header, HTTPException
```

Add the endpoint (after `get_oracle`):

```python
@app.post("/dream")
def post_dream(body: dict = Body(default={}), authorization: str = Header(default="")) -> dict:
    """Generate an LLM dream line from the device-supplied derived context.

    The device sends its full derived context (weather/moon/rhythm/day_load/inbox + fam/
    tones/artifacts/season); we just run the model. Never 500s — returns {"dream": None}
    on any failure so the device falls back to its on-device templates.
    """
    _check_auth(authorization)
    return {"dream": llm.generate_dream(body or {})}
```

- [ ] **Step 4: Compose + .env**

In `server/docker-compose.yml`, add to the `environment:` block (after the IMAP vars):

```yaml
      # LLM dreams: DREAM_PROVIDER = "ollama" or "anthropic" (empty -> template dreams only).
      # Ollama: set OLLAMA_URL/OLLAMA_MODEL. Anthropic: set ANTHROPIC_API_KEY/ANTHROPIC_MODEL.
      DREAM_PROVIDER: "${DREAM_PROVIDER:-}"
      OLLAMA_URL: "${OLLAMA_URL:-http://localhost:11434}"
      OLLAMA_MODEL: "${OLLAMA_MODEL:-llama3.2}"
      ANTHROPIC_API_KEY: "${ANTHROPIC_API_KEY:-}"
      ANTHROPIC_MODEL: "${ANTHROPIC_MODEL:-claude-haiku-4-5}"
      DREAM_MAX_CHARS: "${DREAM_MAX_CHARS:-120}"
```

In `server/.env.example`, append:

```
# LLM dreams (optional). Empty DREAM_PROVIDER -> the pet uses its built-in template dreams.
#   ollama:    DREAM_PROVIDER=ollama, OLLAMA_URL=http://host.docker.internal:11434, OLLAMA_MODEL=llama3.2
#   anthropic: DREAM_PROVIDER=anthropic, ANTHROPIC_API_KEY=sk-ant-..., ANTHROPIC_MODEL=claude-haiku-4-5
DREAM_PROVIDER=
OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2
ANTHROPIC_API_KEY=
ANTHROPIC_MODEL=claude-haiku-4-5
DREAM_MAX_CHARS=120
```

- [ ] **Step 5: Run the full server suite**

Run: `cd server && PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q -p no:cacheprovider`
Expected: PASS (existing + 3 new).

- [ ] **Step 6: Lint + commit**

```bash
source .venv/bin/activate
black --line-length 100 server/app/main.py server/tests/test_main.py
ruff check server/app/main.py server/tests/test_main.py
git add server/app/main.py server/docker-compose.yml server/.env.example server/tests/test_main.py
git commit -m "feat: add POST /dream endpoint + LLM env passthrough"
```

---

## Task 4: Device — pure `dreams.dream_context`

**Files:**
- Modify: `slime/dreams.py`
- Test: `tests/test_dreams.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_dreams.py` (create the file with this content if it does not exist):

```python
from collections import namedtuple

from slime.dreams import dream_context

# Stand-in for slime.oracle.Oracle's fields used by dream_context.
Ora = namedtuple(
    "Ora", "weather_tag moon_phase coding_rhythm cal_known day_load mail_known inbox_load"
)


def _rec(flags):
    # journal record tuple: (day_ordinal, mood_dom, season, flags, tier)
    return (20000, 2, 1, flags, 3)


def test_dream_context_tones_and_artifacts_from_state():
    ctx = dream_context(3, 0b101, [_rec(0b10)], "summer", None)  # busy flag, 2 artifacts
    assert ctx["fam"] == 3
    assert "busy" in ctx["tones"]
    assert ctx["artifacts"] == 2
    assert ctx["season"] == "summer"


def test_dream_context_quiet_when_no_flags():
    ctx = dream_context(1, 0, [], "winter", None)
    assert ctx["tones"] == ["quiet"]
    assert ctx["artifacts"] == 0


def test_dream_context_includes_oracle_signals():
    o = Ora("rain", 4, "heavy", True, "busy", True, "flooded")
    ctx = dream_context(2, 0, [], "spring", o)
    assert ctx["weather"] == "rain"
    assert ctx["moon"] == 4
    assert ctx["rhythm"] == "heavy"
    assert ctx["day_load"] == "busy"
    assert ctx["inbox"] == "flooded"


def test_dream_context_omits_gated_oracle_fields_when_unknown():
    o = Ora("clear", 2, "idle", False, "light", False, "clear")
    ctx = dream_context(0, 0, [], "autumn", o)
    assert "day_load" not in ctx  # cal_known False
    assert "inbox" not in ctx  # mail_known False
    assert ctx["weather"] == "clear"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest tests/test_dreams.py -v`
Expected: FAIL — `ImportError: cannot import name 'dream_context'`.

- [ ] **Step 3: Implement**

In `slime/dreams.py`, add after the `_MIN_SLEEP` constant (before `should_dream`):

```python
# Journal flag bits -> short tone-words for the dream context (matches code.py _maybe_journal).
_TONE_BITS = ((0b10, "busy"), (0b100, "mail"), (0b1, "visited"))


def _popcount(mask):
    count = 0
    while mask:
        count += mask & 1
        mask >>= 1
    return count


def dream_context(tier, artifacts_mask, journal_records, season, oracle):
    """Build the compact derived context the device sends to the dream server. Pure.

    `journal_records` are journal entry tuples (day_ordinal, mood_dom, season, flags, tier);
    tone-words come from the most recent up-to-2 records' flags. `oracle` may be None.
    """
    tones = []
    for record in reversed(list(journal_records)[-2:]):
        flags = record[3]
        for bit, word in _TONE_BITS:
            if flags & bit and word not in tones:
                tones.append(word)
    if not tones:
        tones = ["quiet"]
    ctx = {
        "fam": tier,
        "tones": tones[:2],
        "season": season or "",
        "artifacts": _popcount(artifacts_mask),
    }
    if oracle is not None:
        ctx["weather"] = oracle.weather_tag
        ctx["moon"] = oracle.moon_phase
        ctx["rhythm"] = oracle.coding_rhythm
        if oracle.cal_known:
            ctx["day_load"] = oracle.day_load
        if oracle.mail_known:
            ctx["inbox"] = oracle.inbox_load
    return ctx
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest tests/test_dreams.py -v`
Expected: PASS (4 tests). Re-run full device suite `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q` → all pass.

- [ ] **Step 5: Lint + commit**

```bash
source .venv/bin/activate
black --line-length 100 slime/dreams.py tests/test_dreams.py
ruff check slime/dreams.py tests/test_dreams.py
git add slime/dreams.py tests/test_dreams.py
git commit -m "feat: add pure dreams.dream_context (derived dream context builder)"
```

---

## Task 5: Device — `netdream` adapter + `_dream_on_wake` wiring

**Files:**
- Create: `slime/netdream.py`
- Modify: `code.py`

Device-only. Gate: `python3 -c "import ast; ast.parse(open('code.py').read()); ast.parse(open('slime/netdream.py').read()); print('ok')"`. READ `code.py` `_dream_on_wake` and its call site in `main()` first.

- [ ] **Step 1: Create the netdream adapter**

Create `slime/netdream.py`:

```python
"""Hardware adapter: fetch an LLM dream line from the home server. Device-only. Never raises.

Assumes WiFi is already connected (nettime.sync connects it at boot). POSTs the derived
context to <ORACLE_HOST>/dream; returns the dream line or None on any failure/empty.
"""

import os


def fetch(context):
    """POST `context` to http://<ORACLE_HOST>/dream; return the dream line or None."""
    try:
        import json as _json
        import ssl

        import adafruit_requests
        import socketpool
        import wifi

        host = os.getenv("ORACLE_HOST")
        if not host:
            return None
        pool = socketpool.SocketPool(wifi.radio)
        session = adafruit_requests.Session(pool, ssl.create_default_context())
        headers = {"Content-Type": "application/json"}
        token = os.getenv("ORACLE_TOKEN")
        if token:
            headers["Authorization"] = "Bearer " + token
        resp = session.post(
            "http://" + host + "/dream",
            data=_json.dumps(context),
            headers=headers,
            timeout=25,
        )
        data = resp.json()
        resp.close()
        line = data.get("dream")
        return line if line else None
    except Exception:
        return None
```

- [ ] **Step 2: Import netdream + dream_context in `code.py`**

In `code.py`, add `netdream` to the `from slime import (...)` block (keep alphabetical — it goes after `nettime`). `dreams` is already imported. `journal` is already imported.

- [ ] **Step 3: Rewrite `_dream_on_wake`**

Replace the existing `_dream_on_wake` function in `code.py` with (it now takes `ring` + `season`, builds the context, tries the LLM, and falls back to the template — the artifact roll stays from `dreams.generate`):

```python
def _dream_on_wake(display, sound, state, oracle=None, ring=None, season=None):
    """Generate and show a dream + maybe an artifact. Returns updated state.

    The dream line comes from the home-server LLM when reachable, else the on-device
    template. The artifact roll + NVM bookkeeping always run on-device (unchanged).
    """
    fam_tier = friendship.tier(state.familiarity)
    refs = oracle_mod.dream_refs(oracle) if oracle is not None else ()
    template_line, artifact_id = dreams.generate(
        fam_tier, state.artifacts, _choice, extra_refs=refs
    )
    records = journal.entries(ring) if ring is not None else []
    ctx = dreams.dream_context(fam_tier, state.artifacts, records, season, oracle)
    line = netdream.fetch(ctx) or template_line

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

(This preserves the existing artifact/sound/render behavior verbatim — only the dream *line* source changes. Confirm the original `_dream_on_wake` body matches the artifact/sound/render block above; if the original differs, keep the original's artifact/sound/render lines and only swap in the `line = netdream.fetch(ctx) or template_line` sourcing.)

- [ ] **Step 4: Update the call site in `main()`**

In `code.py` `main()`, find the dream call (currently `state = _dream_on_wake(display, sound, state, oracle)`) and change it to pass the ring + season:

```python
        state = _dream_on_wake(display, sound, state, oracle, ring=ring, season=season)
```

(Confirm `ring` and `season` are already in scope at that point — `ring = journal.load_ring()` and `season = _current_season(...)` are assigned earlier in `main()`, before the `woke_deep`/dream block. They are.)

- [ ] **Step 5: Offline gate + full host suite**

```bash
python3 -c "import ast; ast.parse(open('code.py').read()); ast.parse(open('slime/netdream.py').read()); print('ok')"
source .venv/bin/activate
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q -p no:cacheprovider
```
Expected: `ok`, all host tests pass (code.py/netdream are device-only, not imported by host tests).

- [ ] **Step 6: Lint + commit**

```bash
black --line-length 100 code.py slime/netdream.py
ruff check code.py slime/netdream.py
git add code.py slime/netdream.py
git commit -m "feat: dream on wake via LLM server with on-device template fallback"
```

- [ ] **Step 7: On-device + live-server verification**

1. Configure a provider in `server/.env` (e.g. `DREAM_PROVIDER=anthropic` + `ANTHROPIC_API_KEY=...`, or `DREAM_PROVIDER=ollama` with Ollama running and `OLLAMA_URL=http://host.docker.internal:11434`), then `docker compose up -d --build oracle`. Verify: `curl -s -X POST http://192.168.0.38:8080/dream -H 'content-type: application/json' -d '{"fam":3,"tones":["quiet"],"weather":"clear","season":"summer"}'` returns a `{"dream": "..."}` line.
2. Deploy `code.py` + `slime/` to `CIRCUITPY`.
3. Let the pet sleep > 15 min (battery deep-sleep) or trigger a long-sleep wake; confirm an LLM dream line appears on wake. Stop the server (or unset `DREAM_PROVIDER`) and confirm it falls back to a template dream.

---

## Self-Review

**Spec coverage:**
- Provider-agnostic LLM (ollama/anthropic via httpx, no new dep) → Tasks 1–2. ✓
- Pure `build_prompt` + `clean_dream` (voice/constraints, length cap, single-line) → Task 1. ✓
- `generate_dream` provider switch, None on unconfigured/error → Task 2. ✓
- Config (DREAM_PROVIDER/OLLAMA_*/ANTHROPIC_*/DREAM_MAX_CHARS) + compose + .env → Tasks 2–3. ✓
- `POST /dream` thin endpoint, never 500s, honors ORACLE_TOKEN → Task 3. ✓
- Relational context: pure `dreams.dream_context` (fam/tones/artifacts/season + oracle signals, gated) → Task 4. ✓
- Device `netdream` adapter + `_dream_on_wake` LLM-then-template, artifacts unchanged → Task 5. ✓
- Privacy (only derived buckets/tones; prompt forbids invented facts) → Task 1 system prompt + Task 4 context. ✓
- Offline-first (any failure → template; endpoint never 500s) → Tasks 2/3/5. ✓
- Testing both tiers → Tasks 1–4 host tests; Task 5 on-device. ✓

**Placeholder scan:** No TBD/TODO; every code step has full code. The two "confirm the original matches" notes in Task 5 are guard instructions for an exact-match edit, not placeholders (the full replacement code is given). ✓

**Type consistency:** Context dict keys (`fam`/`tones`/`artifacts`/`season`/`weather`/`moon`/`rhythm`/`day_load`/`inbox`) are produced by `dreams.dream_context` (Task 4), consumed by `llm.build_prompt` via `.get` (Task 1), and posted by `netdream.fetch` (Task 5) → `POST /dream` body → `generate_dream` (Task 2/3). `generate_dream(context)`/`build_prompt(context, max_chars)`/`clean_dream(text, max_chars)`/`_ollama(s,u,url,m)`/`_anthropic(s,u,k,m)` signatures match their call sites. `DREAM_PROVIDER`/`OLLAMA_URL`/`OLLAMA_MODEL`/`ANTHROPIC_API_KEY`/`ANTHROPIC_MODEL`/`DREAM_MAX_CHARS` defined in config (Task 2) and read in `generate_dream` (Task 2). `_dream_on_wake(display, sound, state, oracle, ring, season)` new signature matches the updated call site (Task 5). ✓
