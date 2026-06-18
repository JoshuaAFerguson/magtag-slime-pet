# Slime Pet — Phase 2a: Weather + Moon Oracle (Design)

**Date:** 2026-06-18
**Status:** Approved (design)
**Scope:** Phase 2a — the first slice of the cloud dreamscape: a home API serving weather + moon,
and a MagTag client that reacts to them.
**Builds on:** Phases 0–1b (offline soul, forms/friendship/sound/dreams, NTP time/journal/seasons).

---

## Context

Phase 2 is the "cloud dreamscape": an optional oracle on the Orange Pi cluster that makes the slime
deeper without ever being required (Rule 4: offline first). Phase 2 decomposes into 2a (weather +
moon, public data, no OAuth), 2b (personal calendar/email/GitHub summaries), and 2c (LLM dreams,
long-term memory, readable journal archive). This spec is **2a**.

Per the vision's Phoenix Edition, the slime should *experience* Arizona, not report it: weather and
moon shape personality, voice, forms, and dreams — not a data readout.

## Locked Decisions

| Area | Choice |
|---|---|
| API stack | Python + FastAPI |
| Deployment | Docker container on the cluster |
| Device → Pi addressing | mDNS hostname in `settings.toml`, with a static-IP fallback |
| Weather source | Open-Meteo (free, no key); Pi holds the Phoenix location |
| Moon phase | Computed on the Pi from the date (no external API) |
| Manifestation | Behavior + voice + weather **forms** (melting / hiding) + moon accent |
| Oracle cache | A separate small NVM slot; **state stays v3** (no migration) |
| Build order | Server first (standalone, curl-able), then the MagTag client |

---

## Architecture — two tiers

### Tier 1 — Home API (`server/`, regular CPython, host-tested)
A small FastAPI service, containerized, serving one main endpoint. It owns the location and all
external calls, so the device just asks "what's it like?" and gets feelings back.

```
server/
  app/
    __init__.py
    main.py        # FastAPI app: GET /oracle, GET /health
    weather.py     # Open-Meteo fetch + normalize to feeling tags
    moon.py        # PURE: moon phase + illumination from a date
    oracle.py      # assemble the /oracle payload from weather + moon
    config.py      # env config: LAT/LON (default Phoenix), TZ, ORACLE_TOKEN
  tests/
    test_moon.py
    test_weather.py      # Open-Meteo HTTP mocked — no network in CI
    test_oracle.py
    test_main.py         # FastAPI TestClient
  Dockerfile
  docker-compose.yml
  requirements.txt       # fastapi, uvicorn, httpx
  pyproject.toml         # ruff/black/pytest config for the server
```

### Tier 2 — MagTag client (`slime/`, CircuitPython)
On the daily WiFi sync (alongside NTP) the device fetches `/oracle`, caches it in NVM, and reacts.
Offline, it uses the cached oracle and never blocks on the network.

## The `/oracle` payload

```json
{
  "weather": {"tags": ["extreme_heat"], "temp_c": 43.0, "code": "clear", "sunset_soon": false},
  "moon": {"phase": 4, "name": "full", "illum": 0.98},
  "ts": 1718900000
}
```

- `weather.tags` — a small closed set, desert-tuned: `extreme_heat`, `monsoon`, `rain`,
  `storm_incoming`, `cold`, `clear`. Zero or more apply; the device acts on the first it recognizes.
- `weather.sunset_soon` — true within ~30 min of sunset (drives an "admiring" lift).
- `moon.phase` — 0–7 (new → waning crescent); `name` and `illum` (0–1) included.

## Home API details (`server/`)

- `weather.py`: calls Open-Meteo `current` + `daily` for the configured lat/lon; maps to the tag set
  with Phoenix-tuned thresholds (e.g. `extreme_heat` ≥ 40 °C; `monsoon` = high humidity + daily
  precipitation probability over a threshold in Jun–Sep; `storm_incoming` = high precip probability;
  `cold` ≤ 5 °C; else `clear`). All thresholds are named constants.
- `moon.py`: pure synodic-month calculation → phase index, name, illumination. No dependencies.
- `main.py`: `GET /oracle` (assembles weather + moon + unix `ts`), `GET /health`. If `ORACLE_TOKEN`
  is set, require `Authorization: Bearer <token>`; otherwise open on the LAN.
- Resilience: if Open-Meteo fails, `/oracle` still returns moon + an empty weather tag list (200),
  so the device degrades to moon-only rather than erroring.
- `Dockerfile` (slim Python, uvicorn) + `docker-compose.yml` (env, restart policy, port).

## MagTag client details (`slime/`)

