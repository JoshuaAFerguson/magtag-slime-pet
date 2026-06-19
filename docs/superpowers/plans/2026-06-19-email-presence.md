# Email Presence (Phase 2b-iii) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add IMAP inbox presence (inbox_load + fresh_mail) to the home oracle and the pet's mood, voice, journal, and a status-bar envelope glyph — privacy-safe, offline-first.

**Architecture:** The FastAPI home server reads INBOX read-only over IMAP (stdlib `imaplib`), reduces it to two buckets in a new `inbox` block of `GET /oracle` (emitted only when configured). The device parses those buckets into its `Oracle`, biases mood, picks email quips, flags heavy-inbox days in the journal, and shows an envelope tile in the status bar. Pure reduction logic (server `inbox.summarize`, device `oracle.parse`/effects) is host-tested.

**Tech Stack:** FastAPI + stdlib `imaplib` (server), pytest (host tests), Pillow (asset), CircuitPython (device), black + ruff line-length 100.

**Spec:** `docs/superpowers/specs/2026-06-19-email-presence-design.md`

**Conventions:**
- Pure functions import no hardware/network. Run host tests with `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest` (a global pydantic plugin otherwise errors at collection). A project `.venv` has black/ruff/pytest: `source .venv/bin/activate`.
- Server tests live in `server/tests/` (`from app.X import ...`, run pytest from `server/`). Device tests in `tests/` (`from slime.X import ...`, run from repo root).
- Repo is on branch `email-presence` (NOT main) — committing there is correct.
- The `inbox` block is emitted ONLY when IMAP is configured AND the fetch succeeds; otherwise the key is OMITTED. The device sets `mail_known=True` only when the block is present and gates ALL email behavior on it (so an unconfigured server = no email behavior; existing tests unaffected).

---

## File Structure

| File | Responsibility | Tested |
|------|----------------|--------|
| `server/app/inbox.py` (create) | `fetch_counts` (imaplib I/O) + `_internaldate_epoch` + pure `summarize` | `server/tests/test_inbox.py` |
| `server/app/config.py` (modify) | add `IMAP_HOST`/`IMAP_USER`/`IMAP_PASSWORD` | — |
| `server/app/oracle.py` (modify) | `build(..., inbox=None, ...)` emits `inbox` when present | `server/tests/test_oracle.py` |
| `server/app/main.py` (modify) | `_inbox()` helper; pass into `build` | `server/tests/test_main.py` |
| `server/docker-compose.yml`, `server/.env.example` (modify) | pass + document IMAP env | — |
| `slime/oracle.py` (modify) | Oracle +3 fields, parse, cache format, mood/quip/helpers | `tests/test_oracle_client.py` |
| `slime/quips.py` (modify) | 4 email quip pools | `tests/test_quips.py` |
| `slime/statusbar.py` (modify) | `MAIL_UNREAD`/`MAIL_FRESH` + `mail_icon` | `tests/test_statusbar.py` |
| `assets/make_assets.py` (modify) | 2 envelope tiles → `statusicons.bmp` (10 tiles) | run-and-verify |
| `slime/display.py` (modify) | mail tile + `mail_icon` kwarg | on-device |
| `code.py` (modify) | `_status_fields` mail icon + journal heavy-inbox flag | on-device |
| `slime/journal.py` (modify) | heavy-inbox journal text | `tests/test_journal.py` |

---

## Task 1: Server — `inbox.py` (pure `summarize` + IMAP fetch)

**Files:**
- Create: `server/app/inbox.py`, `server/tests/test_inbox.py`

- [ ] **Step 1: Write the failing tests**

Create `server/tests/test_inbox.py`:

```python
from app.inbox import summarize, _internaldate_epoch

NOW = 1781889000  # arbitrary UTC epoch


def test_inbox_load_buckets():
    assert summarize(0, None, NOW)["inbox_load"] == "clear"
    assert summarize(1, NOW, NOW)["inbox_load"] == "light"
    assert summarize(10, NOW, NOW)["inbox_load"] == "light"
    assert summarize(11, NOW, NOW)["inbox_load"] == "busy"
    assert summarize(30, NOW, NOW)["inbox_load"] == "busy"
    assert summarize(31, NOW, NOW)["inbox_load"] == "flooded"


def test_fresh_mail_window():
    # arrived 10 min ago -> fresh
    assert summarize(3, NOW - 600, NOW)["fresh_mail"] is True
    # arrived 90 min ago -> not fresh
    assert summarize(3, NOW - 5400, NOW)["fresh_mail"] is False
    # exactly 60 min -> fresh (inclusive)
    assert summarize(3, NOW - 3600, NOW)["fresh_mail"] is True


def test_fresh_false_when_no_unread_or_no_date():
    assert summarize(0, None, NOW)["fresh_mail"] is False
    assert summarize(5, None, NOW)["fresh_mail"] is False


def test_internaldate_epoch_parses_imap_response():
    # IMAP INTERNALDATE response shape; UTC offset present.
    resp = b'1 (INTERNALDATE "01-Jun-2026 10:00:00 +0000")'
    out = _internaldate_epoch([resp])
    assert isinstance(out, int)


def test_internaldate_epoch_none_on_garbage():
    assert _internaldate_epoch([None]) is None
    assert _internaldate_epoch([b"nonsense"]) is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd server && PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest tests/test_inbox.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.inbox'`.

