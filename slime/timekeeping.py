"""Pure time math: epoch <-> civil date, day ordinals. No hardware imports."""

_SECONDS_PER_DAY: int = 86400


def now_epoch(synced_epoch: int, mono_at_sync: float, mono_now: float) -> int:
    """Current epoch seconds = last sync epoch + elapsed monotonic since that sync."""
    return int(synced_epoch + (mono_now - mono_at_sync))


def _local_seconds(epoch: int, tz_offset_hours: float) -> int:
    return epoch + int(tz_offset_hours * 3600)


def day_ordinal(epoch: int, tz_offset_hours: float) -> int:
    """Whole local days since the Unix epoch."""
    return _local_seconds(epoch, tz_offset_hours) // _SECONDS_PER_DAY


def civil_from_epoch(epoch: int, tz_offset_hours: float) -> tuple[int, int, int]:
    """Return (year, month, day) in local time.

    Uses Howard Hinnant's civil_from_days algorithm.
    """
    z = day_ordinal(epoch, tz_offset_hours) + 719468
    era = (z if z >= 0 else z - 146096) // 146097
    doe = z - era * 146097
    yoe = (doe - doe // 1460 + doe // 36524 - doe // 146096) // 365
    y = yoe + era * 400
    doy = doe - (365 * yoe + yoe // 4 - yoe // 100)
    mp = (5 * doy + 2) // 153
    d = doy - (153 * mp + 2) // 5 + 1
    m = mp + 3 if mp < 10 else mp - 9
    if m <= 2:
        y += 1
    return (y, m, d)


def is_new_day(prev_ordinal: int, current_ordinal: int) -> bool:
    """True when the calendar day has advanced."""
    return current_ordinal > prev_ordinal
