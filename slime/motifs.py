"""Pure tone-sequence data + selection. Each motif is a tuple of (freq_hz, duration_ms)."""

MOTIFS = {
    "greeting": ((660, 90), (880, 120)),
    "wake": ((523, 80), (659, 90)),
    "dizzy": ((420, 70), (300, 70), (420, 70)),
    "sleepy": ((440, 130), (330, 170)),
    "dream": ((784, 70), (988, 90), (1319, 140)),
}

# A warmer greeting unlocked once the bond is deep (tier 3+).
_BONDED_GREETING = ((660, 90), (880, 90), (1047, 150))


def pick_motif(context, tier=0):
    """Return the (freq, ms) sequence for a context, or None if unknown."""
    if context == "greeting" and tier >= 3:
        return _BONDED_GREETING
    return MOTIFS.get(context)
