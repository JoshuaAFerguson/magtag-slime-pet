# Slime Pet — Phase 1: Richer Offline Behaviors (Design)

**Date:** 2026-06-17
**Status:** Approved (design)
**Scope:** Phase 1a of the MagTag Slime Pet vision — forms, friendship, sound, dreams+artifacts.
**Builds on:** Phase 0 Local Soul (`docs/superpowers/specs/2026-06-17-local-soul-mvp-design.md`).

---

## Context

Phase 0 shipped the offline "Local Soul": mood engine, gesture detection, breathing NeoPixels,
pixel-art E-Ink rendering, quips, and NVM persistence — all on a strict pure-logic / hardware-adapter
split. Phase 1 deepens the creature while staying fully offline.

### Scope decision

Phase 1's full feature set (morphology, journal, sound, friendship, dreams/lore, seasonal) is split:

- **Phase 1a (this spec):** Forms, Friendship/familiarity, Sound (piezo), Dreams + artifacts. All
  robustly offline — no clock required.
- **Phase 1b (next):** Journal ("one per day") and Seasonal behavior. These need wall-clock time;
  rather than wait for the RTC add-on (Phase 3), they will use a lightweight **NTP time sync over
  WiFi** with graceful offline fallback. Deferred to keep this slice focused.

## Locked Decisions

| Area | Choice |
|---|---|
| Forms | All five: puddle, sleeping loaf, explorer, crowned (familiarity-unlocked), wisp |
| Friendship | Gentle, visit-based growth; never decreases; tiered unlocks |
| Sound | Expressive motifs (short tone sequences per mood/event) on the piezo |
| Dreams | Morning dream screen + collectible artifacts referenced later |
| Persistence | NVM-only, struct bumped v1 → v2 with v1 migration (never lose progress) |

---

## Architecture

Same discipline as Phase 0: **pure** modules (no hardware imports, host-tested) and thin
**adapters** (device-only).

### New pure modules
- `slime/friendship.py` — familiarity model: grows from positive events and distinct "visits";
  never falls. `tier(familiarity) -> int` and `unlocked_*` gates.
- `slime/forms.py` — selects the body **form** (or falls back to a Phase-0 expression face) from
  mood + familiarity tier + sleep state; maps the choice to a sprite-sheet frame index.
- `slime/dreams.py` — assembles a dream string from recent-interaction context + a lore pool
  (+ personal references unlocked by tier); may yield an artifact id. Deterministic via an injected
  `choice` function.
- `slime/motifs.py` — data + selection of tone sequences `[(freq_hz, ms), ...]` per mood/event.

### Extended pure modules
- `slime/state.py` — `State` gains `familiarity` (float), `visit_count` (int), `artifacts` (int
  bitmask). `evolve()` extended accordingly.
- `slime/quips.py` — additional pools, some familiarity-gated.
- `slime/persistence.py` — NVM struct v2 + v1→v2 migration.

### New / extended adapters (device-only)
- `slime/sound.py` — plays a motif on the piezo via `pwmio` tones, gating `board.SPEAKER_ENABLE`.
- `slime/display.py` — add a full-screen **dream render** mode (dream line + artifact name).
- `code.py` — wire form selection, familiarity updates, motif playback, and the dream-on-wake flow.

### Assets
- `assets/make_assets.py` — sprite sheet grows 7 → 12 frames (adds puddle, loaf, explorer, crowned,
  wisp). Frame indices stay aligned with `forms.py` / `visuals.POSE_INDEX`.

## Forms

`forms.choose_render(mood, tier, sleeping) -> frame_key` decides what the body looks like, in
priority order:

1. deep sleep / very sleepy → **loaf**
2. very low energy → **puddle**
3. long-quiet / contemplative → **wisp**
4. curious + energetic → **explorer**
5. happy + high familiarity (tier gate) → **crowned**
6. otherwise → the Phase-0 expression face (content / sleepy / curious / happy / contemplative)

Exactly one sprite frame is rendered, so the display remains a single `TileGrid` (KISS).

## Friendship / Familiarity

