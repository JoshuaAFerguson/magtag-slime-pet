"""Pure dream assembly and collectible artifacts. Deterministic via injected choice()."""

ARTIFACTS = (
    "Moon Pebble",
    "Purple Sand",
    "Tiny Crown",
    "Bent Key",
    "Star Feather",
    "Silver Leaf",
    "Glass Bead",
    "Owl Feather",
)

_ACTS = (
    "I crossed",
    "I floated over",
    "I waited at",
    "I drifted past",
    "I remembered",
)
_PLACES = (
    "a desert beneath a purple moon",
    "the Silver Pond",
    "the edge of the Quiet Sea",
    "a field of slow clouds",
    "the Hall of the Owl King",
)
_PERSONAL = (
    "You were there, watching",
    "I looked for you",
    "I carried your warmth",
)

_MIN_SLEEP = 900.0  # seconds asleep before a dream forms

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


def should_dream(slept, sleep_seconds):
    """A dream forms only on waking from a sufficiently long sleep."""
    return bool(slept) and sleep_seconds >= _MIN_SLEEP


def generate(tier, artifacts_mask, choice, extra_refs=()):
    """Assemble one dream line and maybe an artifact id.
    `choice(seq)` picks from a sequence."""
    line = choice(_ACTS) + " " + choice(_PLACES) + "."
    if tier >= 2:
        line += " " + choice(_PERSONAL) + "."
    if extra_refs:
        line += " " + choice(tuple(extra_refs)) + "."

    artifact_id = None
    # ~1-in-4 chance to find something, decided via injected choice.
    if choice((True, False, False, False)):
        uncollected = [i for i in range(len(ARTIFACTS)) if not has_artifact(artifacts_mask, i)]
        if uncollected:
            artifact_id = choice(uncollected)
    return line, artifact_id


def artifact_name(artifact_id):
    """Return the name of an artifact by its ID."""
    return ARTIFACTS[artifact_id]


def has_artifact(mask, artifact_id):
    """Check if artifact is in the bitmask."""
    return bool((mask >> artifact_id) & 1)


def add_artifact(mask, artifact_id):
    """Add artifact to the bitmask."""
    return mask | (1 << artifact_id)
