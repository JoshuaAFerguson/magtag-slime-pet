"""Episodic memory: a bounded JSONL log of notable days + recall.

episode_from/recall are pure; append_episode/load_episodes touch the filesystem. Only
derived buckets/tones are stored — never event content.
"""

import json
import os
import threading

# Serialize the read-modify-write in append_episode. The device posts once per journal day
# so contention is effectively nil, but FastAPI runs sync endpoints in a thread pool, so this
# guards against a corrupted/double-trimmed log if two /remember calls ever overlap.
_APPEND_LOCK = threading.Lock()

_RECALL = {
    "storm": "the day a desert storm rolled in",
    "heat": "an afternoon when the heat shimmered",
    "rain": "the day the rain finally came",
    "full_moon": "a night under the full moon",
    "new_moon": "a night with no moon at all",
    "flooded": "a day the messages would not stop",
    "quiet": "the long quiet before you returned",
    "heavy": "a day full of work and meetings",
}


def episode_from(context, now_iso):
    """Reduce a posted day-context to a compact episode (only derived fields). Pure."""
    return {
        "date": now_iso,
        "weather": context.get("weather", "calm"),
        "moon": context.get("moon"),
        "presence": context.get("rhythm", "idle"),
        "calendar": context.get("day_load"),
        "inbox": context.get("inbox"),
        "tone": (context.get("tones") or ["quiet"])[0],
    }


def _kind(ep):
    """Classify a single episode's most notable kind, or None."""
    w = ep.get("weather")
    if w in ("storm_incoming", "monsoon"):
        return "storm"
    if w == "extreme_heat":
        return "heat"
    if w == "rain":
        return "rain"
    if ep.get("moon") == 4:
        return "full_moon"
    if ep.get("moon") == 0:
        return "new_moon"
    if ep.get("inbox") == "flooded":
        return "flooded"
    if ep.get("presence") == "idle" and ep.get("tone") == "quiet":
        return "quiet"
    if ep.get("calendar") == "heavy" or ep.get("presence") == "heavy":
        return "heavy"
    return None


def recall(episodes, choice):
    """Pick a notable past episode and render a short recall phrase, or None. Pure.

    `choice(kinds)` selects one kind from the notable-kind list (duplicates weight toward
    common kinds); the phrase is looked up per kind.
    """
    kinds = [k for k in (_kind(ep) for ep in episodes) if k]
    if not kinds:
        return None
    return _RECALL[choice(kinds)]


def append_episode(path, episode, cap):
    """Append one episode as a JSON line; keep at most `cap` most-recent lines."""
    with _APPEND_LOCK:
        try:
            with open(path) as f:
                lines = [ln for ln in f.read().splitlines() if ln.strip()]
        except OSError:
            lines = []
        lines.append(json.dumps(episode))
        lines = lines[-cap:]
        directory = os.path.dirname(path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        with open(path, "w") as f:
            f.write("\n".join(lines) + "\n")


def load_episodes(path):
    """Read all episodes from the JSONL log; [] on a missing file, skipping corrupt lines."""
    out = []
    try:
        with open(path) as f:
            content = f.read()
    except OSError:
        return []
    for line in content.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except ValueError:
            continue
    return out
