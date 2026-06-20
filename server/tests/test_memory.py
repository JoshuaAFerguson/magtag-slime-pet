from app import memory


def test_episode_from_reduces_context():
    ctx = {
        "weather": "rain",
        "moon": 4,
        "rhythm": "heavy",
        "day_load": "busy",
        "inbox": "flooded",
        "tones": ["busy", "mail"],
        "fam": 3,
    }
    ep = memory.episode_from(ctx, "2026-06-20T10:00")
    assert ep == {
        "date": "2026-06-20T10:00",
        "weather": "rain",
        "moon": 4,
        "presence": "heavy",
        "calendar": "busy",
        "inbox": "flooded",
        "tone": "busy",
    }


def test_recall_renders_notable_phrase():
    eps = [{"weather": "storm_incoming", "moon": 2, "inbox": "clear"}]
    assert memory.recall(eps, lambda kinds: kinds[0]) == "the day a desert storm rolled in"
    eps2 = [{"weather": "clear", "moon": 4, "inbox": "clear"}]
    assert memory.recall(eps2, lambda kinds: kinds[0]) == "a night under the full moon"


def test_recall_none_when_nothing_notable():
    eps = [{"weather": "clear", "moon": 2, "inbox": "clear", "presence": "light", "tone": "busy"}]
    assert memory.recall(eps, lambda kinds: kinds[0]) is None
    assert memory.recall([], lambda kinds: kinds[0]) is None


def test_append_and_load_roundtrip(tmp_path):
    p = str(tmp_path / "mem.jsonl")
    memory.append_episode(p, {"date": "d1", "weather": "rain"}, cap=10)
    memory.append_episode(p, {"date": "d2", "weather": "clear"}, cap=10)
    eps = memory.load_episodes(p)
    assert len(eps) == 2 and eps[0]["weather"] == "rain" and eps[1]["date"] == "d2"


def test_append_caps_to_most_recent(tmp_path):
    p = str(tmp_path / "mem.jsonl")
    for i in range(5):
        memory.append_episode(p, {"i": i}, cap=3)
    eps = memory.load_episodes(p)
    assert [e["i"] for e in eps] == [2, 3, 4]


def test_load_missing_or_corrupt(tmp_path):
    assert memory.load_episodes(str(tmp_path / "nope.jsonl")) == []
    p = tmp_path / "bad.jsonl"
    p.write_text('{"ok": 1}\nNOT JSON\n{"ok": 2}\n')
    eps = memory.load_episodes(str(p))
    assert [e["ok"] for e in eps] == [1, 2]
