"""FastAPI home oracle: GET /oracle (weather + moon), GET /health."""

import time
from datetime import datetime, timezone

import httpx
from fastapi import FastAPI, Header, HTTPException

from . import calendar, config, github, moon, oracle, weather

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
    return oracle.build(w, mooninfo, _presence(), calendar=_calendar(), ts=int(time.time()))
