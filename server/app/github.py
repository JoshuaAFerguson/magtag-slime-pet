"""GitHub activity -> a privacy-safe coding-rhythm signal. summarize() is pure."""

from datetime import datetime

from . import config

GITHUB_EVENTS_URL = "https://api.github.com/users/{}/events"
# Weighted push activity in the last 24h. GitHub's /users/{u}/events PushEvent payloads often omit
# `size`, so we count each push as >=1 (crediting commit `size` when it is present).
_HEAVY = 5
_LIGHT = 1


def fetch_events(client):
    """GET the configured user's recent events using the PAT. `client` is an httpx.Client."""
    headers = {"Accept": "application/vnd.github+json"}
    if config.GITHUB_TOKEN:
        headers["Authorization"] = "token " + config.GITHUB_TOKEN
    resp = client.get(GITHUB_EVENTS_URL.format(config.GITHUB_USER), headers=headers)
    resp.raise_for_status()
    return resp.json()


def _parse_dt(iso):
    if not iso:
        return None
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return None


def summarize(events, now):
    """Pure: events list + tz-aware `now` -> {coding_rhythm, hours_since_push}."""
    activity = 0
    last_push = None
    for ev in events:
        if ev.get("type") != "PushEvent":
            continue
        created = _parse_dt(ev.get("created_at"))
        if created is None:
            continue
        if (now - created).total_seconds() / 3600.0 <= 24:
            size = ev.get("payload", {}).get("size")
            activity += size if isinstance(size, int) and size > 0 else 1
        if last_push is None or created > last_push:
            last_push = created

    if activity >= _HEAVY:
        rhythm = "heavy"
    elif activity >= _LIGHT:
        rhythm = "light"
    else:
        rhythm = "idle"
    hours = None if last_push is None else round((now - last_push).total_seconds() / 3600.0, 2)
    return {"coding_rhythm": rhythm, "hours_since_push": hours}
