"""Pure oracle parsing + behavioral effects + NVM cache. Device save/load import lazily."""

import struct
from collections import namedtuple

from slime.state import MOOD_FIELDS, Mood, clamp_mood

Oracle = namedtuple(
    "Oracle",
    (
        "weather_tag",
        "temp_c",
        "moon_phase",
        "moon_illum",
        "sunset_soon",
        "coding_rhythm",
        "hours_since_push",
        "in_meeting",
        "meeting_soon",
        "day_load",
        "free_rest",
        "cal_known",
    ),
)

_TAG_PRIORITY = ("storm_incoming", "extreme_heat", "rain", "monsoon", "cold", "clear")
_TAG_IDS = ("clear", "storm_incoming", "extreme_heat", "rain", "monsoon", "cold")

_WEATHER_TARGETS = {
    "storm_incoming": {"comfort": 80.0, "sleepiness": 55.0},
    "extreme_heat": {"energy": 20.0},
    "rain": {"curiosity": 75.0, "energy": 65.0},
    "cold": {"comfort": 70.0},
}
_FORM = {"extreme_heat": "melting", "storm_incoming": "hiding"}
_QUIP = {
    "extreme_heat": "heat",
    "rain": "rain",
    "storm_incoming": "storm",
    "monsoon": "storm",
}

_RHYTHM_IDS = ("idle", "light", "heavy")
_RHYTHM_TARGETS = {
    "heavy": {"comfort": 78.0, "affection": 60.0, "energy": 62.0},
    "light": {"comfort": 72.0},
}
_QUIET_GAP_HOURS = 36.0

_LOAD_IDS = ("light", "normal", "heavy")
_CAL_IDLE = {
    "in_meeting": False,
    "meeting_soon": False,
    "day_load": "light",
    "free_rest_of_day": True,
}


def parse(payload):
    """Map an /oracle dict to an Oracle, or None if there's nothing usable."""
    if payload is None:
        return None
    w = payload.get("weather", {})
    m = payload.get("moon", {})
    p = payload.get("presence", {})
    tags = w.get("tags", []) or []
    tag = "clear"
    for candidate in _TAG_PRIORITY:
        if candidate in tags:
            tag = candidate
            break
    cal = payload.get("calendar")
    cal_known = cal is not None
    c = cal if cal_known else _CAL_IDLE
    return Oracle(
        weather_tag=tag,
        temp_c=w.get("temp_c"),
        moon_phase=m.get("phase", 0),
        moon_illum=m.get("illum", 0.0),
        sunset_soon=bool(w.get("sunset_soon", False)),
        coding_rhythm=p.get("coding_rhythm", "idle"),
        hours_since_push=p.get("hours_since_push"),
        in_meeting=bool(c.get("in_meeting", False)),
        meeting_soon=bool(c.get("meeting_soon", False)),
        day_load=c.get("day_load", "light"),
        free_rest=bool(c.get("free_rest_of_day", True)),
        cal_known=cal_known,
    )


def mood_bias(mood, oracle, rate=0.05):
    """Nudge mood toward the weather's tendency + a small full-moon dreaminess.

    Returns a new Mood with adjusted drives.
    """
    if oracle is None:
        return mood
    vals = {field: getattr(mood, field) for field in MOOD_FIELDS}
    for drive, target in _WEATHER_TARGETS.get(oracle.weather_tag, {}).items():
        vals[drive] += (target - vals[drive]) * rate
    if oracle.sunset_soon:
        vals["affection"] += (70.0 - vals["affection"]) * rate
    if oracle.moon_phase == 4:
        vals["curiosity"] += (65.0 - vals["curiosity"]) * rate
    for drive, target in _RHYTHM_TARGETS.get(oracle.coding_rhythm, {}).items():
        vals[drive] += (target - vals[drive]) * rate
    if oracle.hours_since_push is not None and oracle.hours_since_push >= _QUIET_GAP_HOURS:
        vals["curiosity"] += (70.0 - vals["curiosity"]) * rate
        vals["affection"] += (65.0 - vals["affection"]) * rate
    return clamp_mood(Mood(**vals))


def form_override(oracle):
    """Weather form name (melting/hiding) or None."""
    if oracle is None:
        return None
    return _FORM.get(oracle.weather_tag)


def quip_tag(oracle):
    """Weather/moon quip pool tag, or None."""
    if oracle is None:
        return None
    if oracle.weather_tag in _QUIP:
        return _QUIP[oracle.weather_tag]
    if oracle.sunset_soon:
        return "sunset"
    if oracle.moon_phase == 4:
        return "full_moon"
    if oracle.moon_phase == 0:
        return "new_moon"
    if oracle.coding_rhythm in ("heavy", "light"):
        return "busy"
    if oracle.hours_since_push is not None and oracle.hours_since_push >= _QUIET_GAP_HOURS:
        return "quiet"
    return None


