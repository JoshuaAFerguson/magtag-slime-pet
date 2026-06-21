# Long-term Memory — Plan A: Server Episodic Memory (Phase 2c-ii)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The home server keeps a bounded JSONL log of notable days (posted by the device via `POST /remember`) and weaves a recalled moment into the LLM dream prompt.

**Architecture:** New pure `memory.py` (episode reduction + notable recall + thin JSONL append/load), a `POST /remember` endpoint, recall injected into `POST /dream`, and `build_prompt` gaining an optional memory line. A mounted Docker volume persists the log.

**Tech Stack:** FastAPI + stdlib json/os (no new dep), pytest, black + ruff line-length 100.

**Spec:** `docs/superpowers/specs/2026-06-20-long-term-memory-design.md` (this is Plan A of two; Plan B is the device half).

**Conventions:** Pure functions import no I/O in their bodies. Run host tests from `server/` with `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest`. `.venv` has black/ruff/pytest. Branch is `long-term-memory` (NOT main) — committing there is correct.

---

## File Structure

| File | Responsibility | Tested |
|------|----------------|--------|
| `server/app/memory.py` (create) | `episode_from`/`recall` (pure) + `append_episode`/`load_episodes` (JSONL I/O) | `server/tests/test_memory.py` |
| `server/app/llm.py` (modify) | `build_prompt` optional memory line | `server/tests/test_llm.py` |
| `server/app/config.py` (modify) | `MEMORY_PATH`/`MEMORY_CAP` | — |
| `server/app/main.py` (modify) | `POST /remember`; recall injected into `/dream` | `server/tests/test_main.py` |
| `server/docker-compose.yml`, `server/.env.example` (modify) | memory volume + env | — |

---

## Task 1: `memory.py` — episodes + recall

**Files:**
- Create: `server/app/memory.py`, `server/tests/test_memory.py`

- [ ] **Step 1: Write the failing tests**

Create `server/tests/test_memory.py`:

```python
from app import memory


def test_episode_from_reduces_context():
    ctx = {"weather": "rain", "moon": 4, "rhythm": "heavy", "day_load": "busy",
           "inbox": "flooded", "tones": ["busy", "mail"], "fam": 3}
    ep = memory.episode_from(ctx, "2026-06-20T10:00")
    assert ep == {"date": "2026-06-20T10:00", "weather": "rain", "moon": 4,
                  "presence": "heavy", "calendar": "busy", "inbox": "flooded", "tone": "busy"}


def test_recall_renders_notable_phrase():
    eps = [{"weather": "storm_incoming", "moon": 2, "inbox": "clear"}]
    assert memory.recall(eps, lambda kinds: kinds[0]) == "the day a desert storm rolled in"
    eps2 = [{"weather": "clear", "moon": 4, "inbox": "clear"}]
    assert memory.recall(eps2, lambda kinds: kinds[0]) == "a night under the full moon"


def test_recall_none_when_nothing_notable():
    eps = [{"weather": "clear", "moon": 2, "inbox": "clear", "presence": "light", "tone": "busy"}]
    assert memory.recall(eps, lambda kinds: kinds[0]) is None
    assert memory.recall([], lambda kinds: kinds[0]) is None


def test_append_and_load_roundtrip(tmp_path):
    p = str(tmp_path / "mem.jsonl")
    memory.append_episode(p, {"date": "d1", "weather": "rain"}, cap=10)
    memory.append_episode(p, {"date": "d2", "weather": "clear"}, cap=10)
    eps = memory.load_episodes(p)
    assert len(eps) == 2 and eps[0]["weather"] == "rain" and eps[1]["date"] == "d2"


def test_append_caps_to_most_recent(tmp_path):
    p = str(tmp_path / "mem.jsonl")
    for i in range(5):
        memory.append_episode(p, {"i": i}, cap=3)
    eps = memory.load_episodes(p)
    assert [e["i"] for e in eps] == [2, 3, 4]


def test_load_missing_or_corrupt(tmp_path):
    assert memory.load_episodes(str(tmp_path / "nope.jsonl")) == []
    p = tmp_path / "bad.jsonl"
    p.write_text('{"ok": 1}\nNOT JSON\n{"ok": 2}\n')
    eps = memory.load_episodes(str(p))
    assert [e["ok"] for e in eps] == [1, 2]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd server && PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest tests/test_memory.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.memory'`.

