# Long-term Memory (Phase 2c-ii) — Design

**Date:** 2026-06-20
**Status:** Approved (design); pending spec review

## Goal

Give the pet episodic continuity: it remembers notable moments and brings them back — woven
into its LLM dreams (rich, server-side recall) and occasionally voiced as a waking "remember"
quip (offline, device-side milestones). A hybrid memory: a long episodic log on the home
server + a compact milestone identity in device NVM.

## Motivation

The pet already keeps rolling stats (first-met, longest absence, boops, visits, artifacts) and
a 48-day journal ring, but it has no *episodic recall* — it can't say "the night the storm
came." 2c-ii adds that, deepening the dreams built in 2c-i and making the companion feel like
it has a past. It stays privacy-first and offline-first: only derived buckets/tones are
remembered, and absence of memory degrades silently.

## Decisions (locked)

- **Memory home:** **hybrid**. The home server holds the long episodic log (the rich history
  that feeds dreams); the device holds a compact milestone bitmask in NVM (its core identity,
  driving offline waking quips).
- **Surfacing:** **dreams + waking quips**. Server recall is woven into the dream prompt;
  device milestones occasionally surface as a waking memory quip.
- **Privacy:** only derived buckets/tone-words are recorded — same boundary as the rest. The
  episodic log lives in the user's own Docker volume; no event content.

## Architecture

Two halves under one theme, built as two sequential plans on one branch:
- **Plan A — server episodic memory:** `POST /remember`, a JSONL log, pure `recall`, and dream
  integration. Extends 2c-i directly.
- **Plan B — device milestones:** State v4 milestone bitmask, pure `milestones`, a memory quip
  pool, and `POST /remember` posting on a new day.

### Plan A — Server episodic memory

**`server/app/memory.py` (new):**
- `append_episode(path, episode, cap)` — append `episode` (a dict) as one JSON line to `path`,
  keeping at most `cap` most-recent lines. Creates the file/dir as needed; thin I/O.
- `load_episodes(path) -> list[dict]` — read all JSON lines (tolerates a missing/corrupt file →
  []). Thin I/O.
- `episode_from(context, now_iso) -> dict` — **pure**: reduce a posted day-context to a compact
  episode `{date, weather, moon, presence, calendar, inbox, tone}` (only derived fields).
- `recall(episodes, choice) -> str | None` — **pure**: filter to *notable* episodes (weather in
  storm/monsoon/extreme_heat/rain, moon new/full, inbox flooded, presence quiet/heavy, calendar
  heavy), pick one via `choice`, and render a short recall phrase from a per-kind template
  (e.g. storm → "the day a desert storm rolled in"; full moon → "a night under the full moon").
  Returns None when there are no notable episodes.

**`POST /remember` (in `main.py`):** accepts the device's day-context JSON, builds an episode
via `episode_from(body, datetime.now().isoformat())`, appends it to `config.MEMORY_PATH`
(bounded by `config.MEMORY_CAP`), returns `{"ok": True}`. Honors `ORACLE_TOKEN`. Never 500s
(append failure → `{"ok": False}`).

**Dream integration:** `POST /dream` loads episodes, computes `recall(...)`, and—when non-empty—
adds a `memory` key to the context passed to `llm.generate_dream`. `llm.build_prompt` gains an
optional memory line: when `context["memory"]` is set, append "You may gently reference this
remembered moment: <memory>." to the user prompt. (build_prompt stays pure + tolerant.)

**Config + compose:** `MEMORY_PATH` (default `/data/memory.jsonl`), `MEMORY_CAP` (default 365).
`docker-compose.yml` mounts a named volume at `/data` so the log persists across rebuilds;
`.env.example` documents the two vars (append).

### Plan B — Device milestones + waking quips

**State v4 (`slime/persistence.py`, `slime/state.py`):** add a `milestones` int field to `State`
and the NVM blob → `_FORMAT_V4 = "<B5ffffIfIIII"` (v3 + milestones I). `unpack` migrates v3→v4
(milestones default 0); `default_state` includes `milestones=0`. `BLOB_SIZE` becomes v4 size
(the journal ring/oracle-cache offsets already sit well past the blob, so they are unaffected —
verify the ring start `((BLOB_SIZE//16)+1)*16` still clears the new blob).

**`slime/milestones.py` (new, pure):**
- `MILESTONES` — ordered `(bit, recall_line)` definitions, e.g. `FIRST_STORM`, `FULL_MOON_NIGHT`,
  `BONDED` (tier ≥ 3), `COLLECTOR` (all 8 artifacts), `FAITHFUL` (longest_absence over a
  threshold), `NIGHT_OWL` (a deep-sleep dream).
