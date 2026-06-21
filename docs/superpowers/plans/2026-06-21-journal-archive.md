# Journal Archive (Phase 2c-iii) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Serve a calm, read-only `GET /journal` web page from the home oracle that renders the pet's daily episodes (its generated journal sentence + derived weather/moon/presence buckets) newest-first, with server-side filtering by month and notable kind, open on the LAN.

**Architecture:** Additive and server-only except one small device tweak. The device's `_maybe_journal` already generates a journal sentence for the on-device render; it now also includes that sentence in the context it posts to `/remember`, so the episodic log carries it. A new pure `journal_view.py` filters episodes and renders a self-contained HTML page (inline CSS, zero JS, all episode strings HTML-escaped). A new unauthenticated `GET /journal` route wires it up. `POST /remember` stays token-gated.

**Tech Stack:** FastAPI + `HTMLResponse` (server), pytest (host tests), CircuitPython (device), black + ruff line-length 100.

**Spec:** `docs/superpowers/specs/2026-06-21-journal-archive-design.md`.

**Conventions:** Server tests live in `server/tests/` and import `app.*` (run from the `server/` dir). Run host tests with `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest` (a global pydantic plugin otherwise breaks collection). `.venv` (repo root) has black/ruff/pytest. Branch is `journal-archive` (NOT main). `code.py` is device-only — gate it with `python3 -c "import ast; ast.parse(open('code.py').read())"`, never import it in host tests.

---

## File Structure

| File | Responsibility | Tested |
|------|----------------|--------|
| `server/app/memory.py` (modify) | expose `episode_kind`; `episode_from` keeps `journal` | `server/tests/test_memory.py` |
| `server/app/journal_view.py` (create) | pure filter + HTML render of the archive | `server/tests/test_journal_view.py` |
| `server/app/main.py` (modify) | `GET /journal` (HTMLResponse, no auth) | `server/tests/test_main.py` |
| `code.py` (modify) | `_maybe_journal` posts the journal sentence | on-device (AST-gated) |

---

## Task 1: `memory.py` — expose `episode_kind`, carry the `journal` field

**Files:**
- Modify: `server/app/memory.py`
- Test: `server/tests/test_memory.py`

- [ ] **Step 1: Update + add failing tests**

In `server/tests/test_memory.py`, change `test_episode_from_reduces_context` so the expected dict includes `"journal": None` (episode_from now always carries the key):

```python
    ep = memory.episode_from(ctx, "2026-06-20T10:00")
    assert ep == {
        "date": "2026-06-20T10:00",
        "weather": "rain",
        "moon": 4,
        "presence": "heavy",
        "calendar": "busy",
        "inbox": "flooded",
        "tone": "busy",
        "journal": None,
    }
```

Append these new tests to `server/tests/test_memory.py`:

```python
def test_episode_from_keeps_journal_line():
    ctx = {"weather": "clear", "journal": "you seemed busy today"}
    ep = memory.episode_from(ctx, "2026-06-21T09:00")
    assert ep["journal"] == "you seemed busy today"


def test_episode_kind_classifies():
    assert memory.episode_kind({"weather": "storm_incoming"}) == "storm"
    assert memory.episode_kind({"weather": "clear", "moon": 4}) == "full_moon"
    assert memory.episode_kind({"weather": "clear", "moon": 2, "inbox": "flooded"}) == "flooded"
    assert memory.episode_kind({"weather": "clear", "moon": 2, "inbox": "clear"}) is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run (from `server/`): `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest tests/test_memory.py -v`
Expected: FAIL — `episode_from` lacks `journal`; `memory.episode_kind` does not exist.

- [ ] **Step 3: Rename `_kind` → `episode_kind` and add `journal` to `episode_from`**

In `server/app/memory.py`, rename the private classifier to a public name and update its one caller:

Change the `def _kind(ep):` line to:

```python
def episode_kind(ep):
    """Classify a single episode's most notable kind, or None."""
```

In `recall`, change the comprehension to call the new name:

```python
    kinds = [k for k in (episode_kind(ep) for ep in episodes) if k]
```

In `episode_from`, add the `journal` key to the returned dict (after `"tone": ...`):

```python
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
        "journal": context.get("journal"),
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run (from `server/`): `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest tests/test_memory.py -v`
Expected: PASS (existing recall/append/load tests still pass; the renamed classifier is internal).

- [ ] **Step 5: Lint + commit**

```bash
source .venv/bin/activate
black --line-length 100 server/app/memory.py server/tests/test_memory.py
ruff check server/app/memory.py server/tests/test_memory.py
git add server/app/memory.py server/tests/test_memory.py
git commit -m "feat: expose episode_kind + carry journal line in episodes"
```

