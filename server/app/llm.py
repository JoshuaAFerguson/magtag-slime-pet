"""LLM dream generation. build_prompt/clean_dream are pure; provider calls use httpx.

Only derived mood buckets/tone-words go to the model; only a short dream line comes back.
"""


def build_prompt(context, max_chars=120):
    """Build (system, user) prompts from a derived-context dict. Pure; tolerant of missing keys."""

    def g(key, default):
        value = context.get(key, default)
        return default if value in (None, "") else value

    system = (
        "You are the dreaming inner voice of a small, calm slime companion. "
        "Write ONE short dream of at most {} characters, in 1-2 gentle, slightly surreal "
        "sentences, in a soft ambient voice. You may quietly reflect the mood hints, but "
        "NEVER invent specific people, names, real places, or facts about the human. "
        "Output only the dream line: no preamble, no quotation marks."
    ).format(max_chars)

    tones = g("tones", [])
    tones_str = ", ".join(str(t) for t in tones) if tones else "quiet"
    user = (
        "Mood hints - season: {season}; weather: {weather}; moon phase: {moon}; "
        "work rhythm: {rhythm}; day load: {day_load}; inbox: {inbox}; bond level: {fam}; "
        "recent days felt: {tones}; small treasures found: {artifacts}. "
        "Write the dream now."
    ).format(
        season=g("season", "unknown"),
        weather=g("weather", "calm"),
        moon=g("moon", "?"),
        rhythm=g("rhythm", "idle"),
        day_load=g("day_load", "unknown"),
        inbox=g("inbox", "unknown"),
        fam=g("fam", 0),
        tones=tones_str,
        artifacts=g("artifacts", 0),
    )
    return system, user


def clean_dream(text, max_chars=120):
    """Collapse whitespace, strip wrapping quotes, truncate at a word boundary, terminate."""
    if not text:
        return ""
    s = " ".join(text.split()).strip().strip("\"'").strip()
    if not s:
        return ""
    if len(s) > max_chars:
        cut = s[:max_chars]
        if " " in cut:
            cut = cut[: cut.rfind(" ")]
        s = cut.rstrip(",;:- ")
    if s and s[-1] not in ".!?":
        s += "."
    return s
