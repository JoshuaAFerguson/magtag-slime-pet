"""Pure body-form selection: mood + familiarity tier + sleep -> sprite frame index."""

from slime.friendship import unlocked_forms
from slime.mood import derive_expression
from slime.visuals import POSE_INDEX


def choose_render(mood, tier, sleeping):
    """Return the sprite frame index to display, in priority order.

    Args:
        mood: Mood namedtuple with energy, comfort, curiosity, sleepiness, affection.
        tier: Familiarity tier (0..4).
        sleeping: Boolean indicating sleep state.

    Returns:
        int: Index into POSE_INDEX for the sprite frame to render.
    """
    forms_ok = unlocked_forms(tier)

    if sleeping or mood.sleepiness >= 85.0:
        return POSE_INDEX["loaf"]
    if mood.energy <= 15.0:
        return POSE_INDEX["puddle"]
    if "explorer" in forms_ok and mood.curiosity >= 70.0 and mood.energy >= 60.0:
        return POSE_INDEX["explorer"]
    if "crowned" in forms_ok and mood.affection >= 75.0 and mood.energy >= 50.0:
        return POSE_INDEX["crowned"]
    if mood.curiosity <= 25.0 and mood.energy <= 35.0:
        return POSE_INDEX["wisp"]
    return POSE_INDEX[derive_expression(mood)]
