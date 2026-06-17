"""Tests for pure tone-motif data and selection."""

from slime.motifs import pick_motif


def test_known_contexts_return_tone_sequences():
    """Known contexts return valid tone sequences."""
    for context in ("greeting", "wake", "dizzy", "sleepy", "dream"):
        motif = pick_motif(context)
        assert motif and all(len(step) == 2 for step in motif)  # (freq, ms) pairs


def test_unknown_context_returns_none():
    """Unknown context returns None."""
    assert pick_motif("nonsense") is None


def test_high_tier_greeting_is_richer():
    """Higher tier greeting is richer and at least as long."""
    base = pick_motif("greeting", tier=0)
    bonded = pick_motif("greeting", tier=3)
    assert bonded != base
    assert len(bonded) >= len(base)
