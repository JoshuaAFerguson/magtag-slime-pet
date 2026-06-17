"""Pure seasonal logic: month -> season, mood bias, sprite/accent frames. No hardware imports."""

from slime.state import MOOD_FIELDS, Mood, clamp_mood

SEASONS = ("winter", "spring", "summer", "autumn")

_MONTH_SEASON = {
    12: "winter",
    1: "winter",
    2: "winter",
    3: "spring",
    4: "spring",
    5: "spring",
    6: "summer",
    7: "summer",
    8: "summer",
    9: "autumn",
    10: "autumn",
    11: "autumn",
}

# Frame indices into visuals.POSE_INDEX (seasonal forms) and accent frames.
_FORM_FRAME = {"spring": 12, "summer": 13, "autumn": 14, "winter": 15}
_ACCENT_FRAME = {"spring": 0, "summer": 1, "autumn": 2, "winter": 3}

# Gentle per-drive targets the mood drifts toward in each season.
_TARGETS = {
    "spring": {"energy": 70.0, "curiosity": 65.0},
    "summer": {"curiosity": 70.0, "energy": 68.0},
    "autumn": {"sleepiness": 55.0, "comfort": 68.0},
    "winter": {"comfort": 75.0, "sleepiness": 58.0},
}


def season_of(month):
    """Return the season name for a given month (1-12)."""
    return _MONTH_SEASON[month]


def apply_bias(mood, season, rate=0.05):
    """Nudge biased drives a small step toward seasonal targets.

    Self-limiting; returns new Mood with convergence behavior.
    """
    targets = _TARGETS[season]
    vals = {field: getattr(mood, field) for field in MOOD_FIELDS}
    for drive, target in targets.items():
        vals[drive] += (target - vals[drive]) * rate
    return clamp_mood(Mood(**vals))


def form_frame(season):
    """Return the form frame index for the given season."""
    return _FORM_FRAME[season]


def accent_frame(season):
    """Return the accent frame index for the given season."""
    return _ACCENT_FRAME[season]


def quip_tag(season):
    """Return the quip tag for the given season (identity mapping)."""
    return season
