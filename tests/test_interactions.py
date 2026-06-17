from slime.interactions import (
    AccelReading, Detector, new_detector, detect,
    TAP, DOUBLE_TAP, SHAKE, PICKUP, SETDOWN, FLIP,
)

REST = AccelReading(x=0.0, y=0.0, z=9.8, tapped=False, double_tapped=False)


def test_double_tap_flag_yields_double_tap_event():
    events, _ = detect(new_detector(), REST._replace(double_tapped=True))
    assert DOUBLE_TAP in events


def test_single_tap_flag_yields_tap_event():
    events, _ = detect(new_detector(), REST._replace(tapped=True))
    assert TAP in events


def test_flip_detected_when_z_inverts():
    flipped = AccelReading(x=0.0, y=0.0, z=-9.8, tapped=False, double_tapped=False)
    events, _ = detect(new_detector(), flipped)
    assert FLIP in events


def test_shake_detected_on_high_magnitude():
    shaken = AccelReading(x=22.0, y=18.0, z=9.8, tapped=False, double_tapped=False)
    events, _ = detect(new_detector(), shaken)
    assert SHAKE in events


def test_pickup_then_setdown_transitions():
    d = new_detector()
    _, d = detect(d, REST)
    _, d = detect(d, REST)
    moving = AccelReading(x=3.0, y=3.0, z=11.0, tapped=False, double_tapped=False)
    events, d = detect(d, moving)
    assert PICKUP in events
    _, d = detect(d, REST)
    events, d = detect(d, REST)
    assert SETDOWN in events


def test_rest_produces_no_events():
    d = new_detector()
    _, d = detect(d, REST)
    events, _ = detect(d, REST)
    assert events == ()
