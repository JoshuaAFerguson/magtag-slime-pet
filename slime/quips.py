"""Pure quip selection. The slime's occasional one-line voice. No hardware imports."""

try:
    from random import choice as _default_choice
except ImportError:  # pragma: no cover

    def _default_choice(seq):
        return seq[0]


QUIPS = {
    "content": (
        "warm light today",
        "the desk is calm",
        "i am here",
    ),
    "sleepy": (
        "soft and slow",
        "almost dreaming",
        "the dark is gentle",
    ),
    "curious": (
        "what was that?",
        "something moved",
        "i wonder",
    ),
    "happy": (
        "you came back",
        "good to see you",
        "a fine moment",
    ),
    "contemplative": (
        "the silver pond is quiet",
        "i remember the seventh moon",
        "time passes softly",
    ),
    "greeting": (
        "oh! hello",
        "there you are",
        "hi hi",
    ),
    "bonded": (
        "i kept your warmth",
        "you again — good",
        "our quiet is the best quiet",
    ),
    "spring": (
        "everything is waking",
        "green and new",
        "the air feels young",
    ),
    "summer": (
        "long bright hours",
        "i want to wander",
        "warm all the way through",
    ),
    "autumn": (
        "the light goes gold",
        "i think back often",
        "a season for quiet",
    ),
    "winter": (
        "cozy and slow",
        "the cold is gentle",
        "wrapped up small",
    ),
    "heat": (
        "the air shimmers",
        "i am melting, slowly",
        "too warm to move",
    ),
    "rain": (
        "i smell the rain",
        "everything drinks",
        "petrichor",
    ),
    "storm": (
        "something is coming",
        "i will hide a while",
        "the sky feels heavy",
    ),
    "sunset": (
        "look at that light",
        "the day bows out",
        "gold on everything",
    ),
    "full_moon": (
        "the moon is full tonight",
        "bright even with eyes closed",
        "a night for wandering dreams",
    ),
    "new_moon": (
        "the sky is deep and dark",
        "the moon is hiding too",
        "quiet under no moon",
    ),
    "busy": (
        "you've been deep in work",
        "i watched the clouds while you worked",
        "good work today",
    ),
    "quiet": (
        "it's quiet without you",
        "where did you wander?",
        "i kept your seat warm",
    ),
}


def pick(tag, choice=_default_choice):
    """Return one quip for `tag`, or None if the tag is unknown."""
    pool = QUIPS.get(tag)
    if not pool:
        return None
    return choice(pool)
