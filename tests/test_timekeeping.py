"""Tests for pure time math: epoch, civil dates, day ordinals, new-day detection."""

from slime.timekeeping import civil_from_epoch, day_ordinal, is_new_day, now_epoch


def test_now_epoch_adds_elapsed_monotonic():
    assert now_epoch(1000, mono_at_sync=50.0, mono_now=80.0) == 1030


def test_civil_from_epoch_unix_origin():
    assert civil_from_epoch(0, tz_offset_hours=0) == (1970, 1, 1)
    assert civil_from_epoch(86400, tz_offset_hours=0) == (1970, 1, 2)
    assert civil_from_epoch(31 * 86400, tz_offset_hours=0) == (1970, 2, 1)


def test_civil_from_epoch_applies_timezone():
    assert civil_from_epoch(0, tz_offset_hours=-7) == (1969, 12, 31)


def test_day_ordinal_counts_local_days():
    assert day_ordinal(5 * 86400 + 3600, tz_offset_hours=0) == 5


def test_is_new_day():
    assert is_new_day(4, 5) is True
    assert is_new_day(5, 5) is False
    assert is_new_day(6, 5) is False


def test_hms_from_epoch_at_unix_zero():
    from slime import timekeeping

    assert timekeeping.hms_from_epoch(0, 0.0) == (0, 0, 0)


def test_hms_from_epoch_counts_into_day():
    from slime import timekeeping

    # 1:01:01 after midnight UTC
    assert timekeeping.hms_from_epoch(3661, 0.0) == (1, 1, 1)
    # 12:30:00 after midnight UTC
    assert timekeeping.hms_from_epoch(45000, 0.0) == (12, 30, 0)


def test_hms_from_epoch_applies_tz_offset():
    from slime import timekeeping

    # 45000s UTC, shifted -7h -> 19800s -> 05:30:00 local
    assert timekeeping.hms_from_epoch(45000, -7.0) == (5, 30, 0)


def test_month_abbr_has_twelve_entries():
    from slime import timekeeping

    assert len(timekeeping.MONTH_ABBR) == 12
    assert timekeeping.MONTH_ABBR[0] == "Jan"
    assert timekeeping.MONTH_ABBR[5] == "Jun"
    assert timekeeping.MONTH_ABBR[11] == "Dec"
