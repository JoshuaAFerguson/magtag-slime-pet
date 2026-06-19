# Email Presence (Phase 2b-iii) — Design

**Date:** 2026-06-19
**Status:** Approved (design); pending spec review

## Goal

Give the Slime Pet ambient awareness of the user's inbox: how loaded it is and whether
mail just arrived — surfaced as mood bias, quips, a journal flag, and a status-bar envelope
glyph. Only derived buckets leave the home server; no sender, subject, or body ever reaches
the device.

## Motivation

The pet already blends weather, moon, GitHub coding-rhythm, and calendar into its mood and
voice via the home oracle. Email is the third presence signal in the same mold: it lets the
companion be calm and proud at inbox-zero, sympathetic (not punishing) on a flooded day, and
gently attentive when something new lands — without ever becoming a notifier.

## Decisions (locked)

- **Data source:** **IMAP, read-only**, authenticated with an app password. Works with
  Gmail (`imap.gmail.com` + app password) or any IMAP provider. Implemented with Python's
  stdlib `imaplib` (no new dependency).
- **Signals (derived, privacy-safe):**
  - `inbox_load`: `clear` (0 unread) / `light` (1–10) / `busy` (11–30) / `flooded` (31+)
  - `fresh_mail`: an unread message arrived within the last ~60 minutes
- **Manifestation:** mood bias + email quips + journal flag + **status-bar envelope glyph**.
- **Privacy:** only the two buckets are serialized — never senders, subjects, bodies, or
  counts beyond the bucket.

## Architecture

The two-tier split is preserved. The home server (FastAPI, Docker) does all IMAP I/O and
reduces it to buckets; the device consumes only the buckets, caches them in NVM, and reacts
offline-first. Pure reduction logic is host-tested on both tiers, mirroring
`github.summarize` / `calendar.summarize` and the device `oracle.parse`.

### Server: `server/app/inbox.py` (new)

Named `inbox.py` deliberately — `email.py` and `mailbox.py` would shadow stdlib modules.

- `fetch_counts(host, user, password, now) -> (unread, newest_unseen_epoch)` — impure, thin:
  `imaplib.IMAP4_SSL(host)`, `login(user, password)`, `select("INBOX", readonly=True)`,
  `search(None, "UNSEEN")` for the count, and `fetch` of the newest unseen message's
  `INTERNALDATE` (parsed to a UTC epoch) for freshness. Returns `(0, None)` when there are
  no unseen messages. Logs out in a `finally`. Reads **no** body/header content beyond
  `INTERNALDATE`.
- `summarize(unread, newest_unseen_epoch, now) -> dict` — **pure**:
  ```python
  {
      "inbox_load": "clear" | "light" | "busy" | "flooded",
      "fresh_mail": bool,   # newest_unseen within _FRESH_MIN minutes of now
  }
  ```
  Constants: `_LIGHT_MAX = 10`, `_BUSY_MAX = 30`, `_FRESH_MIN = 60`. `inbox_load` = `clear`
  when `unread == 0`, `light` when `<= 10`, `busy` when `<= 30`, else `flooded`.
  `fresh_mail` is true only when `unread > 0` and `newest_unseen_epoch` is within
  `_FRESH_MIN` minutes of `now`.

### Server: wiring

- `server/app/config.py`: add `IMAP_HOST`, `IMAP_USER`, `IMAP_PASSWORD` (all default `""`).
- `server/app/main.py`: a `_inbox()` helper mirroring `_calendar()` — returns `None` (block
  omitted) when any of host/user/password is unset, or on any exception; otherwise
  `inbox.summarize(*inbox.fetch_counts(...), now)`.
- `server/app/oracle.py`: `build(weather, moon, presence, calendar=None, inbox=None, ts=0)`
  adds an `"inbox"` key only when `inbox is not None`.
- `server/docker-compose.yml`: add `IMAP_HOST`/`IMAP_USER`/`IMAP_PASSWORD` to the
  `environment:` block via `${...:-}` interpolation (compose only passes listed vars — the
  gap that initially hid the calendar URL).
- `server/.env.example`: document the three IMAP vars (and, for Gmail, that an **app
  password** is required, not the account password).

### Device: `slime/oracle.py` (extend)

- `Oracle` gains three fields: `inbox_load` (str: clear/light/busy/flooded), `fresh_mail`
  (bool), `mail_known` (bool — true only when the `inbox` block is present, gating all email
  behavior exactly like `cal_known`).
- `parse` reads `payload["inbox"]` (absent → `mail_known=False`, defaults clear/false).
- pack/unpack: extend the cache struct. The current format is `<BBBffBfBB` (calendar added a
  flags byte + load byte). Email adds the `fresh_mail` + `mail_known` bits into a **second
  flags byte** and an **inbox-load byte** → new format `<BBBffBfBBBB`. The persistent state
  blob stays v3 (oracle cache is its own ephemeral slot). A shorter (older) blob still
  unpacks, defaulting the email fields to clear/unknown.
- `mood_bias` (gated on `mail_known`): `clear` → comfort/affection up (content & proud);
  `flooded` → comfort up, energy down (sympathetic/cozy, never punishing); `fresh_mail` →
  curiosity up (attentive); `busy` → a mild restlessness (small energy bump).
