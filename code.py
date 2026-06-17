"""Slime Pet — Local Soul entry point. Runs on the MagTag under CircuitPython."""
import time
from slime import persistence
from slime.mood import Inputs, step
from slime.interactions import new_detector, detect
from slime.quips import pick
from slime.visuals import should_refresh, choose_run_mode, CONTINUOUS
from slime.sensors import Sensors
from slime.pixels import Pixels
from slime.display import Display
from slime import power

# Refresh policy constants.
_MIN_REFRESH = 180.0       # seconds; protect the panel from flicker
_SCHEDULED = 21600.0       # seconds (~4x/day) for an unconditional refresh
_NAP_SECONDS = 1800.0      # battery nap length between wake cycles
_TICK = 0.05               # breathing frame period (USB loop)


def _gather(sensors, detector):
    reading = sensors.reading()
    events, detector = detect(detector, reading)
    inputs = Inputs(
        light=sensors.light(),
        battery=sensors.battery(),
        on_usb=sensors.on_usb(),
        seconds_since_interaction=0.0 if events else 60.0,
        events=events,
    )
    return inputs, events, detector


def main():
    now = time.monotonic()
    state = persistence.load(now)
    sensors = Sensors()
    pixels = Pixels()
    display = Display()
    detector = new_detector()

    # First thought of this wake.
    inputs, events, detector = _gather(sensors, detector)
    prev_expression = state.expression
    state = step(state, inputs, 1.0)
    if events:
        state = state._replace(total_boops=state.total_boops + (1 if "double_tap" in events else 0))

    quip = pick(state.behavior if state.behavior == "greeting" else state.expression)
    if should_refresh(time.monotonic(), state.last_seen,
                      pose_changed=(state.expression != prev_expression),
                      significant_event=bool(events),
                      min_interval=_MIN_REFRESH, scheduled_interval=_SCHEDULED):
        try:
            display.render(state.expression, quip or "")
            state = state._replace(last_seen=time.monotonic())
        except Exception:
            pass  # never let a render failure kill the creature

    persistence.save(state)

    if choose_run_mode(inputs.on_usb, inputs.battery) == CONTINUOUS:
        # Always-breathing desk mode.
        t0 = time.monotonic()
        while True:
            inputs, events, detector = _gather(sensors, detector)
            if events:
                prev = state.expression
                state = step(state, inputs, 1.0)
                if "double_tap" in events:
                    state = state._replace(total_boops=state.total_boops + 1)
                if state.behavior == "dizzy":
                    pixels.flash((120, 0, 0))
                    time.sleep(0.4)
                if should_refresh(time.monotonic(), state.last_seen,
                                  pose_changed=(state.expression != prev),
                                  significant_event=True,
                                  min_interval=_MIN_REFRESH, scheduled_interval=_SCHEDULED):
                    try:
                        display.render(state.expression, pick(
                            state.behavior if state.behavior == "greeting" else state.expression) or "")
                        state = state._replace(last_seen=time.monotonic())
                    except Exception:
                        pass
                persistence.save(state)
            rate = 0.12 + (state.mood.energy / 100.0) * 0.35  # brisker when energetic
            pixels.breathe(state.mood, time.monotonic() - t0, rate=rate)
            time.sleep(_TICK)
    else:
        # Battery: a short greeting breath, then nap.
        t0 = time.monotonic()
        while time.monotonic() - t0 < 4.0:
            pixels.breathe(state.mood, time.monotonic() - t0, rate=0.2)
            time.sleep(_TICK)
        pixels.off()
        power.nap(_NAP_SECONDS)


main()
