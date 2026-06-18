"""FastAPI home oracle: GET /oracle (weather + moon), GET /health."""

import time
from datetime import datetime

import httpx
from fastapi import FastAPI, Header, HTTPException

from . import config, moon, oracle, weather

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
    return oracle.build(w, mooninfo, ts=int(time.time()))