---

## Task 2: `journal_view.py` — pure filtering + HTML render

**Files:**
- Create: `server/app/journal_view.py`, `server/tests/test_journal_view.py`

- [ ] **Step 1: Write the failing tests**

Create `server/tests/test_journal_view.py`:

```python
from app import journal_view


def _ep(date, **kw):
    base = {
        "date": date,
        "weather": "clear",
        "moon": 2,
        "presence": "idle",
        "calendar": None,
        "inbox": "clear",
        "tone": "quiet",
        "journal": None,
    }
    base.update(kw)
    return base


def test_available_months_distinct_desc():
    eps = [_ep("2026-05-02T08:00"), _ep("2026-06-01T08:00"), _ep("2026-06-20T08:00")]
    assert journal_view.available_months(eps) == ["2026-06", "2026-05"]


def test_present_kinds_distinct():
    eps = [_ep("2026-06-01", weather="storm_incoming"), _ep("2026-06-02", moon=4), _ep("2026-06-03")]
    kinds = journal_view.present_kinds(eps)
    assert "storm" in kinds and "full_moon" in kinds


def test_filter_episodes_by_month_and_kind():
    eps = [
        _ep("2026-05-30", weather="storm_incoming"),
        _ep("2026-06-10", weather="storm_incoming"),
        _ep("2026-06-11", moon=4),
    ]
    assert [e["date"] for e in journal_view.filter_episodes(eps, "2026-06", None)] == [
        "2026-06-10",
        "2026-06-11",
    ]
    assert [e["date"] for e in journal_view.filter_episodes(eps, None, "storm")] == [
        "2026-05-30",
        "2026-06-10",
    ]
    assert journal_view.filter_episodes(eps, "2026-06", "storm")[0]["date"] == "2026-06-10"
    assert journal_view.filter_episodes(eps, "1999-01", None) == []


def test_entry_text_prefers_journal_then_kind_then_default():
    assert journal_view.entry_text(_ep("2026-06-01", journal="we napped in the sun")) == (
        "we napped in the sun"
    )
    assert journal_view.entry_text(_ep("2026-06-01", weather="storm_incoming")) == (
        "the day a desert storm rolled in"
    )
    assert journal_view.entry_text(_ep("2026-06-01")) == "a quiet, ordinary day"


def test_render_page_escapes_and_orders_newest_first():
    eps = [
        _ep("2026-06-01T08:00", journal="first day"),
        _ep("2026-06-20T08:00", journal="<script>alert(1)</script>"),
    ]
    html = journal_view.render_page(eps, None, None)
    assert "<!doctype html>" in html.lower()
    assert "&lt;script&gt;" in html  # escaped
    assert "<script>alert(1)</script>" not in html  # raw injection absent
    # newest-first: the 06-20 entry appears before the 06-01 entry
    assert html.index("2026-06-20") < html.index("2026-06-01")


def test_render_page_empty_state():
    html = journal_view.render_page([], None, None)
    assert "no entries yet" in html.lower()


def test_render_page_filtered_empty_note():
    html = journal_view.render_page([_ep("2026-06-01")], "1999-01", None)
    assert "nothing matches" in html.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run (from `server/`): `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest tests/test_journal_view.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.journal_view'`.

- [ ] **Step 3: Implement `journal_view.py`**

Create `server/app/journal_view.py`:

