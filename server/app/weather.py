"""Open-Meteo fetch + normalization to desert 'feeling' tags."""

from datetime import datetime

import httpx

from .config import LAT, LON, TZ

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

_EXTREME_HEAT_C = 40.0
_COLD_C = 5.0
_HIGH_PRECIP_PROB = 70
_STORM_PRECIP_PROB = 60
_MONSOON_HUMIDITY = 50
_SUNSET_WINDOW_MIN = 30


def fetch_raw(client: httpx.Client) -> dict:
    """Fetch current + daily weather for the configured location.

    `client` is an httpx.Client. Raises httpx.HTTPStatusError on a non-2xx response.
    """
    params = {
        "latitude": LAT,
        "longitude": LON,
        "timezone": TZ,
        "current": "temperature_2m,relative_humidity_2m,precipitation,weather_code",
        "daily": "precipitation_probability_max,sunset",
        "forecast_days": 1,
    }
    resp = client.get(OPEN_METEO_URL, params=params)
    resp.raise_for_status()
    return resp.json()


def _minutes(iso: str) -> int:
    """Minutes-since-midnight from an ISO 'YYYY-MM-DDTHH:MM' string."""
    t = datetime.fromisoformat(iso)
    return t.hour * 60 + t.minute


def normalize(data: dict, now_iso: str) -> dict:
    """Map an Open-Meteo payload to {tags, temp_c, code, sunset_soon}. Pure."""
    cur = data.get("current", {})
    daily = data.get("daily", {})
    temp = cur.get("temperature_2m")
    humidity = cur.get("relative_humidity_2m", 0)
    precip = cur.get("precipitation", 0) or 0
    prob_list = daily.get("precipitation_probability_max") or [0]
    prob = prob_list[0] or 0
    month = datetime.fromisoformat(now_iso).month

    tags = []
    if temp is not None and temp >= _EXTREME_HEAT_C:
        tags.append("extreme_heat")
    if temp is not None and temp <= _COLD_C:
        tags.append("cold")
    if precip > 0:
        tags.append("rain")
    if prob >= _STORM_PRECIP_PROB and "rain" not in tags:
        tags.append("storm_incoming")
    if 6 <= month <= 9 and humidity >= _MONSOON_HUMIDITY and prob >= _STORM_PRECIP_PROB:
        tags.append("monsoon")
    if not tags:
        tags.append("clear")

    sunset_soon = False
    sunset_list = daily.get("sunset") or []
    if sunset_list:
        delta = _minutes(sunset_list[0]) - _minutes(now_iso)
        sunset_soon = 0 <= delta <= _SUNSET_WINDOW_MIN

    return {
        "tags": tags,
        "temp_c": temp,
        "code": cur.get("weather_code", 0),
        "sunset_soon": sunset_soon,
    }
