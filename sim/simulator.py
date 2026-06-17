"""Run the pure mood loop over a scripted day. No hardware. Run: python3 sim/simulator.py"""

from collections import namedtuple

from slime import friendship
from slime.mood import Inputs, step
from slime.quips import pick
from slime.state import default_state, evolve

Tick = namedtuple(
    "Tick", ("hour", "light", "mood", "expression", "behavior", "quip", "familiarity")
)

# A scripted 24-hour arc: (hour, light 0..1, events).
_SCRIPT = [
    (0, 0.02, ()),
    (2, 0.01, ()),
    (4, 0.01, ()),
    (6, 0.15, ()),
    (7, 0.6, ("double_tap",)),
    (9, 0.8, ()),
    (12, 0.95, ("pickup",)),
    (14, 0.85, ()),
    (17, 0.7, ("tap",)),
    (19, 0.4, ("setdown",)),
    (21, 0.2, ()),
    (23, 0.05, ()),
]
_STEP_SECONDS = 3600.0


def run_day():
    """Return a list of Tick across the scripted day, tracking familiarity."""
    state = default_state(now=0.0)
    timeline = []
    last_interaction = 0.0
    for hour, light, events in _SCRIPT:
        now = hour * 3600.0
        gap = now - last_interaction
        if events:
            last_interaction = now
        inputs = Inputs(
            light=light,
            battery=0.8,
            on_usb=True,
            seconds_since_interaction=gap,
            events=events,
        )
        state = step(state, inputs, dt=_STEP_SECONDS)
        fam, visits = friendship.update(state.familiarity, state.visit_count, events, gap)
        state = evolve(state, familiarity=fam, visit_count=visits)
        quip = pick(
            state.behavior if state.behavior == "greeting" else state.expression,
            choice=lambda seq: seq[0],
        )
        timeline.append(
            Tick(
                hour,
                light,
                state.mood,
                state.expression,
                state.behavior,
                quip,
                state.familiarity,
            )
        )
    return timeline


def main():
    for t in run_day():
        bar = "#" * int(t.mood.sleepiness / 5)
        print(
            f"{t.hour:02d}:00  light={t.light:0.2f}  {t.expression:<13} "
            f'{t.behavior:<10} sleepy|{bar:<20}|  "{t.quip}"'
            f"  fam={t.familiarity:0.1f}"
        )


if __name__ == "__main__":
    main()
