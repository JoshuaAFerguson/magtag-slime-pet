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


def test_busy_flag_changes_the_entry_closing():
    busy = (100, 0, 0, 0b10, 0)  # flags bit1 = busy day
    line = generate_entry(busy, day_number=5, choice=lambda s: s[0])
    assert "you seemed busy" in line


def _rec(flags):
    return unpack_record(pack_record(20000, 2, 1, flags, 3))


def test_heavy_inbox_closing():
    line = generate_entry(_rec(0b100), 5, lambda opts: opts[0])
    assert "inbox" in line.lower()


def test_busy_still_wins_over_inbox():
    line = generate_entry(_rec(0b110), 5, lambda opts: opts[0])
    assert "busy" in line.lower()


def test_generate_entry_notes_a_visitor():
    line = generate_entry((10, 0, 0, 0b1000, 1), 3, lambda o: o[0])
    assert "a visitor came by" in line.lower()


def test_generate_entry_without_visitor_flag_has_no_visitor_line():
    line = generate_entry((10, 0, 0, 0b0, 1), 3, lambda o: o[0])
    assert "visitor" not in line.lower()
