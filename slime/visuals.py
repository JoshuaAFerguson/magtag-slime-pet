"""Pure presentation & power-mode decisions. No hardware imports."""
import math
from slime.mood import derive_expression

# Sprite-sheet frame index per expression/behavior. Authored to match assets/slime.bmp.
POSE_INDEX = {
    "content": 0,
    "sleepy": 1,
    "curious": 2,
    "happy": 3,
    "contemplative": 4,
    "dizzy": 5,
    "resting": 6,
}

# Mood-tinted NeoPixel colors (R, G, B), 0..255.
_EXPRESSION_RGB = {
    "content": (0, 110, 110),       # calm teal
    "sleepy": (10, 20, 90),         # dim blue
    "curious": (150, 90, 0),        # amber
    "happy": (140, 40, 90),         # rose
    "contemplative": (40, 30, 90),  # dusk violet
}

CONTINUOUS = "continuous"
WAKE_CYCLE = "wake_cycle"


def expression_to_pose(expression: str) -> int:
    """Map an expression name to a sprite-sheet frame index."""
    return POSE_INDEX.get(expression, POSE_INDEX["resting"])


def mood_to_rgb(mood) -> tuple:
    """Pick a NeoPixel color triple from the dominant mood (shares mood.derive_expression)."""
    expr = derive_expression(mood)
    return _EXPRESSION_RGB.get(expr, _EXPRESSION_RGB["content"])


def breath_brightness(t: float, rate: float = 0.25, lo: float = 0.05, hi: float = 0.5) -> float:
    """Sine breathing curve in [lo, hi]. `rate` is cycles per second, `t` in seconds."""
    phase = math.sin(2.0 * math.pi * rate * t)
    return lo + (hi - lo) * (phase * 0.5 + 0.5)


def should_refresh(
    now: float,
    last_refresh: float,
    pose_changed: bool,
    significant_event: bool,
    min_interval: float,
    scheduled_interval: float,
) -> bool:
    """Decide whether to repaint the slow E-Ink panel."""
    age = now - last_refresh
    if significant_event:
        return True
    if pose_changed and age >= min_interval:
        return True
    if age >= scheduled_interval:
        return True
    return False


def choose_run_mode(on_usb: bool, battery: float) -> str:
    """USB -> always breathing; battery -> motion-wake bursts."""
    return CONTINUOUS if on_usb else WAKE_CYCLE
