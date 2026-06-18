# Slime Pet — Phase 2b-i: GitHub Presence (Design)

**Date:** 2026-06-18
**Status:** Approved (design)
**Scope:** Phase 2b-i — the first personal-summary source: a privacy-safe "coding rhythm" signal
derived from GitHub activity, folded into the existing oracle.
**Builds on:** Phase 2a (the weather+moon oracle, server + device client).

---

## Context

Phase 2b adds personal summaries so the slime "notices your day." It decomposes by auth complexity:
**2b-i GitHub** (Personal Access Token — simplest), 2b-ii Calendar (Google OAuth), 2b-iii Email
(IMAP/OAuth). This spec is **2b-i**, which also establishes the reusable summaries pipeline
(server source → privacy-safe signal → device mood bias + journal/quip).

Governing principle (from the vision): the slime **experiences your day, never reports it**.
Personal data becomes a derived *signal*; repo names, commit messages, and any content **never leave
the Pi** or appear on screen.

## Locked Decisions

| Area | Choice |
|---|---|
| First source | GitHub activity via a Personal Access Token (no OAuth) |
| Transport | Extend the existing `GET /oracle` with a `presence` block (single device fetch) |
| Manifestation | **Blend**: heavy activity → independent-but-proud; long quiet gap → attentive |
| Privacy | PAT and all content stay server-side; only a derived level + hours-since-push reach the device |
| Persistence | Oracle NVM cache format extends; **state stays v3** (cache is its own ephemeral slot) |

---

## Architecture

Extend the Phase 2a oracle on both tiers — no new endpoint, no new device fetch.

### Server (`server/`)
- New `app/github.py`: `fetch_events(client)` (PAT-authenticated GitHub API call, side-effecting,
  not unit-tested) and `summarize(events, now)` (**pure** → presence signal).
- `app/config.py` gains `GITHUB_USER`, `GITHUB_TOKEN`.
- `app/oracle.py` / `app/main.py`: fold a `presence` block into `/oracle`, derived server-side and
  wrapped so any GitHub failure (or missing token) yields `presence = {"coding_rhythm": "idle",
  "hours_since_push": None}` without affecting weather/moon.

### Device (`slime/`)
- `slime/oracle.py`: `Oracle` gains `coding_rhythm` (str) and `hours_since_push` (float|None);
  `parse` reads the `presence` block; `mood_bias` blends presence with weather/moon; new
  presence `quip_tag`s; `pack`/`unpack` extend for the cache.
- `slime/quips.py`: presence quip pools.
- `slime/journal.py`: a "busy day" flag bit and a matching entry phrase.
- `code.py`: presence already arrives via the existing `_load_oracle` fetch — wiring sets the
  journal busy flag and relies on the extended `mood_bias`.

## The `/oracle` presence block

```json
"presence": {"coding_rhythm": "heavy", "hours_since_push": 1.5}
```
- `coding_rhythm` ∈ {`idle`, `light`, `heavy`} from push/commit counts in the last 24h.
- `hours_since_push` — hours since the most recent push (or `null` if none recently); drives the
  "attentive after a long quiet gap" behavior.

## Server details

- `github.py.summarize(events, now)` (pure): counts `PushEvent` commits in the last 24h →
  `heavy` (≥ a busy threshold), `light` (≥ 1), else `idle`; computes `hours_since_push` from the
  newest push event. Thresholds are named constants.
- `github.py.fetch_events(client)`: `GET https://api.github.com/users/{GITHUB_USER}/events` with
  `Authorization: token <PAT>` and the GitHub API headers; returns the JSON list. Not unit-tested
  (HTTP); `summarize` is.
- `main.py`: builds `presence` via `github.fetch_events` + `summarize`, in its own try/except so a
  GitHub outage or unset token degrades to `idle` and never breaks weather/moon. `oracle.build`
  gains a `presence` argument.

## Privacy boundary

The PAT lives only in the Pi's environment. The server fetches events but emits **only**
`coding_rhythm` + `hours_since_push`. No repository names, commit messages, branches, or event
details are placed in the response, cached on the device, or rendered. (This also keeps the earlier
cleartext-on-LAN concern moot: nothing sensitive crosses the wire to the device.)

## Device manifestation (the blend)

`mood_bias` (seasonal-style nudge) gains presence handling, layered after weather/moon:
- **heavy** → independent-but-proud: comfort↑ (content alone, won't "miss" you), small affection↑
  (proud), small energy↑. Visually it tends toward the contemplative/wisp look — no new form.
- **long quiet gap** (`hours_since_push` above a threshold) → attentive: curiosity↑ and affection↑
  (turns toward you).
- `light` → a mild version of heavy.

Quips: a presence pool — busy ("you've been deep in work", "i watched the clouds while you worked")
and quiet ("it's quiet without you", "where did you wander?"). `quip_tag` returns a presence tag
when rhythm is notable (chosen below weather/moon priority).

Journal: the daily record's flags byte gains a **busy** bit (bit1; bit0 already = greeted). When the
day was `heavy`/`light`, `generate_entry` can read "…you seemed busy." (woven into the existing line).

## Persistence

The oracle NVM cache (`slime/oracle.pack`/`unpack`) extends to include `coding_rhythm` (as a small
id) and `hours_since_push`. It remains its **own fixed NVM slot** (offset 512); on a format change a
stale blob simply fails the sanity check and is re-fetched. **State stays v3** — no migration.

## Error Handling

GitHub failure or missing token → server emits `idle` presence (200 OK), so `/oracle` always
succeeds. The device treats `idle`/absent presence as a no-op (behaves as Phase 2a). Nothing here
can crash the creature or block it offline.

## Testing & CI

- **Server (host):** `github.summarize` against mocked event payloads (idle/light/heavy +
  hours-since-push); `/oracle` includes `presence` (idle with no token, populated when
  `fetch_events` is monkeypatched). ≥80%.
- **Device pure (host):** `oracle.parse` of the presence block, the blended `mood_bias`, presence
  `quip_tag`, cache pack/unpack with presence, and the journal busy-flag entry. ≥80%.
- The existing two-job CI (`check` + `server`) covers both tiers.

## Success Criteria

1. `GET /oracle` carries a `presence` block: `idle` with no PAT configured, a real `coding_rhythm` +
   `hours_since_push` when a PAT is set.
2. The slime leans **independent-but-proud** when you've been coding and **attentive** after a quiet
   stretch; a "you seemed busy" journal line appears on busy days.
3. **No GitHub content** (repos, messages) ever reaches the device or screen.
4. Offline / server-down → uses the cached oracle, otherwise behaves as Phase 2a.
5. Server tests ≥80%; device pure tests ≥80%; CI green for both jobs.

## Out of Scope (Phase 2b-i)

Calendar (2b-ii) and email (2b-iii) sources; LLM dreams / long-term memory / readable journal
archive (2c); Phase 3 hardware.
