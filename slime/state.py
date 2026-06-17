"""Pure value types for the slime's soul. No hardware imports."""
from collections import namedtuple

MOOD_FIELDS = ("energy", "comfort", "curiosity", "sleepiness", "affection")
Mood = namedtuple("Mood", MOOD_FIELDS)

State = namedtuple(
    "State",
    (
        "mood",             # Mood
        "last_seen",        # float seconds (monotonic-based)
        "total_boops",      # int
        "longest_absence",  # float seconds
        "first_boot",       # float seconds
        "expression",       # str
        "behavior",         # str
    ),
)


def clamp(value, lo=0.0, hi=100.0):
    """Clamp a drive value into [lo, hi] as a float."""
    return float(min(hi, max(lo, value)))


def clamp_mood(mood):
    """Return a new Mood with every drive clamped to [0, 100]."""
    return Mood(*(clamp(v) for v in mood))


def default_state(now=0.0):
    """A gentle starting personality: comfortable, mildly curious, awake."""
    return State(
        mood=Mood(energy=60.0, comfort=70.0, curiosity=50.0, sleepiness=30.0, affection=40.0),
        last_seen=now,
        total_boops=0,
        longest_absence=0.0,
        first_boot=now,
        expression="content",
        behavior="idle",
    )


def evolve(state, **changes):
    """Return a new State with the given fields changed.

    CircuitPython's namedtuple does not implement `_replace`, so we reconstruct
    explicitly. Works identically on desktop CPython and on-device.
    """
    return State(
        mood=changes.get("mood", state.mood),
        last_seen=changes.get("last_seen", state.last_seen),
        total_boops=changes.get("total_boops", state.total_boops),
        longest_absence=changes.get("longest_absence", state.longest_absence),
        first_boot=changes.get("first_boot", state.first_boot),
        expression=changes.get("expression", state.expression),
        behavior=changes.get("behavior", state.behavior),
    )
