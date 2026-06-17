"""Persist core state to microcontroller NVM. pack/unpack pure; save/load touch hardware."""

import struct

from slime import mood as mood_engine
from slime.state import Mood, State, default_state

NVM_VERSION = 2

# v1 (Phase 0): version + 5 mood floats + last_seen + longest_absence +
# first_boot + total_boops.
_FORMAT_V1 = "<B5ffffI"
_SIZE_V1 = struct.calcsize(_FORMAT_V1)

# v2 (Phase 1): v1 fields + familiarity (f) + visit_count (I) +
# artifacts (I).
_FORMAT_V2 = "<B5ffffIfII"
_SIZE_V2 = struct.calcsize(_FORMAT_V2)

BLOB_SIZE = _SIZE_V2


def pack(state):
    """Serialize the durable parts of a State to a v2 NVM blob."""
    m = state.mood
    return struct.pack(
        _FORMAT_V2,
        NVM_VERSION,
        m.energy,
        m.comfort,
        m.curiosity,
        m.sleepiness,
        m.affection,
        state.last_seen,
        state.longest_absence,
        state.first_boot,
        state.total_boops,
        state.familiarity,
        state.visit_count,
        state.artifacts,
    )


def _build(
    mood,
    last_seen,
    longest_absence,
    first_boot,
    total_boops,
    familiarity,
    visit_count,
    artifacts,
):
    """Construct a State from deserialized fields."""
    return State(
        mood=mood,
        last_seen=last_seen,
        total_boops=total_boops,
        longest_absence=longest_absence,
        first_boot=first_boot,
        expression=mood_engine.derive_expression(mood),
        behavior="idle",
        familiarity=familiarity,
        visit_count=visit_count,
        artifacts=artifacts,
    )


def unpack(blob):
    """Deserialize a v2 blob, migrating a v1 blob.

    Raises ValueError on bad data.
    """
    if len(blob) < 1:
        raise ValueError("nvm blob empty")
    version = blob[0]
    if version == 2:
        if len(blob) < _SIZE_V2:
            raise ValueError("nvm v2 blob too short")
        f = struct.unpack(_FORMAT_V2, blob[:_SIZE_V2])
        mood = Mood(*f[1:6])
        return _build(mood, f[6], f[7], f[8], f[9], f[10], f[11], f[12])
    if version == 1:
        if len(blob) < _SIZE_V1:
            raise ValueError("nvm v1 blob too short")
        f = struct.unpack(_FORMAT_V1, blob[:_SIZE_V1])
        mood = Mood(*f[1:6])
        return _build(mood, f[6], f[7], f[8], f[9], 0.0, 0, 0)
    raise ValueError("nvm version unknown")


def save(state):
    """Write state to NVM. Device-only."""
    import microcontroller

    microcontroller.nvm[0:BLOB_SIZE] = pack(state)


def load(now=0.0):
    """Read state from NVM; return default_state on any problem. Device-only."""
    import microcontroller

    try:
        return unpack(bytes(microcontroller.nvm[0:BLOB_SIZE]))
    except Exception:
        return default_state(now)
