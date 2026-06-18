from datetime import datetime, timezone

from app.github import summarize

NOW = datetime(2026, 6, 18, 15, 0, tzinfo=timezone.utc)


def _push(hours_ago, size):
    created = NOW.timestamp() - hours_ago * 3600
    iso = datetime.fromtimestamp(created, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {"type": "PushEvent", "created_at": iso, "payload": {"size": size}}


def _push_nosize(hours_ago):
    """A PushEvent shaped like GitHub's /users/{u}/events feed, where `size` is absent."""
    created = NOW.timestamp() - hours_ago * 3600
    iso = datetime.fromtimestamp(created, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {"type": "PushEvent", "created_at": iso, "payload": {}}


def test_idle_when_no_recent_pushes():
    out = summarize([_push(48, 3)], NOW)  # 48h ago -> outside the 24h window
    assert out["coding_rhythm"] == "idle"


def test_light_then_heavy_by_activity():
    light = summarize([_push(2, 2)], NOW)  # one push, size 2 -> light
    assert light["coding_rhythm"] == "light"
    heavy = summarize([_push(1, 6)], NOW)  # one push, size 6 (>= heavy) -> heavy
    assert heavy["coding_rhythm"] == "heavy"


def test_counts_pushes_when_size_absent():
    # Regression: GitHub often omits `size`; each push must still count as activity.
    light = summarize([_push_nosize(2)], NOW)
    assert light["coding_rhythm"] == "light"
    heavy = summarize([_push_nosize(h) for h in (1, 2, 3, 4, 5)], NOW)  # 5 pushes -> heavy
    assert heavy["coding_rhythm"] == "heavy"


def test_hours_since_push_from_newest():
    out = summarize([_push(5, 1), _push(2, 1)], NOW)
    assert 1.9 <= out["hours_since_push"] <= 2.1


def test_no_pushes_gives_none_hours():
    out = summarize([{"type": "WatchEvent", "created_at": "2026-06-18T14:00:00Z"}], NOW)
    assert out["coding_rhythm"] == "idle"
    assert out["hours_since_push"] is None
