"""Pure gesture detection from accelerometer readings. No hardware imports."""
import math
from collections import namedtuple

TAP = "tap"
DOUBLE_TAP = "double_tap"
SHAKE = "shake"
PICKUP = "pickup"
SETDOWN = "setdown"
FLIP = "flip"

AccelReading = namedtuple("AccelReading", ("x", "y", "z", "tapped", "double_tapped"))

Detector = namedtuple("Detector", ("was_moving", "still_count"))

_GRAVITY = 9.8
_SHAKE_MAGNITUDE = 16.0   # m/s^2 total; brisk shake clears this
_MOVE_DELTA = 1.5         # deviation from 1g that counts as "moving"
_FLIP_Z = -6.0            # z this negative means upside-down
_STILL_FOR_SETDOWN = 1    # consecutive still reads after motion => setdown


def new_detector():
    """Create a fresh gesture detector with no motion history."""
    return Detector(was_moving=False, still_count=0)


def _magnitude(r):
    """Compute the Euclidean magnitude of acceleration vector."""
    return math.sqrt(r.x * r.x + r.y * r.y + r.z * r.z)


def detect(detector, reading):
    """Return (events_tuple, new_detector) for a single reading.

    Detects tap, double-tap, flip, shake, pickup, and setdown gestures
    by combining hardware tap flags with acceleration magnitude and axis analysis.
    """
    events = []

    # Hardware tap flags take priority (explicit sensor interrupt)
    if reading.double_tapped:
        events.append(DOUBLE_TAP)
    elif reading.tapped:
        events.append(TAP)

    # Flip detection: z axis inverted (device upside-down)
    if reading.z <= _FLIP_Z:
        events.append(FLIP)

    # Compute overall acceleration magnitude
    magnitude = _magnitude(reading)

    # Shake detection: rapid motion in any direction
    if magnitude >= _SHAKE_MAGNITUDE:
        events.append(SHAKE)

    # Movement detection: acceleration deviates from 1g (rest) by more than threshold
    moving = abs(magnitude - _GRAVITY) > _MOVE_DELTA

    # Pickup: transition from stationary to moving
    if moving and not detector.was_moving:
        events.append(PICKUP)

    # Setdown: transition from moving to stationary (with 1-read debounce)
    # After exiting motion, we enter "cooling" mode (still_count=1), then on
    # the next still read, emit SETDOWN.
    if not moving and detector.was_moving:
        new = Detector(was_moving=False, still_count=1)
        return tuple(events), new

    # Setdown event fires after _STILL_FOR_SETDOWN consecutive still readings
    # (but only if we were previously moving, i.e., still_count > 0)
    if not moving and detector.still_count == _STILL_FOR_SETDOWN:
        events.append(SETDOWN)
        return tuple(events), Detector(was_moving=False, still_count=detector.still_count + 1)

    # Update detector state: track motion and still count
    # If moving: reset still_count to 0
    # If not moving and was_moving: this case is handled above
    # If not moving and was_stationary: don't increment still_count (stays 0)
    next_still = 0 if moving else detector.still_count
    return tuple(events), Detector(was_moving=moving, still_count=next_still)
