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


def _gather(sensors, detector, last_event_time, now):
    """Read the senses into mood Inputs. Tracks real elapsed time since the last event.

    Returns (inputs, events, detector, last_event_time). When no sensors are available
    the slime stays calm and present rather than crashing (Rule 1: never dies).
    """
    if sensors is None:
        inputs = Inputs(light=0.5, battery=1.0, on_usb=True,
                        seconds_since_interaction=now - last_event_time, events=())
        return inputs, (), detector, last_event_time

    reading = sensors.reading()
    events, detector = detect(detector, reading)
    if events:
        last_event_time = now
    inputs = Inputs(
        light=sensors.light(),
        battery=sensors.battery(),
        on_usb=sensors.on_usb(),
        seconds_since_interaction=now - last_event_time,
        events=events,
    )
    return inputs, events, detector, last_event_time


def _maybe_greet_refresh(display, state, prev_expression, events, significant):
    """Render if the refresh policy allows; returns a possibly-updated state. Never raises."""
    if not display:
        return state
    if should_refresh(time.monotonic(), state.last_seen,
                      pose_changed=(state.expression != prev_expression),
                      significant_event=significant,
                      min_interval=_MIN_REFRESH, scheduled_interval=_SCHEDULED):
        quip = pick(state.behavior if state.behavior == "greeting" else state.expression)
        try:
            display.render(state.expression, quip or "")
            state = state._replace(last_seen=time.monotonic())
        except Exception:
            pass  # never let a render failure kill the creature
    return state


def main():
    now = time.monotonic()
    state = persistence.load(now)

    # Build the hardware adapters defensively — a failed sensor/display must not
    # kill the creature; it simply lives in a degraded but calm state.
    try:
        sensors = Sensors()
    except Exception:
        sensors = None
    try:
        pixels = Pixels()
    except Exception:
        pixels = None
    try:
        display = Display()
    except Exception:
        display = None

    detector = new_detector()
    last_event_time = time.monotonic()

    # First thought of this wake.
    now = time.monotonic()
    inputs, events, detector, last_event_time = _gather(sensors, detector, last_event_time, now)
    prev_expression = state.expression
    state = step(state, inputs, 1.0)
    if "double_tap" in events:
        state = state._replace(total_boops=state.total_boops + 1)
    state = _maybe_greet_refresh(display, state, prev_expression, events, bool(events))

    persistence.save(state)

    if choose_run_mode(inputs.on_usb, inputs.battery) == CONTINUOUS:
        # Always-breathing desk mode.
        t0 = time.monotonic()
        while True:
            now = time.monotonic()
            inputs, events, detector, last_event_time = _gather(sensors, detector, last_event_time, now)
            if events:
                prev = state.expression
                state = step(state, inputs, 1.0)
                if "double_tap" in events:
                    state = state._replace(total_boops=state.total_boops + 1)
                if state.behavior == "dizzy" and pixels:
                    pixels.flash((120, 0, 0))
                    time.sleep(0.4)
                # Only a greeting forces an immediate refresh; shakes/flips show via
                # NeoPixels and must not thrash the rate-limited E-Ink panel.
                state = _maybe_greet_refresh(display, state, prev, events, "double_tap" in events)
                persistence.save(state)
            if pixels:
                rate = 0.12 + (state.mood.energy / 100.0) * 0.35  # brisker when energetic
                pixels.breathe(state.mood, time.monotonic() - t0, rate=rate)
            time.sleep(_TICK)
    else:
        # Battery: a short greeting breath, then nap.
        t0 = time.monotonic()
        while time.monotonic() - t0 < 4.0:
            if pixels:
                pixels.breathe(state.mood, time.monotonic() - t0, rate=0.2)
            time.sleep(_TICK)
        if pixels:
            pixels.off()
        power.nap(_NAP_SECONDS)


# CircuitPython runs code.py as the main script (__name__ == "__main__"), so the
# slime starts on the device. The guard prevents main() from running (and pulling
# in hardware imports) if this file is ever imported on the host — e.g. the stdlib
# `code` module that pdb imports, which this file would otherwise shadow.
if __name__ == "__main__":
    main()