- [ ] **Step 3: Implement**

Create `server/app/inbox.py`:

```python
"""IMAP inbox -> a privacy-safe inbox-presence signal. summarize() is pure.

Reads INBOX read-only and derives only buckets — never senders, subjects, or bodies.
"""

import imaplib
import time

_LIGHT_MAX = 10
_BUSY_MAX = 30
_FRESH_MIN = 60


def _internaldate_epoch(fetch_data):
    """Parse the newest message's INTERNALDATE (UTC epoch int), or None on any problem."""
    for part in fetch_data or ():
        raw = part[0] if isinstance(part, tuple) else part
        if not raw:
            continue
        if isinstance(raw, str):
            raw = raw.encode()
        try:
            t = imaplib.Internaldate2tuple(raw)
        except Exception:
            t = None
        if t:
            return int(time.mktime(t))
    return None


def fetch_counts(host, user, password):
    """Read-only IMAP INBOX -> (unread_count, newest_unseen_epoch_or_None).

    Connects over SSL, counts UNSEEN, and reads only the newest unseen message's
    INTERNALDATE for freshness. Logs out in a finally.
    """
    m = imaplib.IMAP4_SSL(host)
    try:
        m.login(user, password)
        m.select("INBOX", readonly=True)
        _typ, data = m.search(None, "UNSEEN")
        ids = data[0].split() if data and data[0] else []
        unread = len(ids)
        newest_epoch = None
        if ids:
            _typ, fd = m.fetch(ids[-1], "(INTERNALDATE)")
            newest_epoch = _internaldate_epoch(fd)
        return unread, newest_epoch
    finally:
        try:
            m.logout()
        except Exception:
            pass


def summarize(unread, newest_unseen_epoch, now_epoch):
    """Pure: unread count + newest-unseen epoch + now epoch -> {inbox_load, fresh_mail}."""
    if unread <= 0:
        load = "clear"
    elif unread <= _LIGHT_MAX:
        load = "light"
    elif unread <= _BUSY_MAX:
        load = "busy"
    else:
        load = "flooded"
    fresh = (
        unread > 0
        and newest_unseen_epoch is not None
        and 0 <= now_epoch - newest_unseen_epoch <= _FRESH_MIN * 60
    )
    return {"inbox_load": load, "fresh_mail": bool(fresh)}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd server && PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest tests/test_inbox.py -v`
Expected: PASS (5 tests). (If `test_internaldate_epoch_parses_imap_response` is environment-sensitive to the local TZ, it only asserts the result is an int — which holds regardless.)

- [ ] **Step 5: Lint + commit**

```bash
source .venv/bin/activate
black --line-length 100 server/app/inbox.py server/tests/test_inbox.py
ruff check server/app/inbox.py server/tests/test_inbox.py
git add server/app/inbox.py server/tests/test_inbox.py
git commit -m "feat: add inbox.summarize + IMAP fetch (privacy-safe inbox-presence reducer)"
```

---

## Task 2: Server — wire inbox into `/oracle`

**Files:**
- Modify: `server/app/config.py`, `server/app/oracle.py`, `server/app/main.py`, `server/docker-compose.yml`, `server/.env.example`
- Test: `server/tests/test_oracle.py`, `server/tests/test_main.py`

- [ ] **Step 1: Write the failing tests**

Append to `server/tests/test_oracle.py`:

```python
def test_build_includes_inbox_when_present():
    inbox = {"inbox_load": "busy", "fresh_mail": True}
    out = build({}, {}, {}, inbox=inbox, ts=1)
    assert out["inbox"]["inbox_load"] == "busy"


def test_build_omits_inbox_when_none():
    out = build({}, {}, {}, inbox=None, ts=1)
    assert "inbox" not in out
```

Append to `server/tests/test_main.py`:

```python
def test_oracle_includes_inbox_when_configured(monkeypatch):
    monkeypatch.setattr(main_mod.config, "IMAP_HOST", "imap.example")
    monkeypatch.setattr(main_mod.config, "IMAP_USER", "me@example")
    monkeypatch.setattr(main_mod.config, "IMAP_PASSWORD", "app-pw")
    monkeypatch.setattr(main_mod.inbox, "fetch_counts", lambda h, u, p: (12, None))
    body = _client(monkeypatch).get("/oracle").json()
    assert "inbox" in body
    assert body["inbox"]["inbox_load"] == "busy"


def test_oracle_omits_inbox_without_config(monkeypatch):
    body = _client(monkeypatch).get("/oracle").json()
    assert "inbox" not in body
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd server && PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest tests/test_oracle.py tests/test_main.py -v`
Expected: FAIL — `build()` rejects `inbox=`; `main_mod.inbox` doesn't exist.

- [ ] **Step 3: Add config vars**

In `server/app/config.py`, after the `CALENDAR_ICS_URL` line add:

