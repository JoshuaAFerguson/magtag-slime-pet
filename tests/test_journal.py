from slime.journal import (
    CAPACITY,
    append,
    empty_ring,
    entries,
    generate_entry,
    pack_record,
    unpack_record,
)


def test_record_roundtrip():
    rec = (20630, 3, 1, 0b101, 2)  # day, mood, season, flags, tier
    assert unpack_record(pack_record(*rec)) == rec


def test_ring_append_and_entries_in_order():
    ring = empty_ring()
    ring = append(ring, pack_record(1, 0, 0, 0, 0))
    ring = append(ring, pack_record(2, 0, 0, 0, 0))
    got = [e[0] for e in entries(ring)]  # day ordinals
    assert got == [1, 2]


def test_ring_wraps_at_capacity():
    ring = empty_ring()
    for day in range(CAPACITY + 5):
        ring = append(ring, pack_record(day, 0, 0, 0, 0))
    got = [e[0] for e in entries(ring)]
    assert len(got) == CAPACITY
    assert got[0] == 5 and got[-1] == CAPACITY + 4  # oldest dropped


def test_generate_entry_mentions_day_number_and_is_a_string():
    rec = (20630, 3, 2, 0b001, 1)  # happy mood, autumn, greeted
    line = generate_entry(rec, day_number=14, choice=lambda s: s[0])
    assert line.startswith("Day 14")
    assert line.endswith(".")


def test_entry_season_word_matches_seasons_encoding():
    # The season byte is seasons.accent_frame(); the entry must use the matching ambience word.
    from slime.seasons import accent_frame

    summer = (100, 0, accent_frame("summer"), 0, 0)
    winter = (100, 0, accent_frame("winter"), 0, 0)
    assert "long warm hours" in generate_entry(summer, 1, lambda s: s[0])
    assert "still cold air" in generate_entry(winter, 1, lambda s: s[0])
