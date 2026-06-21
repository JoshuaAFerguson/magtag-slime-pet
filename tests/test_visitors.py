from collections import namedtuple

from slime import visitors

Ora = namedtuple("Ora", "weather_tag moon_phase")


def test_full_moon_makes_owl_eligible():
    keys = visitors.eligible_visitors(Ora("clear", 4), None, 0)
    assert "owl" in keys


def test_rain_makes_snail_eligible():
    assert "snail" in visitors.eligible_visitors(Ora("monsoon", 2), None, 0)
    assert "snail" in visitors.eligible_visitors(Ora("rain", 2), None, 0)


def test_season_and_bond_visitors():
    assert "fox" in visitors.eligible_visitors(None, "winter", 0)
    assert "beetle" in visitors.eligible_visitors(None, "autumn", 0)
    assert "sparrow" in visitors.eligible_visitors(None, "spring", 0)
    assert "cat" in visitors.eligible_visitors(None, None, 3)  # bond alone


def test_nothing_eligible_when_no_signals():
    assert visitors.eligible_visitors(None, "summer", 0) == ()


def test_pick_visitor_uses_choice_and_handles_empty():
    assert visitors.pick_visitor(("owl", "fox"), lambda ks: ks[1]) == "fox"
    assert visitors.pick_visitor((), lambda ks: ks[0]) is None


def test_collect_sets_bit_idempotently():
    m = visitors.collect(0, visitors.bit("owl"))
    assert m & visitors.bit("owl")
    assert visitors.collect(m, visitors.bit("owl")) == m  # idempotent
    m2 = visitors.collect(m, visitors.bit("fox"))
    assert m2 & visitors.bit("owl") and m2 & visitors.bit("fox")  # never clears


def test_roster_lookups_round_trip():
    assert isinstance(visitors.name("owl"), str)
    assert "owl" in visitors.quip("owl") or isinstance(visitors.quip("owl"), str)
    assert isinstance(visitors.glyph("snail"), int)
    # 8 distinct bits filling one byte
    bits = [visitors.bit(k) for k in visitors.KEYS]
    assert len(set(bits)) == 8 and (sum(bits) == 0xFF)
