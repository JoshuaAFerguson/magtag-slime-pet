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
}


def pick(tag, choice=_default_choice):
    """Return one quip for `tag`, or None if the tag is unknown."""
    pool = QUIPS.get(tag)
    if not pool:
        return None
    return choice(pool)
