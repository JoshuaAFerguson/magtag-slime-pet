"""Pure long-term milestones: notable firsts the pet has reached, as an NVM bitmask.

evaluate() never clears bits (a milestone, once reached, is remembered forever).
"""

FIRST_STORM = 0b00001
FULL_MOON_NIGHT = 0b00010
BONDED = 0b00100
COLLECTOR = 0b01000
FAITHFUL = 0b10000

_ALL_ARTIFACTS = 0xFF  # all 8 dream artifacts collected
_FAITHFUL_SECONDS = 7 * 24 * 3600.0  # a week-long absence weathered, then a return

_RECALL = (
    (FIRST_STORM, "i still remember our first storm"),
    (FULL_MOON_NIGHT, "i think of the night the moon was full"),
    (BONDED, "we have come a long way, you and i"),
    (COLLECTOR, "i kept every little treasure we found"),
    (FAITHFUL, "i waited, and you came back"),
)


def evaluate(flags, oracle, state, tier):
    """Return `flags` with any newly-met milestone bits set. Pure; never clears bits."""
    new = flags
    if oracle is not None:
        if oracle.weather_tag in ("storm_incoming", "monsoon"):
            new |= FIRST_STORM
        if oracle.moon_phase == 4:
            new |= FULL_MOON_NIGHT
    if tier >= 3:
        new |= BONDED
    if (state.artifacts & _ALL_ARTIFACTS) == _ALL_ARTIFACTS:
        new |= COLLECTOR
    if state.longest_absence >= _FAITHFUL_SECONDS:
        new |= FAITHFUL
    return new


def memory_quip(flags, choice):
    """Voice one unlocked milestone as a recall line, or None if none are unlocked. Pure."""
    unlocked = [line for bit, line in _RECALL if flags & bit]
    if not unlocked:
        return None
    return choice(unlocked)