```python
"""Pure rendering of the episodic log as a calm, read-only HTML journal archive.

No I/O: the route loads episodes and passes them in. Every episode-derived string is
HTML-escaped — the data originates from the device over the untrusted /remember boundary.
"""

import html

from . import memory

_DEFAULT_ENTRY = "a quiet, ordinary day"

# Notable-kind display order + label for the filter strip.
_KIND_LABELS = (
    ("storm", "storms"),
    ("heat", "heat"),
    ("rain", "rain"),
    ("full_moon", "full moons"),
    ("new_moon", "new moons"),
    ("flooded", "busy inboxes"),
    ("heavy", "full days"),
    ("quiet", "quiet days"),
)

# Small text marks for weather + moon (web fonts render these; no images to ship).
_WEATHER_MARK = {
    "storm_incoming": "⚡",
    "monsoon": "☂",
    "rain": "☂",
    "extreme_heat": "☀",
    "clear": "☀",
    "calm": "·",
}


def _month_of(ep):
    """The YYYY-MM prefix of an episode date, or None if it has no usable date."""
    date = ep.get("date") or ""
    return date[:7] if len(date) >= 7 else None


def available_months(episodes):
    """Distinct YYYY-MM months present, newest first."""
    seen = []
    for ep in episodes:
        m = _month_of(ep)
        if m and m not in seen:
            seen.append(m)
    return sorted(seen, reverse=True)


def present_kinds(episodes):
    """Distinct notable kinds present, in display order."""
    found = {memory.episode_kind(ep) for ep in episodes}
    return [k for k, _ in _KIND_LABELS if k in found]


def filter_episodes(episodes, month, kind):
    """Episodes matching the optional month (YYYY-MM prefix) and kind. Pure."""
    out = []
    for ep in episodes:
        if month and _month_of(ep) != month:
            continue
        if kind and memory.episode_kind(ep) != kind:
            continue
        out.append(ep)
    return out


def entry_text(ep):
    """The diary sentence: the posted journal line, else a kind phrase, else the default."""
    line = ep.get("journal")
    if line:
        return line
    phrase = memory._RECALL.get(memory.episode_kind(ep))
    return phrase or _DEFAULT_ENTRY


_STYLE = """
:root {
  --paper: #f4efe6; --ink: #2b2722; --muted: #8a7f70; --accent: #9a5b34;
  --card: #fbf8f2; --line: #e3dac9;
}
* { box-sizing: border-box; }
body {
  margin: 0; background: var(--paper); color: var(--ink);
  font-family: Georgia, 'Iowan Old Style', serif; line-height: 1.6;
  padding: clamp(1.5rem, 4vw, 4rem);
}
.wrap { max-width: 44rem; margin: 0 auto; }
header h1 {
  font-size: clamp(2rem, 1rem + 5vw, 3.5rem); margin: 0 0 .25rem; letter-spacing: -.01em;
}
header p { color: var(--muted); margin: 0 0 2rem; font-style: italic; }
nav.filters { display: flex; flex-wrap: wrap; gap: .5rem; margin-bottom: 2.5rem;
  padding-bottom: 1.25rem; border-bottom: 1px solid var(--line); }
nav.filters a {
  font-family: -apple-system, system-ui, sans-serif; font-size: .8rem;
  text-decoration: none; color: var(--muted); padding: .2rem .6rem; border: 1px solid var(--line);
  border-radius: 999px; transition: color .15s, border-color .15s, background .15s;
}
nav.filters a:hover, nav.filters a:focus { color: var(--accent); border-color: var(--accent); }
nav.filters a.on { color: var(--card); background: var(--accent); border-color: var(--accent); }
article.day {
  background: var(--card); border: 1px solid var(--line); border-radius: .5rem;
  padding: 1.25rem 1.5rem; margin-bottom: 1.1rem;
}
article.day .date {
  font-family: -apple-system, system-ui, sans-serif; font-size: .75rem; letter-spacing: .08em;
  text-transform: uppercase; color: var(--muted); margin-bottom: .35rem;
}
article.day .text { font-size: 1.15rem; margin: 0 0 .5rem; }
article.day .marks { color: var(--accent); font-size: .95rem; }
article.day .marks .tone { color: var(--muted); font-style: italic; margin-left: .4rem; }
.empty { color: var(--muted); font-style: italic; font-size: 1.1rem; padding: 2rem 0; }
"""


def _filter_nav(episodes, month, kind):
    """Build the month + kind filter strip as escaped <a> links."""
    links = ['<a href="/journal"%s>all</a>' % (' class="on"' if not (month or kind) else "")]
    for m in available_months(episodes):
        on = ' class="on"' if m == month else ""
        links.append('<a href="/journal?month=%s"%s>%s</a>' % (html.escape(m), on, html.escape(m)))
    label = dict(_KIND_LABELS)
    for k in present_kinds(episodes):
        on = ' class="on"' if k == kind else ""
        links.append(
            '<a href="/journal?kind=%s"%s>%s</a>' % (html.escape(k), on, html.escape(label[k]))
        )
    return '<nav class="filters">%s</nav>' % "".join(links)


def _entry_card(ep):
    """One escaped diary card for an episode."""
    date = html.escape((ep.get("date") or "")[:10] or "an untold day")
    text = html.escape(entry_text(ep))
    mark = _WEATHER_MARK.get(ep.get("weather"), "·")
    if ep.get("moon") == 4:
        mark += " ☽"
    tone = ep.get("tone")
    tone_html = '<span class="tone">%s</span>' % html.escape(tone) if tone else ""
    return (
        '<article class="day"><div class="date">%s</div>'
        '<p class="text">%s</p>'
        '<div class="marks">%s%s</div></article>' % (date, text, mark, tone_html)
    )


def render_page(episodes, month, kind):
    """Render the full archive HTML document (newest-first, filtered, escaped)."""
    nav = _filter_nav(episodes, month, kind)
    shown = list(reversed(filter_episodes(episodes, month, kind)))
    if not episodes:
        body = '<p class="empty">no entries yet — the pet has not written home.</p>'
    elif not shown:
        body = '<p class="empty">nothing matches that filter yet.</p>'
    else:
        body = "".join(_entry_card(ep) for ep in shown)
    return (
        "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        "<title>slime &mdash; journal</title><style>%s</style></head>"
        '<body><div class="wrap"><header><h1>journal</h1>'
        "<p>quiet days, remembered.</p></header>%s%s</div></body></html>"
        % (_STYLE, nav, body)
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run (from `server/`): `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest tests/test_journal_view.py -v`
Expected: PASS (8 tests).

- [ ] **Step 5: Lint + commit**

```bash
source .venv/bin/activate
black --line-length 100 server/app/journal_view.py server/tests/test_journal_view.py
ruff check server/app/journal_view.py server/tests/test_journal_view.py
git add server/app/journal_view.py server/tests/test_journal_view.py
git commit -m "feat: pure journal_view (filter + escaped HTML archive render)"
```

---

## Task 3: `GET /journal` route

**Files:**
- Modify: `server/app/main.py`
- Test: `server/tests/test_main.py`

- [ ] **Step 1: Write the failing tests**

Append to `server/tests/test_main.py`:

```python
def test_journal_page_renders_without_auth(monkeypatch):
    eps = [
        {"date": "2026-06-01T08:00", "weather": "clear", "moon": 2, "journal": "first day"},
        {"date": "2026-06-20T08:00", "weather": "storm_incoming", "moon": 2, "journal": "a big storm"},
    ]
    monkeypatch.setattr(main_mod.memory, "load_episodes", lambda path: eps)
    r = _client(monkeypatch).get("/journal")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/html")
    assert "a big storm" in r.text
    # newest-first
    assert r.text.index("2026-06-20") < r.text.index("2026-06-01")


