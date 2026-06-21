"""Pure visitors: guest creatures summoned by on-device conditions. No hardware imports.

A visit is decided in two pure steps — eligible_visitors() (which creatures the current
world allows) then pick_visitor() (choose one) — plus a keepsake collect(). The rarity roll
lives in code.py. collect() never clears bits (a met visitor is remembered forever).
"""

# (bit, key, name, quip, glyph_index). glyph_index matches the tile order in visitors.bmp.
_ROSTER = (
    (0b00000001, "owl", "Owl", "an owl settled on the sill", 0),
    (0b00000010, "snail", "Snail", "a snail came in from the rain", 1),
    (0b00000100, "firefly", "Firefly", "a firefly blinked hello", 2),
    (0b00001000, "moth", "Moth", "a moth circled the lamp", 3),
    (0b00010000, "fox", "Fox", "a fox passed through the cold", 4),
    (0b00100000, "beetle", "Beetle", "a beetle trundled by", 5),
    (0b01000000, "sparrow", "Sparrow", "a sparrow stopped to rest", 6),
    (0b10000000, "cat", "Cat", "a neighbor's cat curled up", 7),
)

KEYS = tuple(r[1] for r in _ROSTER)

_BY_KEY = {r[1]: r for r in _ROSTER}


def _condition(key, oracle, season, tier):
    """True when `key`'s visitor is eligible under the current world. Pure; tolerates None."""
    if key == "owl":
        return oracle is not None and oracle.moon_phase == 4
    if key == "snail":
        return oracle is not None and oracle.weather_tag in ("rain", "monsoon")
    if key == "firefly":
        return oracle is not None and oracle.weather_tag == "extreme_heat"
    if key == "moth":
        return oracle is not None and oracle.moon_phase == 0
    if key == "fox":
        return season == "winter"
    if key == "beetle":
        return season == "autumn"
    if key == "sparrow":
        return season == "spring"
    if key == "cat":
        return tier >= 3
    return False


def eligible_visitors(oracle, season, tier):
    """Tuple of visitor keys whose condition holds right now (in roster order)."""
    return tuple(k for k in KEYS if _condition(k, oracle, season, tier))


def pick_visitor(keys, choice):
    """Choose one key via `choice`, or None when `keys` is empty."""
    if not keys:
        return None
    return choice(keys)


def collect(mask, a_bit):
    """Set `a_bit` in the keepsake mask; never clears other bits."""
    return mask | a_bit


def bit(key):
    """The keepsake bit for a visitor key."""
    return _BY_KEY[key][0]


def name(key):
    """Display name for a visitor key."""
    return _BY_KEY[key][2]


def quip(key):
    """The one-line quip announcing a visitor."""
    return _BY_KEY[key][3]


def glyph(key):
    """The visitors.bmp tile index for a visitor key."""
    return _BY_KEY[key][4]
