"""FastAPI home oracle: GET /oracle (weather + moon), GET /health."""

import random
import time
from datetime import datetime, timezone

import httpx
from fastapi import Body, FastAPI, Header, HTTPException
from fastapi.responses import HTMLResponse

from . import calendar, config, github, inbox, journal_view, llm, memory, moon, oracle, weather

app = FastAPI(title="Slime Oracle")


def _check_auth(authorization: str) -> None:
    """Check bearer token auth if ORACLE_TOKEN is configured.

    Reads config.ORACLE_TOKEN dynamically (not a local constant) so
    monkeypatching works in tests.
    """
    token = config.ORACLE_TOKEN
    if not token:
        return
    if authorization != "Bearer " + token:
        raise HTTPException(status_code=401, detail="bad token")


@app.get("/health")
def health() -> dict:
    """Health check endpoint."""
    return {"ok": True}


def _presence():
    """Derive the GitHub presence signal; idle on missing token or any failure."""
    if not config.GITHUB_USER:
        return {"coding_rhythm": "idle", "hours_since_push": None}
    try:
        with httpx.Client(timeout=10) as client:
            events = github.fetch_events(client)
        return github.summarize(events, datetime.now(timezone.utc))
    except Exception:
        return {"coding_rhythm": "idle", "hours_since_push": None}


def _calendar():
    """Derive the calendar block; None (omitted) on missing URL or any failure."""
    if not config.CALENDAR_ICS_URL:
        return None
    try:
        with httpx.Client(timeout=10) as client:
            body = calendar.fetch_ics(client, config.CALENDAR_ICS_URL)
        now = datetime.now(timezone.utc)
        intervals = calendar.expand_today(body, now, config.TZ)
        return calendar.summarize(intervals, now)
    except Exception:
        return None


def _inbox():
    """Derive the inbox block; None (omitted) on missing config or any failure."""
    if not (config.IMAP_HOST and config.IMAP_USER and config.IMAP_PASSWORD):
        return None
    try:
        unread, newest = inbox.fetch_counts(
            config.IMAP_HOST, config.IMAP_USER, config.IMAP_PASSWORD
        )
        return inbox.summarize(unread, newest, int(time.time()))
    except Exception:
        return None


@app.get("/oracle")
def get_oracle(authorization: str = Header(default="")) -> dict:
    """Fetch weather + moon oracle for the configured location.

    Requires valid bearer token if ORACLE_TOKEN is set in config.
    Falls back to moon-only data if weather fetch fails.
    """
    _check_auth(authorization)
    now = datetime.now()
    mooninfo = moon.moon(now.year, now.month, now.day)
    try:
        with httpx.Client(timeout=10) as client:
            raw = weather.fetch_raw(client)
        w = weather.normalize(raw, now_iso=now.isoformat(timespec="minutes"))
    except Exception:
        w = {"tags": [], "temp_c": None, "code": 0, "sunset_soon": False}
    return oracle.build(
        w, mooninfo, _presence(), calendar=_calendar(), inbox=_inbox(), ts=int(time.time())
    )


@app.post("/dream")
def post_dream(body: dict = Body(default={}), authorization: str = Header(default="")) -> dict:
    """Generate an LLM dream line from the device-supplied derived context + a recalled memory.

    Never 500s — returns {"dream": None} on any failure so the device falls back to templates.
    """
    _check_auth(authorization)
    ctx = dict(body or {})
    try:
        recalled = memory.recall(memory.load_episodes(config.MEMORY_PATH), random.choice)
        if recalled:
            ctx["memory"] = recalled
    except Exception:
        pass
    return {"dream": llm.generate_dream(ctx)}


@app.post("/remember")
def post_remember(body: dict = Body(default={}), authorization: str = Header(default="")) -> dict:
    """Append the device's day-context to the episodic memory log. Never 500s."""
    _check_auth(authorization)
    try:
        episode = memory.episode_from(
            body or {}, datetime.now(timezone.utc).isoformat(timespec="minutes")
        )
        memory.append_episode(config.MEMORY_PATH, episode, config.MEMORY_CAP)
        return {"ok": True}
    except Exception:
        return {"ok": False}


@app.get("/journal", response_class=HTMLResponse)
def get_journal(month: str = "", kind: str = "") -> HTMLResponse:
    """Read-only HTML archive of the pet's days. Open on the LAN (no auth). Never 500s."""
    try:
        episodes = memory.load_episodes(config.MEMORY_PATH)
    except Exception:
        episodes = []
    html_doc = journal_view.render_page(episodes, month or None, kind or None)
    return HTMLResponse(content=html_doc)