- [ ] **Step 3: Implement**

Create `server/app/memory.py`:

```python
"""Episodic memory: a bounded JSONL log of notable days + recall.

episode_from/recall are pure; append_episode/load_episodes touch the filesystem. Only
derived buckets/tones are stored — never event content.
"""

import json
import os

_RECALL = {
    "storm": "the day a desert storm rolled in",
    "heat": "an afternoon when the heat shimmered",
    "rain": "the day the rain finally came",
    "full_moon": "a night under the full moon",
    "new_moon": "a night with no moon at all",
    "flooded": "a day the messages would not stop",
    "quiet": "the long quiet before you returned",
    "heavy": "a day full of work and meetings",
}


def episode_from(context, now_iso):
    """Reduce a posted day-context to a compact episode (only derived fields). Pure."""
    return {
        "date": now_iso,
        "weather": context.get("weather", "calm"),
        "moon": context.get("moon"),
        "presence": context.get("rhythm", "idle"),
        "calendar": context.get("day_load"),
        "inbox": context.get("inbox"),
        "tone": (context.get("tones") or ["quiet"])[0],
    }


def _kind(ep):
    """Classify a single episode's most notable kind, or None."""
    w = ep.get("weather")
    if w in ("storm_incoming", "monsoon"):
        return "storm"
    if w == "extreme_heat":
        return "heat"
    if w == "rain":
        return "rain"
    if ep.get("moon") == 4:
        return "full_moon"
    if ep.get("moon") == 0:
        return "new_moon"
    if ep.get("inbox") == "flooded":
        return "flooded"
    if ep.get("presence") == "idle" and ep.get("tone") == "quiet":
        return "quiet"
    if ep.get("calendar") == "heavy" or ep.get("presence") == "heavy":
        return "heavy"
    return None


def recall(episodes, choice):
    """Pick a notable past episode and render a short recall phrase, or None. Pure.

    `choice(kinds)` selects one kind from the notable-kind list (duplicates weight toward
    common kinds); the phrase is looked up per kind.
    """
    kinds = [k for k in (_kind(ep) for ep in episodes) if k]
    if not kinds:
        return None
    return _RECALL[choice(kinds)]


def append_episode(path, episode, cap):
    """Append one episode as a JSON line; keep at most `cap` most-recent lines."""
    try:
        with open(path) as f:
            lines = [ln for ln in f.read().splitlines() if ln.strip()]
    except OSError:
        lines = []
    lines.append(json.dumps(episode))
    lines = lines[-cap:]
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")


def load_episodes(path):
    """Read all episodes from the JSONL log; [] on a missing file, skipping corrupt lines."""
    out = []
    try:
        with open(path) as f:
            content = f.read()
    except OSError:
        return []
    for line in content.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except ValueError:
            continue
    return out
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd server && PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest tests/test_memory.py -v`
Expected: PASS (6 tests).

- [ ] **Step 5: Lint + commit**

```bash
source .venv/bin/activate
black --line-length 100 server/app/memory.py server/tests/test_memory.py
ruff check server/app/memory.py server/tests/test_memory.py
git add server/app/memory.py server/tests/test_memory.py
git commit -m "feat: add memory.py (episodic log + notable recall)"
```

---

## Task 2: `build_prompt` memory line + config

**Files:**
- Modify: `server/app/llm.py`, `server/app/config.py`
- Test: `server/tests/test_llm.py`

- [ ] **Step 1: Write the failing tests**

Append to `server/tests/test_llm.py`:

