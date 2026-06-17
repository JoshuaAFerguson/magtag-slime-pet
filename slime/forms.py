"""Pure body-form selection: mood + familiarity tier + sleep + season -> sprite frame index."""

from slime.friendship import unlocked_forms
from slime.mood import derive_expression
from slime.seasons import form_frame
from slime.visuals import POSE_INDEX


def choose_render(mood, tier, sleeping, season=None):
    """Return the sprite frame index to display, in priority order."""
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
    expression = derive_expression(mood)
    if season and expression == "content":
        return form_frame(season)  # seasons owns season->frame index (12-15 == POSE_INDEX)
    return POSE_INDEX[expression]
