"""Tests for the pure quip selection module."""

from slime.quips import QUIPS, pick


def test_every_expression_and_behavior_tag_has_quips():
    for tag in ("content", "sleepy", "curious", "happy", "contemplative", "greeting"):
        assert tag in QUIPS
        assert len(QUIPS[tag]) >= 2


def test_pick_returns_a_string_from_the_tag_pool():
    chosen = pick("sleepy", choice=lambda seq: seq[0])
    assert chosen == QUIPS["sleepy"][0]


def test_pick_unknown_tag_returns_none():
    assert pick("nonsense", choice=lambda seq: seq[0]) is None


def test_pick_is_deterministic_with_injected_choice():
    chosen = pick("greeting", choice=lambda seq: seq[-1])
    assert chosen == QUIPS["greeting"][-1]


def test_bonded_pool_exists_for_high_tier_personal_quips():
    assert "bonded" in QUIPS
    assert len(QUIPS["bonded"]) >= 2
    assert pick("bonded", choice=lambda seq: seq[0]) == QUIPS["bonded"][0]
