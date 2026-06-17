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


def should_dream(slept, sleep_seconds):
    """A dream forms only on waking from a sufficiently long sleep."""
    return bool(slept) and sleep_seconds >= _MIN_SLEEP


def generate(tier, artifacts_mask, choice):
    """Assemble one dream line and maybe an artifact id.
    `choice(seq)` picks from a sequence."""
    line = choice(_ACTS) + " " + choice(_PLACES) + "."
    if tier >= 2:
        line += " " + choice(_PERSONAL) + "."

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