- `familiarity` is a 0–100 float, persisted, that **only ever rises**.
- Growth: a small increment per positive interaction (boop / pet / greeting); a larger increment
  when a **new visit** begins — a visit is registered when activity resumes after a long quiet gap
  (tracked via elapsed time since last interaction). `visit_count` is persisted.
- `tier(familiarity)` returns an integer band (e.g., 0–4). Tiers unlock progressively:
  - more quips → Explorer form → richer sound motifs → Crowned form + personal dream references.
- **No familiarity number or bar is ever shown** — only the behavioral unlocks reveal the bond.

## Sound (piezo motifs)

- `motifs.py` defines short tone sequences and selects one for a context (greeting tune, dizzy
  warble, sleepy descending notes, wake chirp, dream-found sparkle).
- `sound.py` plays the selected motif on `board.SPEAKER` (PWM square tones), enabling
  `board.SPEAKER_ENABLE` around playback.
- Calm by default: motifs fire on greetings, waking, dreams, and dizzy — not continuously. Higher
  familiarity tiers unlock a few extra motifs.

## Dreams + Artifacts

- **Trigger:** a "night" is an extended dark + quiet stretch; when the slime then returns to
  wakefulness (deep-sleep wake on battery, or dark→light + activity on USB) it dreams **once**.
- **Generation:** `dreams.generate(context, choice)` assembles one dream line from a lore pool plus
  recent-interaction tokens; at higher familiarity tiers it may use personal references. It
  *occasionally* returns an **artifact id** (Moon Pebble, Bent Key, Star Feather, Purple Sand, Tiny
  Crown, …).
- **Surfacing:** on that wake, the E-Ink shows a brief **dream screen** (dream line + any artifact
  found), then returns to the normal creature render. A "dream-found" motif may play.
- **Artifacts** are stored as a bitmask in NVM (collected / not). They are *not* currency or
  upgrades — they seed future personal dream and quip references. Up to 32 artifact types.

## Persistence (NVM v2 with migration)

- The NVM blob format gains: `familiarity` (float), `visit_count` (uint32), `artifacts` (uint32
  bitmask). `NVM_VERSION` becomes 2.
- `pack` writes v2. `unpack`:
  - v2 blob → full decode.
  - **v1 blob → migrate**: keep Phase-0 mood/last_seen/boops/longest_absence/first_boot, default the
    new fields (familiarity 0, visit_count 0, artifacts 0). This honors "never lose progress" across
    a firmware upgrade.
  - anything else → `default_state` fallback.
- Dreams are generated and shown at wake (not persisted), so no variable-length data is stored;
  Phase 1 stays **NVM-only** (no filesystem-write remount needed).

## Error Handling

Consistent with Phase 0: every adapter call is guarded; a missing/failed piezo, display, or sensor
degrades gracefully and never crashes the creature (Rule 1). Sound is always optional — silence on
failure, never an error.

## Testing

- Host unit tests (≥80% on the pure layer) for: friendship growth/visit-detection/tiers, form
  selection priority, dream-assembly determinism (injected `choice`), motif selection, and NVM
  **v1→v2 migration** and v2 round-trip.
- Extend `sim/simulator.py` so a scripted multi-day run exercises familiarity growth, form changes,
  and a dream.
- Adapters (`sound`, dream render) verified on-device.

## Success Criteria

1. Body **forms** appear based on mood + familiarity (loaf asleep, puddle drained, explorer curious,
   crowned when bonded + happy, wisp when long-quiet).
2. The bond **deepens visibly** over visits — new quips/forms/sounds unlock — and **survives a
   firmware upgrade from a v1 NVM blob** (Phase-0 progress preserved).
3. **Motifs** play on greetings, waking, dreams, and dizzy; calm and gentle otherwise.
4. After a long sleep, a **dream screen** shows on wake; artifacts are occasionally found, **persist**,
   and get **referenced** later.
5. Fully offline; never crashes; never loses progress.
6. Pure-layer host tests ≥80%.

## Out of Scope (Phase 1a)

Journal, seasonal behavior, NTP/WiFi (all Phase 1b), the cloud dreamscape (Phase 2), and add-on
sensors (Phase 3).
