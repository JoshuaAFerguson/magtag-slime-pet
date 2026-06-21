"""LLM dream generation. build_prompt/clean_dream are pure; provider calls use httpx.

Only derived mood buckets/tone-words go to the model; only a short dream line comes back.
"""

import httpx

from . import config


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
        "recent days felt: {tones}; small treasures found: {artifacts}."
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
    memory_hint = context.get("memory")
    if memory_hint:
        user += " You may gently reference this remembered moment: {}.".format(memory_hint)
    user += " Write the dream now."
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


def _ollama(system, user, url, model):
    """Call a local Ollama /api/generate. Returns raw text; raises on HTTP error."""
    with httpx.Client(timeout=25) as client:
        resp = client.post(
            url.rstrip("/") + "/api/generate",
            json={"model": model, "system": system, "prompt": user, "stream": False},
        )
        resp.raise_for_status()
        return resp.json().get("response", "")


def _anthropic(system, user, key, model):
    """Call the Anthropic Messages REST API. Returns raw text; raises on HTTP error."""
    with httpx.Client(timeout=25) as client:
        resp = client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": model,
                "max_tokens": 200,
                "system": system,
                "messages": [{"role": "user", "content": user}],
            },
        )
        resp.raise_for_status()
        parts = resp.json().get("content", [])
        return "".join(p.get("text", "") for p in parts if p.get("type") == "text")


def generate_dream(context):
    """Generate a cleaned dream line for the context, or None (unconfigured/empty/any error)."""
    provider = config.DREAM_PROVIDER
    if not provider:
        return None
    try:
        system, user = build_prompt(context, config.DREAM_MAX_CHARS)
        if provider == "ollama":
            raw = _ollama(system, user, config.OLLAMA_URL, config.OLLAMA_MODEL)
        elif provider == "anthropic":
            raw = _anthropic(system, user, config.ANTHROPIC_API_KEY, config.ANTHROPIC_MODEL)
        else:
            return None
        return clean_dream(raw, config.DREAM_MAX_CHARS) or None
    except Exception:
        return None
