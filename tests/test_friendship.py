from slime.friendship import (
    VISIT_GAP,
    personal_dreams_unlocked,
    tier,
    unlocked_forms,
    update,
)


def test_positive_event_raises_familiarity():
    fam, visits = update(10.0, 0, ("double_tap",), gap=5.0)
    assert fam > 10.0
    assert visits == 0  # short gap -> not a new visit


def test_return_after_long_gap_counts_as_visit():
    fam, visits = update(10.0, 2, ("tap",), gap=VISIT_GAP + 1.0)
    assert visits == 3
    assert fam > 10.0 + 1.5  # got the larger visit bonus too


def test_no_events_no_change():
    fam, visits = update(30.0, 4, (), gap=99999.0)
    assert fam == 30.0 and visits == 4


def test_familiarity_never_exceeds_100():
    fam, _ = update(99.5, 0, ("double_tap", "pickup"), gap=VISIT_GAP + 1)
    assert fam == 100.0


def test_tiers_increase_with_familiarity():
    assert tier(0.0) == 0
    assert tier(25.0) == 1
    assert tier(45.0) == 2
    assert tier(65.0) == 3
    assert tier(85.0) == 4


def test_form_unlocks_by_tier():
    assert "explorer" not in unlocked_forms(0)
    assert "explorer" in unlocked_forms(1)
    assert "crowned" not in unlocked_forms(2)
    assert "crowned" in unlocked_forms(3)


def test_personal_dreams_unlock_at_tier_2():
    assert personal_dreams_unlocked(1) is False
    assert personal_dreams_unlocked(2) is True