- `evaluate(flags, oracle, state, tier) -> int` — returns `flags` with newly-met bits set
  (weather storm/monsoon → FIRST_STORM; moon_phase == 4 → FULL_MOON_NIGHT; tier ≥ 3 → BONDED;
  all artifacts → COLLECTOR; longest_absence ≥ threshold → FAITHFUL). Pure; never clears bits.
- `memory_quip(flags, choice) -> str | None` — pick one unlocked milestone's recall line, or
  None when nothing is unlocked yet.

**`slime/quips.py`:** no new pool needed — `milestones.memory_quip` returns full lines. (Quip
selection in `code.py` calls it directly.)

**`code.py`:**
- After loading state + oracle each cycle, `state = evolve(state, milestones=milestones.evaluate(
  state.milestones, oracle, state, friendship.tier(state.familiarity)))`, then persist.
- In the render path, occasionally (a low-probability roll via `_choice`, only when not in a
  weather/calendar/inbox-driven quip) show `milestones.memory_quip(state.milestones, _choice)`
  instead of the usual quip.
- `_maybe_journal`: on a new journal day, also `netmemory.post(dreams.dream_context(...))` so the
  server log grows ~daily.

**`slime/netmemory.py` (new adapter):** `post(context)` — POST the context to `<ORACLE_HOST>/
remember` (scheme-aware like netdream/netoracle, optional bearer), fire-and-forget, never raises.

## Data Flow

```
new journal day ─> netmemory.post(dream_context) ─POST /remember─> memory.episode_from ─> append JSONL log
wake ─> POST /dream ─> memory.recall(load_episodes) ─> context["memory"] ─> build_prompt ─> richer dream
each cycle ─> milestones.evaluate(flags, oracle, state, tier) ─> state.milestones (NVM v4)
            └─> occasionally ─> milestones.memory_quip ─> waking "remember" quip (offline)
```

## Error Handling / Offline-First

- `/remember` and `netmemory.post` failures are silent (memory just doesn't grow that day).
- `recall` returns None on an empty/notable-less log → the dream is generated without a memory
  hint (unchanged 2c-i behavior).
- `milestones` are derived purely on-device and persist in NVM; with no oracle they simply don't
  advance. v4 migration defaults milestones to 0 for existing devices.
- The memory JSONL is bounded (cap) and tolerates corruption (load → []).

## Testing

**Server (host pytest):**
- `episode_from`: reduces a context to the compact episode (only derived fields).
- `recall`: returns a phrase for a notable episode; None when none are notable; uses injected
  `choice` deterministically; each notable kind renders its phrase.
- `append_episode`/`load_episodes`: round-trip; cap trims to most-recent; missing/corrupt file → [].
- `build_prompt`: includes the memory line when `context["memory"]` is set, omits it otherwise.
- `/remember` (monkeypatched store path / append): returns ok; honors token. `/dream` injects a
  recalled memory (monkeypatched recall) into generate_dream's context.

**Device (host pytest):**
- `persistence` v4 pack/unpack round-trip + v3→v4 migration (milestones default 0) + v2/v1 still
  migrate; `default_state` has milestones 0.
- `milestones.evaluate`: sets the right bits per oracle/state/tier; never clears; idempotent.
- `milestones.memory_quip`: a line for an unlocked flag; None when flags == 0.
- `netmemory` is a thin device-only adapter (not host-imported); on-device verified.

**On-device:** new-day posts grow the server log; dreams begin referencing remembered moments;
a waking memory quip surfaces occasionally; with the server down, dreams/quips degrade to
2c-i / non-memory behavior.

## Scope Guard (YAGNI)

- No database (append-bounded JSONL); no memory UI/analytics; no editing/forgetting controls.
- Only derived buckets/tones recorded; no event content.
- Milestone set is small and fixed; no user-defined milestones.
- One memory file; no per-source partitioning.

## Files Touched

**Plan A:** Create `server/app/memory.py`, `server/tests/test_memory.py`. Modify
`server/app/config.py`, `server/app/main.py`, `server/app/llm.py` (+ `server/tests/test_llm.py`,
`server/tests/test_main.py`), `server/docker-compose.yml`, `server/.env.example`.

**Plan B:** Create `slime/milestones.py` (+ `tests/test_milestones.py`), `slime/netmemory.py`.
Modify `slime/persistence.py`, `slime/state.py` (+ `tests/test_state.py`/`tests/test_persistence.py`),
`code.py`.
