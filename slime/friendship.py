"""Pure friendship/familiarity model. Grows from interaction + visits; never falls."""

PER_EVENT = 1.5  # familiarity gained per positive interaction
PER_VISIT = 6.0  # extra gained when activity resumes after a long quiet gap
VISIT_GAP = 1800.0  # seconds of quiet before a return counts as a new visit
_POSITIVE = ("double_tap", "tap", "pickup")
_TIER_THRESHOLDS = (20.0, 40.0, 60.0, 80.0)  # -> tiers 0,1,2,3,4


def update(familiarity, visit_count, events, gap):
    """Return (familiarity, visit_count) after applying events.

    Never decreases familiarity.
    """
    has_positive = any(e in _POSITIVE for e in events)
    if has_positive:
        familiarity += PER_EVENT
    if events and gap >= VISIT_GAP:
        familiarity += PER_VISIT
        visit_count += 1
    if familiarity > 100.0:
        familiarity = 100.0
    return familiarity, visit_count


def tier(familiarity):
    """Integer band 0..4 from familiarity."""
    band = 0
    for threshold in _TIER_THRESHOLDS:
        if familiarity >= threshold:
            band += 1
    return band


def unlocked_forms(tier_level):
    """Forms unlocked at a tier.

    Explorer at >=1, crowned at >=3.
    """
    forms = ()
    if tier_level >= 1:
        forms += ("explorer",)
    if tier_level >= 3:
        forms += ("crowned",)
    return forms


def personal_dreams_unlocked(tier_level):
    """Personal dream references unlock at tier 2+."""
    return tier_level >= 2
