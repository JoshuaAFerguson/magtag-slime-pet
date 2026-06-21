# Journal Archive (Phase 2c-iii) — Design

**Date:** 2026-06-21
**Status:** Approved (scope chosen by user); pending plan

## Goal

A calm, read-only web page served by the home oracle that renders the pet's daily journal as
an editorial diary — the pet's own generated sentence per day, plus its derived weather / moon /
presence buckets — newest-first, with light server-side filtering by month and notable kind.
Open on the LAN, no token. This is sub-project 2c-iii of Phase 2c.

## Motivation

The pet already posts a compact episode to the server's episodic memory log each new journal day
(2c-ii). That log is the natural source for a human-readable archive: a quiet place to look back
on the pet's days. 2c-iii surfaces it as a single server-rendered page — no app, no database, no
client JavaScript — in keeping with the slow-technology, offline-first, privacy-first ethos.

## Decisions (locked)

- **Data source: both.** Render the episode buckets the device already posts AND have the device
  also post its generated journal *sentence* per day, so the archive shows the pet's actual words.
- **Presentation: timeline + light filtering.** A single read-only HTML page, newest-first, one
  calm diary card per day, with server-side filters (by month, by notable kind) via query params.
  No client JS framework, no pagination, no charts.
- **Access: open on the LAN.** `GET /journal` needs no token (only derived buckets/prose are
  stored; the server is LAN-only). `POST /remember` stays token-gated.

## Architecture

Additive: server-only, plus one small device tweak so the journal sentence reaches the log.

### Device tweak — post the journal sentence

`code.py` `_maybe_journal` already generates a human-readable journal line
(`journal.generate_entry(...)`) for the on-device journal render. Today it posts only the derived
`dreams.dream_context(...)` to `/remember`. The tweak: generate that line *once* before posting,
include it in the posted context under a `"journal"` key, and reuse it for the on-device render.

The line is derived ambient prose ("you seemed busy", "the inbox ran deep") composed purely from
flag bits — no event content — so the privacy boundary is unchanged.

`server/app/memory.py` `episode_from` gains `"journal": context.get("journal")` (None when absent,
so older posts and the existing tests are unaffected).

### New pure module `server/app/journal_view.py`

- `episode_kind(ep)` — public classifier. `memory.py` currently has a private `_kind(ep)`; expose
  it as `memory.episode_kind` (rename with `_kind = episode_kind` kept as an internal alias used by
  `recall`) and import it here, so classification logic lives in one place.
- `available_months(episodes) -> list[str]` — sorted-descending distinct `YYYY-MM` prefixes of
  episode `date`s (skips episodes with no usable date).
- `present_kinds(episodes) -> list[str]` — distinct notable kinds present, in a stable display order.
- `filter_episodes(episodes, month, kind) -> list` — pure. Keep episodes whose `date` starts with
  `month` (when `month` truthy) and whose `episode_kind` equals `kind` (when `kind` truthy). Unknown/
  empty filter values match nothing extra (an unmatched filter yields an empty list, not an error).
- `entry_text(ep) -> str` — prefer `ep["journal"]` (the posted sentence); else a recall-style phrase
  for `episode_kind(ep)`; else a gentle default ("a quiet, ordinary day").
- `render_page(episodes, month, kind) -> str` — return a complete HTML document. Inline `<style>`,
  no JS, no build step. Sections: a header, a filter strip (month links + kind links built from
  `available_months`/`present_kinds`, each an `<a href="/journal?month=..."/...?kind=...">`, plus an
  "all" reset link), then the filtered episodes newest-first as one diary card each (date heading,
  the entry sentence, small weather/moon marks + tone). Empty result → a friendly "no entries yet"
  (or "nothing matches that filter") message. **Every episode-derived string is `html.escape`d** —
  the data crosses the untrusted `/remember` boundary, so this is the XSS guard.

### New route `GET /journal`

In `main.py`: `GET /journal` → `fastapi.responses.HTMLResponse`. Reads `?month=` / `?kind=` query
params (both optional), loads `memory.load_episodes(config.MEMORY_PATH)`, calls
`journal_view.render_page(...)`, returns the HTML. **No auth.** Wrapped so it never 500s — on any
error (incl. an empty/missing log) it still returns a valid page (empty state). `POST /remember`
remains token-gated and unchanged.

## Visual Direction

Warm-paper editorial diary — not a default card grid. Serif display date headings, generous
vertical rhythm, one calm card per day, small inline-SVG weather/moon marks, a quiet filter strip.
Design tokens as CSS custom properties (paper background, ink text, a single restrained accent).
Microsite budgets: CSS < 15kb inline, **zero JS**. Qualities targeted: clear hierarchy through
scale contrast, intentional spacing rhythm, typographic character, designed link hover/focus states,
editorial composition (not a uniform grid).

## Data Flow

```
new journal day ─> code.py _maybe_journal builds ctx = dream_context(...) + {"journal": line}
                 ─netmemory.post─> POST /remember ─> episode_from(ctx) keeps "journal" ─> JSONL log
browser GET /journal?month=&kind= ─> load_episodes ─> journal_view.filter_episodes
                                   ─> journal_view.render_page (escaped HTML) ─> HTMLResponse
```

## Error Handling / Offline-First

- `GET /journal` never 500s: empty/missing/corrupt log → a valid empty-state page (`load_episodes`
  already returns `[]` on a missing file and skips corrupt lines).
- Unknown/empty filter params render an empty result with a "nothing matches" note, not an error.
- The device tweak rides the existing fire-and-forget `netmemory.post` (never raises); if the post
  fails, that day simply isn't archived — unchanged 2c-ii behavior.
- All rendered episode strings are HTML-escaped.

## Testing

**Server (host pytest):**
- `episode_from`: preserves the `journal` line; `None` when absent (existing tests unaffected).
- `episode_kind`: same classifications as the old `_kind` (move/alias does not change behavior).
- `filter_episodes`: by month; by kind; by both; an unmatched filter → `[]`.
- `available_months` / `present_kinds`: distinct, ordered, tolerate missing dates/kinds.
- `entry_text`: prefers the posted journal line; falls back to a kind phrase; then the default.
- `render_page`: includes the entries; **escapes** an injected `<script>` in a journal line;
  orders newest-first; renders the filter nav; renders the empty state.
- `GET /journal`: returns 200 `text/html` with **no** auth; honors `?month=`/`?kind=`; empty log
  still 200.

**Device (host pytest + on-device):**
- The `_maybe_journal` change is device-only (`code.py`), gated via `ast.parse`. The posted-context
  shape (`"journal"` key) is covered by the server `episode_from` test. On-device: confirm a new day
  posts the sentence and `GET /journal` shows it.

## Scope Guard (YAGNI)

- No database (reuses the bounded JSONL log), no client JS, no charts/stats/streaks, no pagination.
- No auth/edit/delete on the page; read-only.
- One page, server-rendered. Filtering is month + kind only.
- Only derived buckets + the pet's derived prose are stored/shown; no event content.

## Files Touched

**Create:** `server/app/journal_view.py`, `server/tests/test_journal_view.py`.
**Modify:** `server/app/memory.py` (expose `episode_kind`; `episode_from` keeps `journal`),
`server/app/main.py` (+ `GET /journal`), `server/tests/test_memory.py`, `server/tests/test_main.py`,
`code.py` (`_maybe_journal` posts the journal line).