```python
def test_build_prompt_includes_memory_when_set():
    _, user = build_prompt({"memory": "the night of the storm"})
    assert "remembered moment: the night of the storm" in user


def test_build_prompt_omits_memory_when_absent():
    _, user = build_prompt({})
    assert "remembered moment" not in user
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd server && PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest tests/test_llm.py -v`
Expected: FAIL — no memory line in the user prompt.

- [ ] **Step 3: Add the memory line to `build_prompt`**

In `server/app/llm.py` `build_prompt`, replace the `user = (...).format(...)` assignment and the
`return system, user` with a version that drops the inline "Write the dream now." from the
template, conditionally appends the memory hint, then the closing instruction. The `user`
template currently ends with `"small treasures found: {artifacts}. " "Write the dream now."` —
change it to end at `"small treasures found: {artifacts}."` (remove the trailing
`" Write the dream now."` from the template string), then after the `.format(...)` add:

```python
    memory_hint = context.get("memory")
    if memory_hint:
        user += " You may gently reference this remembered moment: {}.".format(memory_hint)
    user += " Write the dream now."
    return system, user
```

(So the final `user` is: the mood-hints sentence, then optionally the memory sentence, then
"Write the dream now.")

- [ ] **Step 4: Add config vars**

In `server/app/config.py`, after the DREAM_* / ANTHROPIC_* block add:

```python
MEMORY_PATH = os.getenv("MEMORY_PATH", "/data/memory.jsonl")  # episodic log (mounted volume)
MEMORY_CAP = int(os.getenv("MEMORY_CAP", "365"))  # keep at most this many most-recent episodes
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd server && PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest tests/test_llm.py -v`
Expected: PASS (existing + 2 new). The existing prompt tests still pass — they assert tokens
that are still present, and "Write the dream now." still appears at the end.

- [ ] **Step 6: Lint + commit**

```bash
source .venv/bin/activate
black --line-length 100 server/app/llm.py server/app/config.py server/tests/test_llm.py
ruff check server/app/llm.py server/app/config.py server/tests/test_llm.py
git add server/app/llm.py server/app/config.py server/tests/test_llm.py
git commit -m "feat: weave a recalled memory line into the dream prompt + memory config"
```

---

## Task 3: `POST /remember` + `/dream` recall + volume

**Files:**
- Modify: `server/app/main.py`, `server/docker-compose.yml`, `server/.env.example`
- Test: `server/tests/test_main.py`

- [ ] **Step 1: Write the failing tests**

Append to `server/tests/test_main.py`:

```python
def test_remember_appends_episode(monkeypatch, tmp_path):
    p = str(tmp_path / "mem.jsonl")
    monkeypatch.setattr(main_mod.config, "MEMORY_PATH", p)
    monkeypatch.setattr(main_mod.config, "MEMORY_CAP", 10)
    r = _client(monkeypatch).post("/remember", json={"weather": "rain", "moon": 4})
    assert r.status_code == 200 and r.json()["ok"] is True
    assert len(main_mod.memory.load_episodes(p)) == 1


def test_remember_requires_token_when_configured(monkeypatch):
    monkeypatch.setattr(main_mod.config, "ORACLE_TOKEN", "sekret")
    assert _client(monkeypatch).post("/remember", json={}).status_code == 401


def test_dream_injects_recalled_memory(monkeypatch):
    seen = {}
    monkeypatch.setattr(main_mod.memory, "load_episodes", lambda path: [{"weather": "rain"}])
    monkeypatch.setattr(main_mod.memory, "recall", lambda eps, choice: "the day the rain came")

    def capture(ctx):
        seen.update(ctx)
        return "a dream."

    monkeypatch.setattr(main_mod.llm, "generate_dream", capture)
    r = _client(monkeypatch).post("/dream", json={"fam": 2})
    assert r.json()["dream"] == "a dream."
    assert seen["memory"] == "the day the rain came"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd server && PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest tests/test_main.py -v`
Expected: FAIL — no `/remember` route; `main_mod.memory` missing; `/dream` doesn't inject memory.

- [ ] **Step 3: Wire memory into `main.py`**