def dream_refs(oracle):
    """Lore fragments to weave into dreams from weather/moon."""
    if oracle is None:
        return ()
    refs = []
    if oracle.moon_phase == 4:
        refs.append("beneath the full moon")
    elif oracle.moon_phase == 0:
        refs.append("under a dark new-moon sky")
    if oracle.weather_tag == "extreme_heat":
        refs.append("the desert stayed warm")
    elif oracle.weather_tag in ("rain", "storm_incoming", "monsoon"):
        refs.append("rain was coming")
    return tuple(refs)


def is_busy(oracle):
    """True when there's notable recent coding activity (drives the journal 'busy' flag)."""
    return oracle is not None and oracle.coding_rhythm in ("heavy", "light")


_FMT_OLD = "<BBBffBf"  # pre-calendar layout (still readable for migration)
SIZE_OLD = struct.calcsize(_FMT_OLD)
# + flags byte (bit0 in_meeting, bit1 meeting_soon, bit2 free_rest, bit3 cal_known)
# + load byte (index into _LOAD_IDS)
_FMT = "<BBBffBfBB"
SIZE = struct.calcsize(_FMT)


def pack(oracle):
    """Pack an Oracle into binary form for NVM storage."""
    tag_id = _TAG_IDS.index(oracle.weather_tag) if oracle.weather_tag in _TAG_IDS else 0
    temp = oracle.temp_c if oracle.temp_c is not None else -999.0
    rhythm_id = (
        _RHYTHM_IDS.index(oracle.coding_rhythm) if oracle.coding_rhythm in _RHYTHM_IDS else 0
    )
    hours = oracle.hours_since_push if oracle.hours_since_push is not None else -1.0
    flags = (
        (0b0001 if oracle.in_meeting else 0)
        | (0b0010 if oracle.meeting_soon else 0)
        | (0b0100 if oracle.free_rest else 0)
        | (0b1000 if oracle.cal_known else 0)
    )
    load_id = _LOAD_IDS.index(oracle.day_load) if oracle.day_load in _LOAD_IDS else 0
    return struct.pack(
        _FMT,
        tag_id,
        oracle.moon_phase,
        1 if oracle.sunset_soon else 0,
        temp,
        oracle.moon_illum,
        rhythm_id,
        hours,
        flags,
        load_id,
    )


def _oracle_from(
    tag_id,
    phase,
    sunset,
    temp,
    illum,
    rhythm_id,
    hours,
    in_meeting,
    meeting_soon,
    day_load,
    free_rest,
    cal_known,
):
    return Oracle(
        weather_tag=_TAG_IDS[tag_id] if tag_id < len(_TAG_IDS) else "clear",
        temp_c=None if temp < -900.0 else temp,
        moon_phase=phase,
        moon_illum=illum,
        sunset_soon=bool(sunset),
        coding_rhythm=_RHYTHM_IDS[rhythm_id] if rhythm_id < len(_RHYTHM_IDS) else "idle",
        hours_since_push=None if hours < 0.0 else hours,
        in_meeting=in_meeting,
        meeting_soon=meeting_soon,
        day_load=day_load,
        free_rest=free_rest,
        cal_known=cal_known,
    )


def unpack(blob):
    """Unpack binary form back into an Oracle. Old (pre-calendar) blobs read as cal unknown."""
    if len(blob) >= SIZE:
        tag_id, phase, sunset, temp, illum, rhythm_id, hours, flags, load_id = struct.unpack(
            _FMT, blob[:SIZE]
        )
        return _oracle_from(
            tag_id,
            phase,
            sunset,
            temp,
            illum,
            rhythm_id,
            hours,
            bool(flags & 0b0001),
            bool(flags & 0b0010),
            _LOAD_IDS[load_id] if load_id < len(_LOAD_IDS) else "light",
            bool(flags & 0b0100),
            bool(flags & 0b1000),
        )
    tag_id, phase, sunset, temp, illum, rhythm_id, hours = struct.unpack(_FMT_OLD, blob[:SIZE_OLD])
    return _oracle_from(
        tag_id,
        phase,
        sunset,
        temp,
        illum,
        rhythm_id,
        hours,
        False,
        False,
        "light",
        True,
        False,
    )


_NVM_OFFSET = 512  # fixed slot safely past the state blob and the journal ring


def save_cache(oracle):
    """Persist the oracle to its NVM slot. Device-only."""
    import microcontroller

    microcontroller.nvm[_NVM_OFFSET : _NVM_OFFSET + SIZE] = pack(oracle)


def load_cache():
    """Read the cached oracle from NVM, or None if absent/invalid. Device-only."""
    import microcontroller

    try:
        blob = bytes(microcontroller.nvm[_NVM_OFFSET : _NVM_OFFSET + SIZE])
        o = unpack(blob)
        if o.moon_phase > 7:
            return None
        return o
    except Exception:
        return None