```python
IMAP_HOST = os.getenv("IMAP_HOST", "")  # e.g. imap.gmail.com
IMAP_USER = os.getenv("IMAP_USER", "")
IMAP_PASSWORD = os.getenv("IMAP_PASSWORD", "")  # an APP password for Gmail, not the account pw
```

- [ ] **Step 4: Extend `build`**

Replace `server/app/oracle.py`'s `build` with:

```python
def build(weather, moon, presence, calendar=None, inbox=None, ts=0):
    """Return the compact oracle payload served to the device.

    The `calendar` and `inbox` blocks are included only when present (not None)."""
    payload = {"weather": weather, "moon": moon, "presence": presence, "ts": ts}
    if calendar is not None:
        payload["calendar"] = calendar
    if inbox is not None:
        payload["inbox"] = inbox
    return payload
```

- [ ] **Step 5: Add `_inbox()` and wire it**

In `server/app/main.py`, add `inbox` to the imports line:

```python
from . import calendar, config, github, inbox, moon, oracle, weather
```

Add the helper (after `_calendar`):

```python
def _inbox():
    """Derive the inbox block; None (omitted) on missing config or any failure."""
    if not (config.IMAP_HOST and config.IMAP_USER and config.IMAP_PASSWORD):
        return None
    try:
        unread, newest = inbox.fetch_counts(
            config.IMAP_HOST, config.IMAP_USER, config.IMAP_PASSWORD
        )
        return inbox.summarize(unread, newest, int(time.time()))
    except Exception:
        return None
```

Change the final return of `get_oracle` to:

```python
    return oracle.build(
        w, mooninfo, _presence(), calendar=_calendar(), inbox=_inbox(), ts=int(time.time())
    )
```

- [ ] **Step 6: Compose env passthrough + .env docs**

In `server/docker-compose.yml`, add to the `environment:` block (after the calendar line):

```yaml
      # Inbox presence: put IMAP_HOST / IMAP_USER / IMAP_PASSWORD (an APP password for
      # Gmail) in the gitignored server/.env. Empty -> inbox block omitted from /oracle.
      IMAP_HOST: "${IMAP_HOST:-}"
      IMAP_USER: "${IMAP_USER:-}"
      IMAP_PASSWORD: "${IMAP_PASSWORD:-}"
```

In `server/.env.example`, append:

```
# Inbox presence (read-only IMAP). For Gmail use imap.gmail.com and a Google APP PASSWORD
# (Account -> Security -> App passwords), NOT your normal password. Empty -> inbox off.
IMAP_HOST=
IMAP_USER=
IMAP_PASSWORD=
```

- [ ] **Step 7: Run the full server suite**

Run: `cd server && PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q -p no:cacheprovider`
Expected: PASS (existing + new). The no-config test confirms the block is omitted by default.

- [ ] **Step 8: Lint + commit**

```bash
source .venv/bin/activate
black --line-length 100 server/app/config.py server/app/oracle.py server/app/main.py server/tests/test_oracle.py server/tests/test_main.py
ruff check server/app/config.py server/app/oracle.py server/app/main.py server/tests/test_oracle.py server/tests/test_main.py
git add server/app/config.py server/app/oracle.py server/app/main.py server/docker-compose.yml server/.env.example server/tests/test_oracle.py server/tests/test_main.py
git commit -m "feat: serve inbox presence block in /oracle when IMAP configured"
```

---

## Task 3: Device — `Oracle` inbox fields, parse, cache format

**Files:**
- Modify: `slime/oracle.py`
- Test: `tests/test_oracle_client.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_oracle_client.py`:

```python
def _with_inbox(load="clear", fresh=False):
    return {
        "weather": {"tags": ["clear"], "temp_c": 25.0, "sunset_soon": False},
        "moon": {"phase": 2, "illum": 0.5},
        "inbox": {"inbox_load": load, "fresh_mail": fresh},
    }


def test_parse_reads_inbox():
    o = parse(_with_inbox(load="flooded", fresh=True))
    assert o.mail_known is True
    assert o.inbox_load == "flooded"
    assert o.fresh_mail is True


def test_parse_inbox_unknown_when_absent():
    o = parse(_payload(["clear"]))
    assert o.mail_known is False
    assert o.inbox_load == "clear"
    assert o.fresh_mail is False


def test_cache_roundtrip_preserves_inbox():
    o = parse(_with_inbox(load="busy", fresh=True))
    o2 = unpack(pack(o))
    assert o2.mail_known is True
    assert o2.inbox_load == "busy"
    assert o2.fresh_mail is True


def test_unpack_calendar_era_blob_defaults_inbox_unknown():
    # A blob written before email existed (calendar-era 11-byte format) still unpacks.
    import struct

    from slime.oracle import _FMT_CAL

    cal_blob = struct.pack(_FMT_CAL, 1, 4, 1, 30.0, 0.98, 2, 1.5, 0b1000, 1)
    o = unpack(cal_blob)
    assert o.weather_tag == "storm_incoming"
    assert o.cal_known is True  # calendar bits preserved
    assert o.mail_known is False  # email defaults unknown
    assert o.inbox_load == "clear"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest tests/test_oracle_client.py -v`