- `quip_tag`: new tags slotted into the priority chain — `fresh_mail` → `"fresh_mail"`;
  `inbox_load == "flooded"` → `"inbox_flooded"`; `inbox_load == "busy"` → `"inbox_busy"`;
  `inbox_load == "clear"` → `"inbox_clear"`. (Exact ordering relative to weather/calendar/
  coding fixed in the plan; calendar meeting states keep priority over email.)
- `has_unread(oracle) -> bool` — small helper (true when `mail_known` and
  `inbox_load != "clear"`) for the status-bar glyph and the journal flag.

### Device: `slime/quips.py`

Add four quip pools: `fresh_mail`, `inbox_clear`, `inbox_busy`, `inbox_flooded` (several
short lines each, ≤ ~22 chars so the existing `wrap_quip` keeps them tidy).

### Device: status-bar envelope glyph

- Add **two tiles** to `assets/statusicons.bmp` (via `make_assets.py`): an envelope (unread)
  and an envelope-with-dot (fresh mail). New `statusbar` tile-index constants
  `MAIL_UNREAD`, `MAIL_FRESH`, plus `mail_icon(oracle) -> int | None` returning `MAIL_FRESH`
  when `fresh_mail`, else `MAIL_UNREAD` when `has_unread`, else `None` (hidden).
- `slime/display.py`: a new lazily-shown 12×12 tile in the bar's **right group**, just left
  of the temperature. `render_frame` gains a `mail_icon` kwarg (None → hidden). Exact x is
  tuned on-device (the right group is full; positions are first-guesses).

### Device: journal

`code.py` `_maybe_journal` already encodes a "busy" flag bit from `oracle_mod.is_busy`. Add a
heavy-inbox bit using `oracle_mod.has_unread` + flooded check (an `is_inbox_heavy(oracle)`
helper) so a flooded day is remembered, regenerated into journal text.

## Data Flow

```
IMAP INBOX (read-only) ─> inbox.fetch_counts ─> (unread, newest_unseen_epoch)
        └─> inbox.summarize(now) ─> {inbox_load, fresh_mail}
              └─> oracle.build(..., inbox, ts) ─> GET /oracle JSON (block omitted if unconfigured)
                                   │
   device netoracle.fetch ─> oracle.parse ─> Oracle(+inbox_load/fresh_mail/mail_known) ─> NVM cache
        ├─> oracle.mood_bias ─> mood
        ├─> oracle.quip_tag  ─> voice
        ├─> oracle.mail_icon ─> status-bar envelope tile
        └─> oracle.is_inbox_heavy ─> code.py journal flag
```

## Error Handling / Offline-First

- Missing IMAP config or any IMAP/parse failure → server omits the `inbox` block → device
  `mail_known=False` → zero email behavior. Existing device tests (no block) unaffected.
- Device offline → cached oracle (email fields survive pack/unpack); old-format blob → email
  fields default clear/unknown.
- `imaplib` calls wrapped so the server endpoint degrades gracefully (mirrors `_presence`/
  `_calendar`); a `finally` logout avoids leaked IMAP sessions.

## Testing

**Server (CI `server` job, host pytest):**
- `inbox.summarize` (pure): bucket thresholds (0 → clear, 10 → light, 11/30 → busy, 31 →
  flooded), freshness window edge (within/just outside 60 min), `fresh_mail=False` when
  `unread==0`, empty → clear/false.
- `main`/`oracle.build`: payload includes an `inbox` block when configured (monkeypatched
  `fetch_counts`); omitted when IMAP env unset.

**Device (CI `check` job, host pytest):**
- `oracle.parse` reads the inbox block (and defaults clear/unknown when absent).
- pack/unpack round-trip including the new email bits; old-format blob → clear/unknown.
- `mood_bias` per signal; `quip_tag` returns the email tags in the defined priority;
  `mail_icon` / `has_unread` / `is_inbox_heavy` behavior.
- New quip pools non-empty.
- `make_assets` emits the two new tiles (image dimension check).

**On-device:** envelope glyph appears with unread / fresh mail; quips and mood shift; with no
IMAP config the pet behaves exactly as before.

## Scope Guard (YAGNI)

- No OAuth, no Gmail API, no message-content reading, no per-folder logic (INBOX only), one
  mailbox.
- No new device **state** fields (state stays v3); only the ephemeral oracle cache grows.
- No notifications/alerts — ambient mood/voice/glyph only.

## Files Touched

- Create: `server/app/inbox.py`, `server/tests/test_inbox.py`
- Modify: `server/app/config.py`, `server/app/main.py`, `server/app/oracle.py`,
  `server/docker-compose.yml`, `server/.env.example`, `server/tests/test_main.py`,
  `server/tests/test_oracle.py`
- Modify: `slime/oracle.py` (+ `tests/test_oracle_client.py`), `slime/quips.py`
  (+ `tests/test_quips.py`), `slime/statusbar.py` (+ `tests/test_statusbar.py`),
  `slime/display.py`, `assets/make_assets.py`, `assets/statusicons.bmp` (regenerated),
  `code.py`
