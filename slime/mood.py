"""Pure mood engine. Inputs -> new State. No hardware imports."""
from collections import namedtuple
from slime.state import Mood, clamp_mood

Inputs = namedtuple(
    "Inputs",
    (
        "light",                      # 0.0 (dark) .. 1.0 (bright)
        "battery",                    # 0.0 .. 1.0
        "on_usb",                     # bool
        "seconds_since_interaction",  # float
        "events",                     # tuple[str, ...]
    ),
)

# Tuning constants (per-minute influence rates, scaled by dt).
_DAY_LIGHT = 0.35          # light level above which it's "daytime"
_SLEEP_GAIN = 8.0          # sleepiness change per minute in full dark/light
_ENERGY_DRAIN = 6.0        # energy lost per minute at empty battery
_COMFORT_BASELINE = 65.0   # comfort drifts toward this when alone
_DRIFT = 3.0               # generic drift per minute toward baseline
_LONELY_AFTER = 3600.0     # seconds alone before curiosity starts to fade

_EVENT_DELTAS = {
    "double_tap": {"affection": 12.0, "curiosity": 8.0, "sleepiness": -6.0},
    "tap": {"affection": 3.0, "curiosity": 3.0},
    "pickup": {"curiosity": 14.0, "sleepiness": -10.0, "energy": 4.0},
    "setdown": {"comfort": 6.0, "curiosity": -4.0},
    "shake": {"comfort": -8.0, "curiosity": 6.0},
    "flip": {"comfort": -10.0, "curiosity": 4.0},
}


def _apply_events(values, events):
    for ev in events:
        for drive, delta in _EVENT_DELTAS.get(ev, {}).items():
            values[drive] += delta
    return values


def step(state, inputs, dt):
    """Advance the mood by `dt` seconds given `inputs`. Returns a new State."""
    minutes = dt / 60.0
    m = state.mood
    values = {
        "energy": m.energy,
        "comfort": m.comfort,
        "curiosity": m.curiosity,
        "sleepiness": m.sleepiness,
        "affection": m.affection,
    }

    if inputs.light < _DAY_LIGHT:
        values["sleepiness"] += _SLEEP_GAIN * minutes
    else:
        values["sleepiness"] -= _SLEEP_GAIN * minutes

    values["energy"] += (inputs.battery - 0.5) * 2.0 * _ENERGY_DRAIN * minutes

    if state.mood.comfort < _COMFORT_BASELINE:
        values["comfort"] += _DRIFT * minutes
    else:
        values["comfort"] -= _DRIFT * minutes * 0.5

    if inputs.seconds_since_interaction > _LONELY_AFTER:
        values["curiosity"] -= _DRIFT * minutes

    values = _apply_events(values, inputs.events)

    mood = clamp_mood(
        Mood(
            energy=values["energy"],
            comfort=values["comfort"],
            curiosity=values["curiosity"],
            sleepiness=values["sleepiness"],
            affection=values["affection"],
        )
    )
    return state._replace(
        mood=mood,
        expression=derive_expression(mood),
        behavior=derive_behavior(mood, inputs.events),
    )


def derive_expression(mood):
    """Pick the visible expression from the dominant drive."""
    if mood.sleepiness >= 75.0:
        return "sleepy"
    if mood.affection >= 75.0 and mood.energy >= 50.0:
        return "happy"
    if mood.curiosity >= 70.0:
        return "curious"
    if mood.curiosity <= 30.0 and mood.energy <= 40.0:
        return "contemplative"
    return "content"


def derive_behavior(mood, events):
    """Events take priority over steady-state behavior."""
    if "flip" in events or "shake" in events:
        return "dizzy"
    if "double_tap" in events:
        return "greeting"
    if "pickup" in events:
        return "attentive"
    if "setdown" in events:
        return "settling"
    return "idle"