Expected: FAIL — `Oracle` has no `mail_known`/`inbox_load`/`fresh_mail`; `_FMT_CAL` missing.

- [ ] **Step 3: Extend the `Oracle` namedtuple**

In `slime/oracle.py`, replace the `Oracle = namedtuple(...)` block to append the 3 email fields after `cal_known`:

```python
Oracle = namedtuple(
    "Oracle",
    (
        "weather_tag",
        "temp_c",
        "moon_phase",
        "moon_illum",
        "sunset_soon",
        "coding_rhythm",
        "hours_since_push",
        "in_meeting",
        "meeting_soon",
        "day_load",
        "free_rest",
        "cal_known",
        "inbox_load",
        "fresh_mail",
        "mail_known",
    ),
)
```

- [ ] **Step 4: Add inbox constants + extend `parse`**

After the `_CAL_IDLE = {...}` block, add:

```python
_INBOX_IDS = ("clear", "light", "busy", "flooded")
_INBOX_IDLE = {"inbox_load": "clear", "fresh_mail": False}
```

In `parse`, after the `c = cal if cal_known else _CAL_IDLE` line add:

```python
    ib = payload.get("inbox")
    mail_known = ib is not None
    e = ib if mail_known else _INBOX_IDLE
```

And add these keyword fields to the returned `Oracle(...)` (after `cal_known=cal_known,`):

```python
        inbox_load=e.get("inbox_load", "clear"),
        fresh_mail=bool(e.get("fresh_mail", False)),
        mail_known=mail_known,
```

- [ ] **Step 5: Extend pack/unpack with backward compatibility**

Replace the format/size block, `pack`, `_oracle_from`, and `unpack` with:

```python
_FMT_OLD = "<BBBffBf"  # pre-calendar layout
SIZE_OLD = struct.calcsize(_FMT_OLD)
_FMT_CAL = "<BBBffBfBB"  # calendar-era layout (cal flags byte + day_load byte)
SIZE_CAL = struct.calcsize(_FMT_CAL)
# + mail flags byte (bit0 fresh_mail, bit1 mail_known) + inbox_load byte (index into _INBOX_IDS)
_FMT = "<BBBffBfBBBB"
SIZE = struct.calcsize(_FMT)


def pack(oracle):
    """Pack an Oracle into binary form for NVM storage."""
    tag_id = _TAG_IDS.index(oracle.weather_tag) if oracle.weather_tag in _TAG_IDS else 0
    temp = oracle.temp_c if oracle.temp_c is not None else -999.0
    rhythm_id = (
        _RHYTHM_IDS.index(oracle.coding_rhythm) if oracle.coding_rhythm in _RHYTHM_IDS else 0
    )
    hours = oracle.hours_since_push if oracle.hours_since_push is not None else -1.0
    flags = (
        (0b0001 if oracle.in_meeting else 0)
        | (0b0010 if oracle.meeting_soon else 0)
        | (0b0100 if oracle.free_rest else 0)
        | (0b1000 if oracle.cal_known else 0)
    )
    load_id = _LOAD_IDS.index(oracle.day_load) if oracle.day_load in _LOAD_IDS else 0
    mail_flags = (0b0001 if oracle.fresh_mail else 0) | (0b0010 if oracle.mail_known else 0)
    inbox_id = _INBOX_IDS.index(oracle.inbox_load) if oracle.inbox_load in _INBOX_IDS else 0
    return struct.pack(
        _FMT,
        tag_id,
        oracle.moon_phase,
        1 if oracle.sunset_soon else 0,
        temp,
        oracle.moon_illum,
        rhythm_id,
        hours,
        flags,
        load_id,
        mail_flags,
        inbox_id,
    )


def _oracle_from(
    tag_id,
    phase,
    sunset,
    temp,
    illum,
    rhythm_id,
    hours,
    in_meeting,
    meeting_soon,
    day_load,
    free_rest,
    cal_known,
    inbox_load,
    fresh_mail,
    mail_known,
):
    return Oracle(
        weather_tag=_TAG_IDS[tag_id] if tag_id < len(_TAG_IDS) else "clear",
        temp_c=None if temp < -900.0 else temp,
        moon_phase=phase,
        moon_illum=illum,
        sunset_soon=bool(sunset),
        coding_rhythm=_RHYTHM_IDS[rhythm_id] if rhythm_id < len(_RHYTHM_IDS) else "idle",
        hours_since_push=None if hours < 0.0 else hours,
        in_meeting=in_meeting,
        meeting_soon=meeting_soon,
        day_load=day_load,
        free_rest=free_rest,
        cal_known=cal_known,
        inbox_load=inbox_load,
        fresh_mail=fresh_mail,
        mail_known=mail_known,
    )


def _from_cal_fields(tag_id, phase, sunset, temp, illum, rhythm_id, hours, flags, load_id,
                     mail_flags=0, inbox_id=0):
    return _oracle_from(
        tag_id,
        phase,
        sunset,
        temp,
        illum,
        rhythm_id,
        hours,
        bool(flags & 0b0001),
        bool(flags & 0b0010),
        _LOAD_IDS[load_id] if load_id < len(_LOAD_IDS) else "light",
        bool(flags & 0b0100),
        bool(flags & 0b1000),
        _INBOX_IDS[inbox_id] if inbox_id < len(_INBOX_IDS) else "clear",
        bool(mail_flags & 0b0001),
        bool(mail_flags & 0b0010),
    )


def unpack(blob):
    """Unpack binary form back into an Oracle. Older blobs default the missing fields."""
    if len(blob) >= SIZE:
        fields = struct.unpack(_FMT, blob[:SIZE])
        return _from_cal_fields(*fields)
    if len(blob) >= SIZE_CAL:
        fields = struct.unpack(_FMT_CAL, blob[:SIZE_CAL])
        return _from_cal_fields(*fields)  # email -> default clear/unknown
    tag_id, phase, sunset, temp, illum, rhythm_id, hours = struct.unpack(_FMT_OLD, blob[:SIZE_OLD])
    return _oracle_from(
        tag_id, phase, sunset, temp, illum, rhythm_id, hours,
        False, False, "light", True, False, "clear", False, False,
    )
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest tests/test_oracle_client.py -v`
Expected: PASS (existing + 4 new). Existing tests still pass (email fields default clear/unknown when no `inbox` block).

