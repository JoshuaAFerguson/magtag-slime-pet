"""Pure daily-journal records + NVM ring buffer + regenerated entry text.

Records are compact (8 bytes). Text is regenerated from the record, not
stored. Device read/write of the ring (save_ring/load_ring) import
microcontroller lazily.
"""

import struct

_RECORD_FMT = "<IBBBB"  # day_ordinal, mood_dom, season, flags, tier
RECORD_SIZE = struct.calcsize(_RECORD_FMT)  # 8
_HEADER_FMT = "<HH"  # count, head
_HEADER_SIZE = struct.calcsize(_HEADER_FMT)  # 4
CAPACITY = 48
RING_SIZE = _HEADER_SIZE + CAPACITY * RECORD_SIZE

# Mood byte -> ambience tone words used in the entry.
_MOOD_WORD = {
    0: "i watched the clouds",
    1: "i drifted",
    2: "a good day",
    3: "i wondered at things",
    4: "i thought of far places",
}
# Keyed by seasons.accent_frame(): spring=0, summer=1, autumn=2, winter=3.
_SEASON_WORD = {
    0: "green light",
    1: "long warm hours",
    2: "soft gray light",
    3: "still cold air",
}


def pack_record(day_ordinal, mood_dom, season, flags, tier):
    """Pack a record into 8 bytes."""
    return struct.pack(_RECORD_FMT, day_ordinal, mood_dom, season, flags, tier)


def unpack_record(blob):
    """Unpack a record from bytes."""
    return struct.unpack(_RECORD_FMT, blob[:RECORD_SIZE])


def empty_ring():
    """Return an empty ring buffer."""
    return struct.pack(_HEADER_FMT, 0, 0) + bytes(CAPACITY * RECORD_SIZE)


def append(ring, record_bytes):
    """Return a new ring with record appended at the head (wrapping at CAPACITY)."""
    count, head = struct.unpack(_HEADER_FMT, ring[:_HEADER_SIZE])
    body = bytearray(ring[_HEADER_SIZE:])
    off = head * RECORD_SIZE
    body[off : off + RECORD_SIZE] = record_bytes[:RECORD_SIZE]
    head = (head + 1) % CAPACITY
    count = min(count + 1, CAPACITY)
    return struct.pack(_HEADER_FMT, count, head) + bytes(body)


def entries(ring):
    """Return unpacked records oldest-first."""
    count, head = struct.unpack(_HEADER_FMT, ring[:_HEADER_SIZE])
    body = ring[_HEADER_SIZE:]
    start = (head - count) % CAPACITY
    out = []
    for i in range(count):
        idx = (start + i) % CAPACITY
        off = idx * RECORD_SIZE
        out.append(unpack_record(body[off : off + RECORD_SIZE]))
    return out


def generate_entry(record, day_number, choice):
    """Regenerate the journal line for a record.

    `choice` picks a closing variant from a tuple of options.
    """
    _, mood_dom, season, flags, _tier = record
    ambience = _SEASON_WORD.get(season, "the usual light")
    presence = "you came near" if flags & 0b1 else "a quiet day alone"
    if flags & 0b10:
        closing = "you seemed busy"
    else:
        closing = choice((_MOOD_WORD.get(mood_dom, "i watched the clouds"),))
    return "Day {} - {}. {}. {}.".format(day_number, ambience, presence, closing)


def save_ring(ring):
    """Write the journal ring to NVM after the state blob. Device-only."""
    import microcontroller

    from slime.persistence import BLOB_SIZE

    start = ((BLOB_SIZE // 16) + 1) * 16  # 16-byte aligned after state blob
    microcontroller.nvm[start : start + RING_SIZE] = ring


def load_ring():
    """Read the journal ring from NVM; return an empty ring on any problem.

    Device-only.
    """
    import microcontroller

    from slime.persistence import BLOB_SIZE

    start = ((BLOB_SIZE // 16) + 1) * 16
    try:
        data = bytes(microcontroller.nvm[start : start + RING_SIZE])
        struct.unpack(_HEADER_FMT, data[:_HEADER_SIZE])  # sanity
        return data
    except Exception:
        return empty_ring()
