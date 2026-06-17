from slime.persistence import BLOB_SIZE, NVM_VERSION, pack, unpack
from slime.state import Mood, default_state


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