- [ ] **Step 7: Lint + commit**

```bash
source .venv/bin/activate
black --line-length 100 slime/oracle.py tests/test_oracle_client.py
ruff check slime/oracle.py tests/test_oracle_client.py
git add slime/oracle.py tests/test_oracle_client.py
git commit -m "feat: parse + cache inbox presence fields on the device oracle"
```

---

## Task 4: Device — inbox mood bias, quips, helpers

**Files:**
- Modify: `slime/oracle.py`, `slime/quips.py`
- Test: `tests/test_oracle_client.py`, `tests/test_quips.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_oracle_client.py`:

```python
from slime.oracle import has_unread, is_inbox_heavy


def test_clear_inbox_makes_it_content():
    o = parse(_with_inbox(load="clear"))
    biased = mood_bias(Mood(60, 50, 50, 30, 40), o)
    assert biased.affection >= 30


def test_flooded_inbox_lowers_energy_not_punishing():
    o = parse(_with_inbox(load="flooded"))
    biased = mood_bias(Mood(60, 50, 80, 30, 40), o)
    assert biased.energy < 80
    assert biased.comfort >= 50


def test_inbox_quip_tags():
    assert quip_tag(parse(_with_inbox(load="clear"))) == "inbox_clear"
    assert quip_tag(parse(_with_inbox(load="busy"))) == "inbox_busy"
    assert quip_tag(parse(_with_inbox(load="flooded"))) == "inbox_flooded"
    assert quip_tag(parse(_with_inbox(load="light", fresh=True))) == "fresh_mail"


def test_inbox_silent_when_unknown():
    assert quip_tag(parse(_payload(["clear"], phase=2))) is None


def test_inbox_helpers():
    assert has_unread(parse(_with_inbox(load="busy"))) is True
    assert has_unread(parse(_with_inbox(load="clear"))) is False
    assert has_unread(parse(_payload(["clear"]))) is False  # mail_known False
    assert is_inbox_heavy(parse(_with_inbox(load="flooded"))) is True
    assert is_inbox_heavy(parse(_with_inbox(load="busy"))) is False
    assert is_inbox_heavy(None) is False
```

Append to `tests/test_quips.py`:

```python
def test_email_pools_present_and_nonempty():
    for tag in ("fresh_mail", "inbox_clear", "inbox_busy", "inbox_flooded"):
        assert tag in QUIPS
        assert len(QUIPS[tag]) >= 1
        assert pick(tag) in QUIPS[tag]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest tests/test_oracle_client.py tests/test_quips.py -v`
Expected: FAIL — `has_unread`/`is_inbox_heavy` missing; email tags/pools missing.

- [ ] **Step 3: Add inbox mood bias**

In `slime/oracle.py` `mood_bias`, insert this block immediately BEFORE the final `return clamp_mood(Mood(**vals))` line:

```python
    if oracle.mail_known:
        if oracle.inbox_load == "clear":
            vals["comfort"] += (72.0 - vals["comfort"]) * rate
            vals["affection"] += (66.0 - vals["affection"]) * rate
        elif oracle.inbox_load == "flooded":
            vals["comfort"] += (76.0 - vals["comfort"]) * rate
            vals["energy"] += (35.0 - vals["energy"]) * rate
        elif oracle.inbox_load == "busy":
            vals["energy"] += (60.0 - vals["energy"]) * rate
        if oracle.fresh_mail:
            vals["curiosity"] += (70.0 - vals["curiosity"]) * rate
```

- [ ] **Step 4: Add inbox quip tags + helpers**

In `slime/oracle.py` `quip_tag`, insert these checks immediately BEFORE the final `return None` line:

```python
    if oracle.mail_known and oracle.fresh_mail:
        return "fresh_mail"
    if oracle.mail_known and oracle.inbox_load == "flooded":
        return "inbox_flooded"
    if oracle.mail_known and oracle.inbox_load == "busy":
        return "inbox_busy"
    if oracle.mail_known and oracle.inbox_load == "clear":
        return "inbox_clear"
```

Add these helpers after `is_in_meeting`:

```python
def has_unread(oracle):
    """True when inbox data is present and there is at least one unread message."""
    return oracle is not None and oracle.mail_known and oracle.inbox_load != "clear"


def is_inbox_heavy(oracle):
    """True when inbox data is present and the inbox is flooded (drives the journal flag)."""
    return oracle is not None and oracle.mail_known and oracle.inbox_load == "flooded"
```

- [ ] **Step 5: Add the quip pools**

In `slime/quips.py`, add these four entries to the `QUIPS` dict (after the calendar pools, still inside the dict literal). Keep each line ≤ ~22 chars so `wrap_quip` keeps them to one line:

```python
    "fresh_mail": (
        "something new arrived",
        "a fresh note for you",
        "the inbox just stirred",
    ),
    "inbox_clear": (
        "all caught up",
        "your inbox is calm",
        "nothing left waiting",
    ),
    "inbox_busy": (
        "a lot landed today",
        "the inbox is busy",
        "messages are stacking",
    ),
    "inbox_flooded": (
        "the inbox is deep today",
        "so much is waiting",
        "i'll keep you company",
    ),
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest tests/test_oracle_client.py tests/test_quips.py -v`
Expected: PASS. Then the full device suite: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q` → all pass (existing quip_tag tests unaffected — email branches are gated on `mail_known`, false for payloads with no inbox block).

- [ ] **Step 7: Lint + commit**

```bash
source .venv/bin/activate
black --line-length 100 slime/oracle.py slime/quips.py tests/test_oracle_client.py tests/test_quips.py
ruff check slime/oracle.py slime/quips.py tests/test_oracle_client.py tests/test_quips.py
git add slime/oracle.py slime/quips.py tests/test_oracle_client.py tests/test_quips.py
git commit -m "feat: inbox mood bias, quips, and has_unread/is_inbox_heavy helpers"
```

---

## Task 5: Device — `statusbar.mail_icon` + tile constants

**Files:**
- Modify: `slime/statusbar.py`
- Test: `tests/test_statusbar.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_statusbar.py`:

```python
Mailbox = namedtuple("Mailbox", ("mail_known", "inbox_load", "fresh_mail"))


def test_mail_icon_states():
    assert statusbar.mail_icon(Mailbox(True, "clear", False)) is None
    assert statusbar.mail_icon(Mailbox(True, "busy", False)) == statusbar.MAIL_UNREAD
    assert statusbar.mail_icon(Mailbox(True, "busy", True)) == statusbar.MAIL_FRESH
    assert statusbar.mail_icon(Mailbox(False, "flooded", True)) is None  # not mail_known
    assert statusbar.mail_icon(None) is None
```

(The `namedtuple` import already exists at the top of `tests/test_statusbar.py`.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest tests/test_statusbar.py -v`
Expected: FAIL — `AttributeError: module 'slime.statusbar' has no attribute 'MAIL_UNREAD'`.

- [ ] **Step 3: Implement**

In `slime/statusbar.py`, after the `WIFI_STALE = 7` line add:

```python
MAIL_UNREAD = 8  # envelope
MAIL_FRESH = 9  # envelope with a dot (arrived recently)
```

And add this function (e.g. after `weather_icon`):

```python
def mail_icon(oracle):
    """Status-bar mail tile index: fresh -> MAIL_FRESH, unread -> MAIL_UNREAD, else None.

    None (hidden) when there's no inbox data or the inbox is clear.
    """
    if oracle is None or not getattr(oracle, "mail_known", False):
        return None
    if oracle.fresh_mail:
        return MAIL_FRESH
    if oracle.inbox_load != "clear":
        return MAIL_UNREAD
    return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest tests/test_statusbar.py -v`
Expected: PASS.

- [ ] **Step 5: Lint + commit**

```bash
source .venv/bin/activate
black --line-length 100 slime/statusbar.py tests/test_statusbar.py
ruff check slime/statusbar.py tests/test_statusbar.py
git add slime/statusbar.py tests/test_statusbar.py
git commit -m "feat: add statusbar mail_icon (envelope / fresh-mail tile)"
```

---

## Task 6: Asset — two envelope tiles in `statusicons.bmp`

**Files:**
- Modify: `assets/make_assets.py`
- Asset (generated): `assets/statusicons.bmp`

The sheet grows from 8 to 10 tiles (96×12 → 120×12). New tiles: `8` envelope (unread), `9` envelope-with-dot (fresh). Indices MUST match `statusbar.MAIL_UNREAD=8` / `MAIL_FRESH=9`.

- [ ] **Step 1: Bump the tile count**

In `assets/make_assets.py` `_status_icons`, change:

```python
    n, sz = 8, 12
```
to:
```python
    n, sz = 10, 12
```
and update the docstring first line to:
```python
    """10 grayscale 12x12 tiles: sun, cloud, rain, storm, heat, moon, wifi-live, wifi-stale,
    mail-unread, mail-fresh."""
```

