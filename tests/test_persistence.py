import struct

from slime.persistence import _FORMAT_V1, _FORMAT_V2, BLOB_SIZE, NVM_VERSION, pack, unpack
from slime.state import Mood, default_state, evolve


def test_pack_roundtrips_state():
    s = default_state(now=123.0)._replace(
        mood=Mood(11, 22, 33, 44, 55), total_boops=7, longest_absence=900.0, last_seen=500.0
    )
    blob = pack(s)
    assert len(blob) == BLOB_SIZE
    s2 = unpack(blob)
    assert tuple(s2.mood) == (11.0, 22.0, 33.0, 44.0, 55.0)
    assert s2.total_boops == 7
    assert s2.longest_absence == 900.0
    assert s2.last_seen == 500.0
    assert s2.first_boot == 123.0


def test_unpack_recomputes_expression_and_behavior():
    s = default_state(now=0.0)._replace(mood=Mood(20, 60, 30, 95, 30))
    s2 = unpack(pack(s))
    assert s2.expression == "sleepy"
    assert s2.behavior == "idle"


def test_unpack_rejects_wrong_version():
    blob = bytearray(pack(default_state()))
    blob[0] = NVM_VERSION + 9
    try:
        unpack(bytes(blob))
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_unpack_rejects_garbage_length():
    try:
        unpack(b"\x00\x00")
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_v2_roundtrip_includes_new_fields():
    s = default_state(now=1.0)
    s2 = evolve(s, familiarity=42.0, visit_count=5, artifacts=9)
    out = unpack(pack(s2))
    assert out.familiarity == 42.0
    assert out.visit_count == 5
    assert out.artifacts == 9


def test_v1_blob_migrates_preserving_core_progress():
    blob = struct.pack(_FORMAT_V1, 1, 11.0, 22.0, 33.0, 44.0, 55.0, 100.0, 7.0, 1.0, 9)
    out = unpack(blob)
    assert tuple(out.mood) == (11.0, 22.0, 33.0, 44.0, 55.0)
    assert out.total_boops == 9
    assert out.last_seen == 100.0
    assert out.familiarity == 0.0 and out.visit_count == 0 and out.artifacts == 0


def test_unpack_rejects_unknown_version():
    blob = bytearray(pack(default_state()))
    blob[0] = 99
    try:
        unpack(bytes(blob))
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_v3_roundtrip_includes_journal_day():
    s = evolve(default_state(now=1.0), last_journal_day_ordinal=20630)
    out = unpack(pack(s))
    assert out.last_journal_day_ordinal == 20630


def test_v2_blob_migrates_to_v3_defaulting_journal_day():
    s = evolve(default_state(now=2.0), familiarity=30.0, visit_count=4, artifacts=3)
    v2_blob = struct.pack(
        _FORMAT_V2,
        2,
        s.mood.energy,
        s.mood.comfort,
        s.mood.curiosity,
        s.mood.sleepiness,
        s.mood.affection,
        s.last_seen,
        s.longest_absence,
        s.first_boot,
        s.total_boops,
        s.familiarity,
        s.visit_count,
        s.artifacts,
    )
    out = unpack(v2_blob)
    assert out.familiarity == 30.0 and out.visit_count == 4 and out.artifacts == 3
    assert out.last_journal_day_ordinal == 0
