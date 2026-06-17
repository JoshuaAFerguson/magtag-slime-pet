"""Slime Pet — Local Soul entry point. Runs on the MagTag under CircuitPython."""

import time

from slime import dreams, friendship, persistence, power
from slime.forms import choose_render
from slime.interactions import detect, new_detector
from slime.mood import Inputs, step
from slime.motifs import pick_motif
from slime.quips import pick
from slime.state import evolve
from slime.visuals import CONTINUOUS, choose_run_mode, should_refresh

# Refresh / timing constants.
_MIN_REFRESH = 180.0
_SCHEDULED = 21600.0
_NAP_SECONDS = 1800.0
_TICK = 0.05
_SLEEPY_FRAME = 85.0  # sleepiness at/above which the slime counts as "sleeping" (loaf)


def _new_adapter(factory):
    """Construct a hardware adapter, returning None on failure (never kill the creature)."""
    try:
        return factory()
    except Exception:
        return None


def _gather(sensors, detector, last_event_time, now):
    """Read senses into Inputs; return (inputs, events, detector, last_event_time, gap)."""
    if sensors is None:
        return (
            Inputs(
                light=0.5,
                battery=1.0,
                on_usb=True,
                seconds_since_interaction=now - last_event_time,
                events=(),
            ),
            (),
            detector,
            last_event_time,
            now - last_event_time,
        )
    reading = sensors.reading()
    events, detector = detect(detector, reading)
    gap = now - last_event_time
    if events:
        last_event_time = now
    inputs = Inputs(
        light=sensors.light(),
        battery=sensors.battery(),
        on_usb=sensors.on_usb(),
        seconds_since_interaction=gap,
        events=events,
    )
    return inputs, events, detector, last_event_time, gap


def _render_frame(display, state):
    """Render the current form + an expression-appropriate quip. Returns updated state."""
    if not display:
        return state
    sleeping = state.mood.sleepiness >= _SLEEPY_FRAME
    ftier = friendship.tier(state.familiarity)
    frame = choose_render(state.mood, ftier, sleeping)
    tag = "bonded" if ftier >= 3 else state.expression
    quip = pick(tag) or pick(state.expression)
    try:
        display.render_frame(frame, quip or "")
        state = evolve(state, last_seen=time.monotonic())
    except Exception:
        pass
    return state


def _choice(seq):
    """Pick a random element (CircuitPython has random.choice)."""
    import random

    return random.choice(seq)


def _dream_on_wake(display, sound, state):
    """Generate and show a dream + maybe an artifact. Returns updated state."""
    fam_tier = friendship.tier(state.familiarity)
    line, artifact_id = dreams.generate(fam_tier, state.artifacts, _choice)
    artifact_name = ""
    artifacts = state.artifacts
    if artifact_id is not None and not dreams.has_artifact(artifacts, artifact_id):
        artifacts = dreams.add_artifact(artifacts, artifact_id)
        artifact_name = dreams.artifact_name(artifact_id)
    if sound:
        sound.play(pick_motif("dream"))
    if display:
        try:
            display.render_dream(line, artifact_name)
        except Exception:
            pass
    return evolve(state, artifacts=artifacts, last_seen=time.monotonic())


def main():
    from slime.display import Display
    from slime.pixels import Pixels
    from slime.sensors import Sensors
    from slime.sound import Sound

    now = time.monotonic()
    state = persistence.load(now)
    sensors = _new_adapter(Sensors)
    pixels = _new_adapter(Pixels)
    display = _new_adapter(Display)
    sound = _new_adapter(Sound)
    detector = new_detector()
    last_event_time = time.monotonic()

    woke_deep = power.woke_from_deep_sleep()

    # If we woke from a long deep-sleep nap, that was a "night" — dream first.
    # (No autonomous boot chirp: the slime must never beep unprompted.)
    if woke_deep and dreams.should_dream(True, _NAP_SECONDS):
        state = _dream_on_wake(display, sound, state)

    inputs, events, detector, last_event_time, gap = _gather(
        sensors, detector, last_event_time, now
    )
    state = step(state, inputs, 1.0)
    if "double_tap" in events:
        state = evolve(state, total_boops=state.total_boops + 1)
    fam, visits = friendship.update(state.familiarity, state.visit_count, events, gap)
    state = evolve(state, familiarity=fam, visit_count=visits)

    # Cold boot always paints; a deep-sleep wake (post-dream) repaints the creature too.
    state = _render_frame(display, state)
    persistence.save(state)

    if choose_run_mode(inputs.on_usb, inputs.battery) == CONTINUOUS:
        t0 = time.monotonic()
        while True:
            now = time.monotonic()
            inputs, events, detector, last_event_time, gap = _gather(
                sensors, detector, last_event_time, now
            )
            if events:
                prev = state.expression
                state = step(state, inputs, 1.0)
                if "double_tap" in events:
                    state = evolve(state, total_boops=state.total_boops + 1)
                fam, visits = friendship.update(state.familiarity, state.visit_count, events, gap)
                state = evolve(state, familiarity=fam, visit_count=visits)
                ftier = friendship.tier(state.familiarity)
                # Sound ONLY on a deliberate greeting (double-tap) — never unprompted, so the
                # slime won't beep from a desk bump or during a meeting. Dizzy stays pixel-only.
                if sound and state.behavior == "greeting":
                    sound.play(pick_motif("greeting", ftier))
                if state.behavior == "dizzy" and pixels:
                    pixels.flash((120, 0, 0))
                    time.sleep(0.4)
                if should_refresh(
                    time.monotonic(),
                    state.last_seen,
                    pose_changed=(state.expression != prev),
                    significant_event=("double_tap" in events),
                    min_interval=_MIN_REFRESH,
                    scheduled_interval=_SCHEDULED,
                ):
                    state = _render_frame(display, state)
                persistence.save(state)
            if pixels:
                rate = 0.12 + (state.mood.energy / 100.0) * 0.35
                pixels.breathe(state.mood, time.monotonic() - t0, rate=rate)
            time.sleep(_TICK)
    else:
        t0 = time.monotonic()
        while time.monotonic() - t0 < 4.0:
            if pixels:
                pixels.breathe(state.mood, time.monotonic() - t0, rate=0.2)
            time.sleep(_TICK)
        if pixels:
            pixels.off()
        if sound:
            sound.play(pick_motif("sleepy"))
        power.nap(_NAP_SECONDS)


# CircuitPython runs code.py as __main__; the guard keeps host imports from running main().
if __name__ == "__main__":
    main()
