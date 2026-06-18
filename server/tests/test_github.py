from datetime import datetime, timezone

from app.github import summarize

NOW = datetime(2026, 6, 18, 15, 0, tzinfo=timezone.utc)


def _push(hours_ago, size):
    created = NOW.timestamp() - hours_ago * 3600
    iso = datetime.fromtimestamp(created, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {"type": "PushEvent", "created_at": iso, "payload": {"size": size}}


def test_idle_when_no_recent_pushes():
    out = summarize([_push(48, 3)], NOW)
    assert out["coding_rhythm"] == "idle"


def test_light_then_heavy_by_commit_count():
    light = summarize([_push(2, 2)], NOW)
    assert light["coding_rhythm"] == "light"
    heavy = summarize([_push(1, 6), _push(3, 6)], NOW)
    assert heavy["coding_rhythm"] == "heavy"


def test_hours_since_push_from_newest():
    out = summarize([_push(5, 1), _push(2, 1)], NOW)
    assert 1.9 <= out["hours_since_push"] <= 2.1


def test_no_pushes_gives_none_hours():
    out = summarize([{"type": "WatchEvent", "created_at": "2026-06-18T14:00:00Z"}], NOW)
    assert out["coding_rhythm"] == "idle"
    assert out["hours_since_push"] is None
