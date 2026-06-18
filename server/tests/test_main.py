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
