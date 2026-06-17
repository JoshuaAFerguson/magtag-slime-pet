"""Persist core state to microcontroller NVM. pack/unpack are pure; save/load touch hardware."""
import struct
from slime.state import Mood, State, default_state
from slime import mood as mood_engine

NVM_VERSION = 1
# version(B) + 5 mood floats + last_seen + longest_absence + first_boot (f) + total_boops (I)
_FORMAT = "<B5ffffI"
BLOB_SIZE = struct.calcsize(_FORMAT)


def pack(state):
    """Serialize the durable parts of a State to bytes (expression/behavior are recomputed)."""
    m = state.mood
    return struct.pack(
        _FORMAT,
        NVM_VERSION,
        m.energy, m.comfort, m.curiosity, m.sleepiness, m.affection,
        state.last_seen, state.longest_absence, state.first_boot,
        state.total_boops,
    )


def unpack(blob):
    """Deserialize bytes to a State, recomputing expression/behavior. Raises ValueError on bad data."""
    if len(blob) < BLOB_SIZE:
        raise ValueError("nvm blob too short")
    fields = struct.unpack(_FORMAT, blob[:BLOB_SIZE])
    version = fields[0]
    if version != NVM_VERSION:
        raise ValueError("nvm version mismatch")
    mood = Mood(*fields[1:6])
    last_seen, longest_absence, first_boot, total_boops = fields[6:10]
    return State(
        mood=mood,
        last_seen=last_seen,
        total_boops=total_boops,
        longest_absence=longest_absence,
        first_boot=first_boot,
        expression=mood_engine.derive_expression(mood),
        behavior="idle",
    )


def save(state):
    """Write state to NVM. Device-only."""
    import microcontroller
    microcontroller.nvm[0:BLOB_SIZE] = pack(state)


def load(now=0.0):
    """Read state from NVM; return a fresh default_state on any problem. Device-only."""
    import microcontroller
    try:
        return unpack(bytes(microcontroller.nvm[0:BLOB_SIZE]))
    except Exception:
        return default_state(now)