def test_journal_page_filters_by_kind(monkeypatch):
    eps = [
        {"date": "2026-06-01", "weather": "clear", "moon": 2, "journal": "calm"},
        {"date": "2026-06-02", "weather": "storm_incoming", "moon": 2, "journal": "stormy"},
    ]
    monkeypatch.setattr(main_mod.memory, "load_episodes", lambda path: eps)
    r = _client(monkeypatch).get("/journal?kind=storm")
    assert "stormy" in r.text and "calm" not in r.text


def test_journal_page_open_even_when_token_configured(monkeypatch):
    monkeypatch.setattr(main_mod.config, "ORACLE_TOKEN", "sekret")
    monkeypatch.setattr(main_mod.memory, "load_episodes", lambda path: [])
    # The archive page is intentionally NOT token-gated.
    assert _client(monkeypatch).get("/journal").status_code == 200


def test_journal_page_never_500s_on_load_failure(monkeypatch):
    def boom(path):
        raise RuntimeError("disk gone")

    monkeypatch.setattr(main_mod.memory, "load_episodes", boom)
    r = _client(monkeypatch).get("/journal")
    assert r.status_code == 200
    assert "no entries yet" in r.text.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run (from `server/`): `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest tests/test_main.py -k journal -v`
Expected: FAIL — `/journal` returns 404 (route absent).

- [ ] **Step 3: Add the route**

In `server/app/main.py`, add `journal_view` to the package import (the line
`from . import calendar, config, github, inbox, llm, memory, moon, oracle, weather`) so it reads:

```python
from . import calendar, config, github, inbox, journal_view, llm, memory, moon, oracle, weather
```

Add `HTMLResponse` to the FastAPI imports. Change:

```python
from fastapi import Body, FastAPI, Header, HTTPException
```

to:

```python
from fastapi import Body, FastAPI, Header, HTTPException
from fastapi.responses import HTMLResponse
```

Add the route (place it after the `post_remember` endpoint at the end of the file):

```python
@app.get("/journal", response_class=HTMLResponse)
def get_journal(month: str = "", kind: str = "") -> HTMLResponse:
    """Read-only HTML archive of the pet's days. Open on the LAN (no auth). Never 500s."""
    try:
        episodes = memory.load_episodes(config.MEMORY_PATH)
    except Exception:
        episodes = []
    html_doc = journal_view.render_page(episodes, month or None, kind or None)
    return HTMLResponse(content=html_doc)
```

- [ ] **Step 4: Run tests to verify they pass**

Run (from `server/`): `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest tests/test_main.py -v`
Expected: PASS (existing + 4 new journal tests).