- `slime/netoracle.py` (**adapter**, device-only): `GET http://<ORACLE_HOST>/oracle` via
  `adafruit_requests`; `ORACLE_HOST` and optional `ORACLE_TOKEN` from `settings.toml`. Returns the
  parsed dict or `None` on any failure (never raises into the loop).
- `slime/oracle.py` (**pure**):
  - `parse(payload)` → `Oracle` namedtuple `(weather_tag, temp_c, moon_phase, moon_illum, sunset_soon)`
    (picks the single dominant weather tag by a fixed priority).
  - `mood_bias(oracle)` → seasonal-style nudge: `storm_incoming`→comfort↑ (cozy/hiding),
    `extreme_heat`→energy↓ (drained), `rain`→curiosity↑ (excited), `sunset_soon`→a brief
    affection/comfort lift (admiring); full moon → a small curiosity/“dreamy” lift.
  - `quip_tag(oracle)` → `heat` / `rain` / `storm` / `sunset` / `full_moon` / `new_moon` / None.
  - `form_override(oracle)` → `"melting"` (extreme_heat) / `"hiding"` (storm_incoming) / None.
  - `dream_refs(oracle)` → lore fragments for dreams ("beneath the full moon", "the desert stayed
    warm").
  - `pack`/`unpack` for the compact NVM cache record.
- `code.py`: on the daily sync, `netoracle` fetch → cache to NVM; load cached oracle at boot; apply
  `mood_bias`; pass `form_override` into `forms.choose_render`; surface weather/moon quips; feed
  `dream_refs`/moon into `dreams.generate`. All gated so that with no oracle (offline, no cache) the
  slime behaves exactly as Phase 1b.

## New content

- **Weather forms** (sprite frames 16–17 in `slime.bmp`): `melting` (extreme heat) and `hiding`
  (storm). `forms.choose_render(mood, tier, sleeping, season=None, weather=None)` slots a weather
  form just below `loaf` (deep sleep) and above the mood/seasonal forms.
- **Moon accent**: a small corner moon added to `accents.bmp`; shown when a moon phase is known.
- **Quip pools**: `heat`, `rain`, `storm`, `sunset`, `full_moon`, `new_moon`; moon/weather references
  woven into `dreams.generate`.

## Persistence

The cached oracle (`weather_tag` byte, `moon_phase` byte, `temp_c`, `ts`, `flags` ~8 bytes) lives in
its **own fixed NVM slot** placed after the journal ring (offset computed from
`persistence.BLOB_SIZE` + journal `RING_SIZE`, 16-byte aligned, no overlap). State remains **v3** —
no migration. Pure `pack`/`unpack`; device `save_cache`/`load_cache` import `microcontroller` lazily.

## Error Handling

`netoracle.fetch` returns `None` on any WiFi/HTTP/JSON error. The server returns moon-only on weather
failure. The device uses the NVM-cached oracle when a fetch fails, and falls back to no-oracle
behavior when there is no cache. Nothing in this slice can crash the creature or block it offline.

## Testing & CI

- **Server (host):** `moon` math; `weather` tag normalization against mocked Open-Meteo payloads;
  `oracle` assembly; `main` via FastAPI `TestClient` (incl. auth + weather-failure degradation). ≥80%.
- **Client pure (host):** `oracle.parse`/`mood_bias`/`quip_tag`/`form_override`/`dream_refs`/cache
  pack-unpack; `forms.choose_render` with `weather`; weather/moon quip pools; dream refs. ≥80%.
- `netoracle` and rendering verified on-device after deploy (incl. an offline-cache run).
- **CI:** extend the GitHub Actions workflow with a second job for `server/` (installs its
  requirements, runs `ruff`/`black`/`pytest` in `server/`). The existing device-code job is unchanged.

## Success Criteria

1. `GET /oracle` returns Phoenix weather tags + moon phase; runs in Docker; `curl`-able; degrades to
   moon-only if Open-Meteo is down; honors `ORACLE_TOKEN` when set.
2. The MagTag fetches and caches the oracle on its WiFi sync and visibly reacts: mood bias, a weather
   **form** (melting in heat / hiding in a storm), weather/moon quips, and moon-flavored dreams.
3. Offline (or server down), the slime uses the cached oracle and otherwise behaves exactly as
   Phase 1b — never crashes, never blocks.
4. Server tests ≥80%; client pure tests ≥80%; CI green for both jobs.

## Out of Scope (Phase 2a)

Calendar/email/GitHub summaries (2b); LLM dream generation, long-term memory, readable journal
archive, rare visitors (2c); Phase 3 hardware add-ons.