In `server/app/main.py`:
- add `import random` to the top imports (after `import time`).
- add `memory` to the `from . import ...` line (alphabetical): `from . import calendar, config, github, inbox, llm, memory, moon, oracle, weather`
- replace the existing `post_dream` with a version that injects a recalled memory:

```python
@app.post("/dream")
def post_dream(body: dict = Body(default={}), authorization: str = Header(default="")) -> dict:
    """Generate an LLM dream line from the device-supplied derived context + a recalled memory.

    Never 500s — returns {"dream": None} on any failure so the device falls back to templates.
    """
    _check_auth(authorization)
    ctx = dict(body or {})
    try:
        recalled = memory.recall(memory.load_episodes(config.MEMORY_PATH), random.choice)
        if recalled:
            ctx["memory"] = recalled
    except Exception:
        pass
    return {"dream": llm.generate_dream(ctx)}
```

- add the new endpoint after `post_dream`:

```python
@app.post("/remember")
def post_remember(body: dict = Body(default={}), authorization: str = Header(default="")) -> dict:
    """Append the device's day-context to the episodic memory log. Never 500s."""
    _check_auth(authorization)
    try:
        episode = memory.episode_from(body or {}, datetime.now().isoformat(timespec="minutes"))
        memory.append_episode(config.MEMORY_PATH, episode, config.MEMORY_CAP)
        return {"ok": True}
    except Exception:
        return {"ok": False}
```

- [ ] **Step 4: Volume + env**

In `server/docker-compose.yml`, add a memory volume to the `oracle` service (after its `ports:`
block, at the same indent level as `ports:`/`environment:`):

```yaml
    volumes:
      - slime-memory:/data
```

Add the env vars to the `environment:` block (after the DREAM vars):

```yaml
      MEMORY_PATH: "${MEMORY_PATH:-/data/memory.jsonl}"
      MEMORY_CAP: "${MEMORY_CAP:-365}"
```

And add a top-level `volumes:` key at the END of the file (same indent as `services:`):

```yaml
volumes:
  slime-memory:
```

In `server/.env.example`, APPEND (do NOT remove existing content):

```
# Long-term memory log (kept in the slime-memory docker volume; rarely need to change).
MEMORY_PATH=/data/memory.jsonl
MEMORY_CAP=365
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
git commit -m "feat: add POST /remember + recall memory into /dream + memory volume"
```

---

## Self-Review

**Spec coverage (Plan A scope):**
- `memory.py` episode_from/recall (pure) + append/load JSONL → Task 1. ✓
- Notable-recall phrases per kind → Task 1 `_RECALL`/`_kind`. ✓
- `build_prompt` optional memory line → Task 2. ✓
- `MEMORY_PATH`/`MEMORY_CAP` config → Task 2. ✓
- `POST /remember` (token, never 500) → Task 3. ✓
- `/dream` injects recall → Task 3. ✓
- Mounted volume persists log → Task 3 (`slime-memory:/data` + top-level volume). ✓
- Privacy (only derived fields) → Task 1 `episode_from`. ✓
- Offline/error tolerance (load→[], append failure→ok:False, recall→None) → Tasks 1/3. ✓
- (Device half — milestones, /remember posting, waking quips — is Plan B, intentionally out of scope here.)

**Placeholder scan:** No TBD/TODO; every code step has full code. ✓

**Type consistency:** `episode_from(context, now_iso)`, `recall(episodes, choice)`, `append_episode(path, episode, cap)`, `load_episodes(path)` signatures match call sites (`/remember` uses episode_from+append_episode; `/dream` uses load_episodes+recall). Episode keys (`date/weather/moon/presence/calendar/inbox/tone`) produced by `episode_from` and read by `_kind`. `context["memory"]` set in `/dream` (Task 3) is read by `build_prompt` (Task 2). `config.MEMORY_PATH`/`MEMORY_CAP` defined Task 2, used Task 3. `main_mod.memory`/`main_mod.config`/`main_mod.llm` monkeypatch targets exist. ✓