- [ ] **Step 5: Full server suite + lint + commit**

```bash
source .venv/bin/activate
cd server && PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q -p no:cacheprovider ; cd ..
black --line-length 100 server/app/main.py server/tests/test_main.py
ruff check server/app/main.py server/tests/test_main.py
git add server/app/main.py server/tests/test_main.py
git commit -m "feat: add GET /journal archive page (open on LAN, never 500s)"
```

---

## Task 4: Device — post the journal sentence on a new day

**Files:**
- Modify: `code.py`

Device-only. Gate: `python3 -c "import ast; ast.parse(open('code.py').read()); print('ok')"`. READ `code.py`'s current `_maybe_journal` first.

- [ ] **Step 1: Include the journal line in the posted context**

In `code.py` `_maybe_journal`, the current block (after the 2c-ii change) is:

```python
    ring = journal.append(ring, record)
    journal.save_ring(ring)
    netmemory.post(
        dreams.dream_context(
            friendship.tier(state.familiarity),
            state.artifacts,
            journal.entries(ring),
            season,
            oracle,
        )
    )
    state = evolve(state, last_journal_day_ordinal=ordinal)
    if display:
        recs = journal.entries(ring)
        line = journal.generate_entry(recs[-1], len(recs), _choice)
        try:
            display.render_journal([line])
        except Exception:
            pass
    return state, ring
```

Replace that entire block with a version that generates the sentence ONCE, posts it inside the
context, and reuses it for the on-device render:

```python
    ring = journal.append(ring, record)
    journal.save_ring(ring)
    recs = journal.entries(ring)
    line = journal.generate_entry(recs[-1], len(recs), _choice)
    ctx = dreams.dream_context(
        friendship.tier(state.familiarity), state.artifacts, recs, season, oracle
    )
    ctx["journal"] = line  # local dict, safe to augment; reaches /remember -> episode_from
    netmemory.post(ctx)
    state = evolve(state, last_journal_day_ordinal=ordinal)
    if display:
        try:
            display.render_journal([line])
        except Exception:
            pass
    return state, ring
```

- [ ] **Step 2: Offline gate + full host suite**

```bash
python3 -c "import ast; ast.parse(open('code.py').read()); print('ok')"
source .venv/bin/activate
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q -p no:cacheprovider
cd server && PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q -p no:cacheprovider ; cd ..
```
Expected: `ok`; both suites pass (code.py is device-only, not imported by host tests).

- [ ] **Step 3: Lint + commit**

```bash
black --line-length 100 code.py
ruff check code.py
git add code.py
git commit -m "feat: post the daily journal sentence to the archive log"
```

- [ ] **Step 4: On-device + live-server verification**

1. Rebuild the server with the memory volume running (`cd server && docker compose up -d --build oracle`).
2. Open `http://<server-host>:8080/journal` in a browser — confirm the page renders, the empty
   state shows when the log is fresh, and the filter strip appears once episodes exist.
3. Deploy `code.py` + `slime/` to `CIRCUITPY`; over a few days confirm new entries appear with the
   pet's sentence and that `?month=` / `?kind=` filters work.

---

## Self-Review

**Spec coverage:**
- Device posts the journal sentence; `episode_from` keeps `journal` → Tasks 1 + 4. ✓
- `episode_kind` exposed + reused → Task 1. ✓
- `available_months` / `present_kinds` / `filter_episodes` / `entry_text` / `render_page` (escaped, newest-first, empty states, filter nav) → Task 2. ✓
- `GET /journal` HTMLResponse, no auth, never 500s, honors `?month=`/`?kind=` → Task 3. ✓
- Visual direction (warm-paper editorial, inline CSS, zero JS, designed hover/focus) → Task 2 `_STYLE`. ✓
- XSS escaping of all episode-derived strings → Task 2 (`html.escape` in `_entry_card`/`_filter_nav`); verified by the `<script>` test. ✓
- Offline-first / never-500 / empty-state → Tasks 2 + 3. ✓

**Placeholder scan:** No TBD/TODO; every code step shows full code. ✓

**Type consistency:** `memory.episode_kind` (Task 1) is called by `journal_view` (Task 2) and the renamed caller `recall`. `episode_from` carries `journal` (Task 1), set by `code.py` `ctx["journal"]` (Task 4), consumed by `entry_text` (Task 2). `journal_view.render_page(episodes, month, kind)` matches the `get_journal` call site (Task 3) with `month or None`/`kind or None`. `_RECALL` reused from `memory` for the `entry_text` fallback. `dreams.dream_context(tier, artifacts_mask, journal_records, season, oracle)` call in Task 4 matches its 2c-i signature. ✓