- [ ] **Step 2: Draw the two envelope tiles**

In `_status_icons`, immediately BEFORE the `img.save("assets/statusicons.bmp")` line, add:

```python
    # 8 mail-unread: envelope (body + flap)
    d.rectangle([ox(8) + 1, 3, ox(8) + 10, 9], outline=BLACK, fill=GRAY)
    d.line([ox(8) + 1, 3, ox(8) + 6, 7], fill=BLACK)
    d.line([ox(8) + 10, 3, ox(8) + 6, 7], fill=BLACK)

    # 9 mail-fresh: same envelope + a filled dot (new arrival)
    d.rectangle([ox(9) + 1, 4, ox(9) + 9, 10], outline=BLACK, fill=GRAY)
    d.line([ox(9) + 1, 4, ox(9) + 5, 7], fill=BLACK)
    d.line([ox(9) + 9, 4, ox(9) + 5, 7], fill=BLACK)
    d.ellipse([ox(9) + 8, 0, ox(9) + 12, 4], fill=BLACK)
```

- [ ] **Step 3: Generate and verify**

```bash
source .venv/bin/activate
python3 assets/make_assets.py
python3 -c "from PIL import Image; im=Image.open('assets/statusicons.bmp'); print(im.size, im.mode)"
```
Expected: prints `wrote assets/statusicons.bmp (120x12, 10 frames)` and `(120, 12) P`.

- [ ] **Step 4: Keep the tree clean, then commit**

Running the generator also re-saves `slime.bmp` / `accents.bmp`. If `git status` shows them modified (Pillow re-encode), restore them so only the icon sheet + generator change:

```bash
git checkout -- assets/slime.bmp assets/accents.bmp   # only if they appear modified
black --line-length 100 assets/make_assets.py
ruff check assets/make_assets.py
git add assets/make_assets.py assets/statusicons.bmp
git commit -m "feat: add envelope (mail) tiles to statusicons.bmp"
```
Confirm `git status` is clean afterward (no stray modified bmp files).

---

## Task 7: Device — render the mail tile in `display.py`

**Files:**
- Modify: `slime/display.py`

Device-only adapter (cannot import on host). Gate: `python3 -c "import ast; ast.parse(open('slime/display.py').read()); print('ok')"`. READ `display.py` first. The bar's right group has `_bar_temp` (right-anchored at `w-72`), `_weather` tile (`x=w-70`), `_bar_batt` (`w-18`), `_wifi` (`w-14`). You add a `_mail` tile just left of the temp text.

- [ ] **Step 1: Construct the mail tile in `__init__`**

In `slime/display.py` `__init__`, immediately AFTER the `self._bar_temp` block (the `self._root.append(self._bar_temp)` line) and BEFORE the divider block, add:

```python
        self._mail = displayio.TileGrid(
            self._icons_bmp,
            pixel_shader=self._icons_bmp.pixel_shader,
            width=1,
            height=1,
            tile_width=12,
            tile_height=12,
        )
        self._mail.x = w - 110  # left of the temp text; first-guess, tuned on-device
        self._mail.y = 2
        self._mail_hidden = True
```

- [ ] **Step 2: Add `mail_icon` to `render_frame`**

Change `render_frame`'s signature to add a keyword-only `mail_icon=None` (after `wifi_state=None`):

```python
    def render_frame(
        self,
        frame_index,
        quip_text="",
        *,
        time_str=None,
        date_str=None,
        temp_str=None,
        battery_str=None,
        weather_icon=None,
        wifi_state=None,
        mail_icon=None,
    ):
```

And in its body, after the `self._set_tile(self._wifi, "_wifi_hidden", wifi_state)` line add:

```python
        self._set_tile(self._mail, "_mail_hidden", mail_icon)
```

- [ ] **Step 3: Add `mail_icon` to `render_sleep`**

Change `render_sleep`'s signature to add `mail_icon=None` (after `wifi_state=None`), and pass it through to the inner `render_frame(...)` call (add `mail_icon=mail_icon,` to that call's kwargs).

- [ ] **Step 4: Offline gate + lint + commit**

```bash
python3 -c "import ast; ast.parse(open('slime/display.py').read()); print('ok')"
source .venv/bin/activate
black --line-length 100 slime/display.py
ruff check slime/display.py
git add slime/display.py
git commit -m "feat: render status-bar mail tile (envelope / fresh)"
```
Expected: `ok`, clean lint.

---

## Task 8: Device — wire mail icon + journal flag in `code.py` and `journal.py`

**Files:**
- Modify: `code.py`, `slime/journal.py`
- Test: `tests/test_journal.py`

- [ ] **Step 1: Journal heavy-inbox text — failing test**

Append to `tests/test_journal.py` (create the file with this content if it does not exist):

