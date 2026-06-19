"""FastAPI endpoint tests: /health, /oracle with auth."""

from fastapi.testclient import TestClient

import app.main as main_mod

SAMPLE = {
    "current": {
        "temperature_2m": 43,
        "relative_humidity_2m": 10,
        "precipitation": 0,
        "weather_code": 0,
        "time": "2026-06-18T15:00",
    },
    "daily": {
        "precipitation_probability_max": [0],
        "sunset": ["2026-06-18T19:42"],
    },
}


def _client(monkeypatch, fetch=None):
    if fetch is None:

        def fetch(_client):
            return SAMPLE

    monkeypatch.setattr(main_mod.weather, "fetch_raw", fetch)
    return TestClient(main_mod.app)


def test_health(monkeypatch):
    assert _client(monkeypatch).get("/health").json() == {"ok": True}


def test_oracle_returns_weather_and_moon(monkeypatch):
    r = _client(monkeypatch).get("/oracle")
    assert r.status_code == 200
    body = r.json()
    assert "extreme_heat" in body["weather"]["tags"]
    assert 0 <= body["moon"]["phase"] <= 7
    assert "ts" in body


def test_oracle_degrades_to_moon_only_on_weather_failure(monkeypatch):
    def boom(_client):
        raise RuntimeError("open-meteo down")

    body = _client(monkeypatch, fetch=boom).get("/oracle").json()
    assert body["weather"]["tags"] == []
    assert 0 <= body["moon"]["phase"] <= 7


def test_oracle_requires_token_when_configured(monkeypatch):
    monkeypatch.setattr(main_mod.config, "ORACLE_TOKEN", "sekret")
    c = _client(monkeypatch)
    assert c.get("/oracle").status_code == 401
    assert c.get("/oracle", headers={"Authorization": "Bearer sekret"}).status_code == 200


def test_oracle_includes_presence_when_github_configured(monkeypatch):
    monkeypatch.setattr(main_mod.config, "GITHUB_USER", "octocat")
    monkeypatch.setattr(
        main_mod.github,
        "fetch_events",
        lambda client: [
            {"type": "PushEvent", "created_at": "2026-06-18T14:30:00Z", "payload": {"size": 12}}
        ],
    )
    body = _client(monkeypatch).get("/oracle").json()
    assert body["presence"]["coding_rhythm"] == "heavy"


def test_oracle_presence_idle_without_token(monkeypatch):
    body = _client(monkeypatch).get("/oracle").json()
    assert body["presence"]["coding_rhythm"] == "idle"


def test_oracle_includes_calendar_when_configured(monkeypatch):
    monkeypatch.setattr(main_mod.config, "CALENDAR_ICS_URL", "https://example/ics")
    monkeypatch.setattr(main_mod.calendar, "fetch_ics", lambda client, url: b"ICS")
    monkeypatch.setattr(main_mod.calendar, "expand_today", lambda body, now, tz: [])
    body = _client(monkeypatch).get("/oracle").json()
    assert "calendar" in body
    assert body["calendar"]["free_rest_of_day"] is True


def test_oracle_omits_calendar_without_url(monkeypatch):
    body = _client(monkeypatch).get("/oracle").json()
    assert "calendar" not in body
