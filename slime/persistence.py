"""Persist core state to microcontroller NVM. pack/unpack pure; save/load touch hardware."""

import struct

from slime import mood as mood_engine
from slime.state import Mood, State, default_state

NVM_VERSION = 4

# v1 (Phase 0): version + 5 mood floats + last_seen + longest_absence +
# first_boot + total_boops.
_FORMAT_V1 = "<B5ffffI"
_SIZE_V1 = struct.calcsize(_FORMAT_V1)

# v2 (Phase 1): v1 fields + familiarity (f) + visit_count (I) +
# artifacts (I).
_FORMAT_V2 = "<B5ffffIfII"
_SIZE_V2 = struct.calcsize(_FORMAT_V2)

# v3 (Phase 1b): v2 fields + last_journal_day_ordinal (I).
_FORMAT_V3 = "<B5ffffIfIII"
_SIZE_V3 = struct.calcsize(_FORMAT_V3)

# v4 (Phase 2c-ii): v3 fields + milestones (I).
_FORMAT_V4 = "<B5ffffIfIIII"
_SIZE_V4 = struct.calcsize(_FORMAT_V4)

BLOB_SIZE = _SIZE_V4


def pack(state):
    """Serialize the durable parts of a State to a v4 NVM blob."""
    m = state.mood
    return struct.pack(
        _FORMAT_V4,
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
        state.last_journal_day_ordinal,
        state.milestones,
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
    last_journal_day_ordinal,
    milestones,
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
        last_journal_day_ordinal=last_journal_day_ordinal,
        milestones=milestones,
    )


def unpack(blob):
    """Deserialize a v4 blob, migrating v3/v2/v1. Raises ValueError on bad data."""
    if len(blob) < 1:
        raise ValueError("nvm blob empty")
    version = blob[0]
    if version == 4:
        if len(blob) < _SIZE_V4:
            raise ValueError("nvm v4 blob too short")
        f = struct.unpack(_FORMAT_V4, blob[:_SIZE_V4])
        mood = Mood(*f[1:6])
        return _build(mood, f[6], f[7], f[8], f[9], f[10], f[11], f[12], f[13], f[14])
    if version == 3:
        if len(blob) < _SIZE_V3:
            raise ValueError("nvm v3 blob too short")
        f = struct.unpack(_FORMAT_V3, blob[:_SIZE_V3])
        mood = Mood(*f[1:6])
        return _build(mood, f[6], f[7], f[8], f[9], f[10], f[11], f[12], f[13], 0)
    if version == 2:
        if len(blob) < _SIZE_V2:
            raise ValueError("nvm v2 blob too short")
        f = struct.unpack(_FORMAT_V2, blob[:_SIZE_V2])
        mood = Mood(*f[1:6])
        return _build(mood, f[6], f[7], f[8], f[9], f[10], f[11], f[12], 0, 0)
    if version == 1:
        if len(blob) < _SIZE_V1:
            raise ValueError("nvm v1 blob too short")
        f = struct.unpack(_FORMAT_V1, blob[:_SIZE_V1])
        mood = Mood(*f[1:6])
        return _build(mood, f[6], f[7], f[8], f[9], 0.0, 0, 0, 0, 0)
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