```python
from slime.journal import generate_entry, pack_record, unpack_record


def _rec(flags):
    return unpack_record(pack_record(20000, 2, 1, flags, 3))


def test_heavy_inbox_closing():
    line = generate_entry(_rec(0b100), 5, lambda opts: opts[0])
    assert "inbox" in line.lower()


def test_busy_still_wins_over_inbox():
    # bit1 (busy) takes precedence over bit2 (inbox)
    line = generate_entry(_rec(0b110), 5, lambda opts: opts[0])
    assert "busy" in line.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest tests/test_journal.py -v`
Expected: FAIL — the inbox closing isn't produced yet.

- [ ] **Step 3: Add the heavy-inbox closing**

In `slime/journal.py` `generate_entry`, replace the closing block:

```python
    if flags & 0b10:
        closing = "you seemed busy"
    else:
        closing = choice((_MOOD_WORD.get(mood_dom, "i watched the clouds"),))
```

with:

```python
    if flags & 0b10:
        closing = "you seemed busy"
    elif flags & 0b100:
        closing = "the inbox ran deep"
    else:
        closing = choice((_MOOD_WORD.get(mood_dom, "i watched the clouds"),))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest tests/test_journal.py -v`
Expected: PASS.

- [ ] **Step 5: Set the journal flag in `code.py`**

In `code.py` `_maybe_journal`, change the `record = journal.pack_record(...)` flags argument from:

```python
        (0b1 if "double_tap" in events else 0) | (0b10 if oracle_mod.is_busy(oracle) else 0),
```

to:

```python
        (
            (0b1 if "double_tap" in events else 0)
            | (0b10 if oracle_mod.is_busy(oracle) else 0)
            | (0b100 if oracle_mod.is_inbox_heavy(oracle) else 0)
        ),
```

- [ ] **Step 6: Add the mail icon to `_status_fields` in `code.py`**

In `code.py` `_status_fields`, add `"mail_icon": statusbar.mail_icon(oracle),` to the returned dict (e.g. after the `"weather_icon"` entry):

```python
        "weather_icon": statusbar.weather_icon(oracle),
        "mail_icon": statusbar.mail_icon(oracle),
        "wifi_state": wifi_state,
```

(`_render_frame` already forwards `**(fields or {})` to `display.render_frame`, so the new `mail_icon` field flows through automatically. The sleep path uses an explicit subset and does not need the mail icon — render_sleep's `mail_icon` defaults to None.)

- [ ] **Step 7: Offline gate + full host suite**

```bash
python3 -c "import ast; ast.parse(open('code.py').read()); print('ok')"
source .venv/bin/activate
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q -p no:cacheprovider
```
Expected: `ok`, all host tests pass.

- [ ] **Step 8: Lint + commit**

```bash
black --line-length 100 code.py slime/journal.py tests/test_journal.py
ruff check code.py slime/journal.py tests/test_journal.py
git add code.py slime/journal.py tests/test_journal.py
git commit -m "feat: wire mail status icon + heavy-inbox journal flag"
```

---

## Self-Review

**Spec coverage:**
- IMAP read-only source → Task 1 `fetch_counts` + Task 2 `IMAP_*` config. ✓
- `summarize` buckets (clear/light/busy/flooded) + fresh-mail 60-min window → Task 1. ✓
- Block only when configured; omitted otherwise → Task 2 `_inbox()` returns None, `build` omits. ✓
- Compose env passthrough + .env docs (app password note) → Task 2 Step 6. ✓
- Device `Oracle` +fields, parse, cache format (+backward compat for old AND calendar-era blobs), state stays v3 → Task 3. ✓
- Mood bias (clear/flooded/busy/fresh), quips, `has_unread`/`is_inbox_heavy`, gated on `mail_known` → Task 4. ✓
- Status-bar envelope: `mail_icon` (Task 5), tiles (Task 6), display render (Task 7), wired in `_status_fields` (Task 8). ✓
- Journal heavy-inbox flag → Task 8 (journal text + flag bit). ✓
- Privacy (only buckets leave Pi; only INTERNALDATE read) → Tasks 1–2. ✓
- Offline-first / idle fallback → Task 2 None-on-failure, Task 3 absent-block + old-blob defaults. ✓
- Testing both tiers → Tasks 1–5, 8 host tests; Tasks 6–7 run/visual. ✓

**Placeholder scan:** No TBD/TODO; every code step has full code. ✓

**Type consistency:** Wire key `inbox_load`/`fresh_mail` map to device `Oracle.inbox_load`/`fresh_mail`; device adds `mail_known`. `_INBOX_IDS = ("clear","light","busy","flooded")` consistent across summarize, parse, pack/unpack, mood_bias, quip_tag, mail_icon. `build(weather, moon, presence, calendar=None, inbox=None, ts=0)` matches `main.py` keyword call and the existing `build(..., ts=...)` test. `mail_icon` returned by `statusbar` (Task 5) and consumed by `display.render_frame` (Task 7) + `_status_fields` (Task 8). `MAIL_UNREAD=8`/`MAIL_FRESH=9` match the generated tile order (Task 6). `is_inbox_heavy`/`has_unread` defined Task 4, used Tasks 7/8. Journal flag bit `0b100` set in Task 8 Step 5 matches the read in Task 8 Step 3. ✓
