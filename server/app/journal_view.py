"""Pure rendering of the episodic log as a calm, read-only HTML journal archive.

No I/O: the route loads episodes and passes them in. Every episode-derived string is
HTML-escaped — the data originates from the device over the untrusted /remember boundary.
"""

import html

from . import memory

_DEFAULT_ENTRY = "a quiet, ordinary day"

# Notable-kind display order + label for the filter strip.
_KIND_LABELS = (
    ("storm", "storms"),
    ("heat", "heat"),
    ("rain", "rain"),
    ("full_moon", "full moons"),
    ("new_moon", "new moons"),
    ("flooded", "busy inboxes"),
    ("heavy", "full days"),
    ("quiet", "quiet days"),
)

# Small text marks for weather + moon (web fonts render these; no images to ship).
_WEATHER_MARK = {
    "storm_incoming": "⚡",
    "monsoon": "☂",
    "rain": "☂",
    "extreme_heat": "☀",
    "clear": "☀",
    "calm": "·",
}


def _month_of(ep):
    """The YYYY-MM prefix of an episode date, or None if it has no usable date."""
    date = ep.get("date") or ""
    return date[:7] if len(date) >= 7 else None


def available_months(episodes):
    """Distinct YYYY-MM months present, newest first."""
    seen = []
    for ep in episodes:
        m = _month_of(ep)
        if m and m not in seen:
            seen.append(m)
    return sorted(seen, reverse=True)


def present_kinds(episodes):
    """Distinct notable kinds present, in display order."""
    found = {memory.episode_kind(ep) for ep in episodes}
    return [k for k, _ in _KIND_LABELS if k in found]


def filter_episodes(episodes, month, kind):
    """Episodes matching the optional month (YYYY-MM prefix) and kind. Pure."""
    out = []
    for ep in episodes:
        if month and _month_of(ep) != month:
            continue
        if kind and memory.episode_kind(ep) != kind:
            continue
        out.append(ep)
    return out


def entry_text(ep):
    """The diary sentence: the posted journal line, else a kind phrase, else the default.

    "quiet" is not a notable kind for recall purposes — ordinary days fall through to the default.
    """
    line = ep.get("journal")
    if line:
        return line
    kind = memory.episode_kind(ep)
    if kind and kind != "quiet":
        phrase = memory._RECALL.get(kind)
        if phrase:
            return phrase
    return _DEFAULT_ENTRY


_STYLE = """
:root {
  --paper: #f4efe6; --ink: #2b2722; --muted: #8a7f70; --accent: #9a5b34;
  --card: #fbf8f2; --line: #e3dac9;
}
* { box-sizing: border-box; }
body {
  margin: 0; background: var(--paper); color: var(--ink);
  font-family: Georgia, 'Iowan Old Style', serif; line-height: 1.6;
  padding: clamp(1.5rem, 4vw, 4rem);
}
.wrap { max-width: 44rem; margin: 0 auto; }
header h1 {
  font-size: clamp(2rem, 1rem + 5vw, 3.5rem); margin: 0 0 .25rem; letter-spacing: -.01em;
}
header p { color: var(--muted); margin: 0 0 2rem; font-style: italic; }
nav.filters { display: flex; flex-wrap: wrap; gap: .5rem; margin-bottom: 2.5rem;
  padding-bottom: 1.25rem; border-bottom: 1px solid var(--line); }
nav.filters a {
  font-family: -apple-system, system-ui, sans-serif; font-size: .8rem;
  text-decoration: none; color: var(--muted); padding: .2rem .6rem; border: 1px solid var(--line);
  border-radius: 999px; transition: color .15s, border-color .15s, background .15s;
}
nav.filters a:hover, nav.filters a:focus { color: var(--accent); border-color: var(--accent); }
nav.filters a.on { color: var(--card); background: var(--accent); border-color: var(--accent); }
article.day {
  background: var(--card); border: 1px solid var(--line); border-radius: .5rem;
  padding: 1.25rem 1.5rem; margin-bottom: 1.1rem;
}
article.day .date {
  font-family: -apple-system, system-ui, sans-serif; font-size: .75rem; letter-spacing: .08em;
  text-transform: uppercase; color: var(--muted); margin-bottom: .35rem;
}
article.day .text { font-size: 1.15rem; margin: 0 0 .5rem; }
article.day .marks { color: var(--accent); font-size: .95rem; }
article.day .marks .tone { color: var(--muted); font-style: italic; margin-left: .4rem; }
.empty { color: var(--muted); font-style: italic; font-size: 1.1rem; padding: 2rem 0; }
"""


def _filter_nav(episodes, month, kind):
    """Build the month + kind filter strip as escaped <a> links."""
    links = ['<a href="/journal"%s>all</a>' % (' class="on"' if not (month or kind) else "")]
    for m in available_months(episodes):
        on = ' class="on"' if m == month else ""
        links.append('<a href="/journal?month=%s"%s>%s</a>' % (html.escape(m), on, html.escape(m)))
    label = dict(_KIND_LABELS)
    for k in present_kinds(episodes):
        on = ' class="on"' if k == kind else ""
        links.append(
            '<a href="/journal?kind=%s"%s>%s</a>' % (html.escape(k), on, html.escape(label[k]))
        )
    return '<nav class="filters">%s</nav>' % "".join(links)


def _entry_card(ep):
    """One escaped diary card for an episode."""
    date = html.escape((ep.get("date") or "")[:10] or "an untold day")
    text = html.escape(entry_text(ep))
    mark = _WEATHER_MARK.get(ep.get("weather"), "·")
    if ep.get("moon") == 4:
        mark += " ☽"
    tone = ep.get("tone")
    tone_html = '<span class="tone">%s</span>' % html.escape(tone) if tone else ""
    return (
        '<article class="day"><div class="date">%s</div>'
        '<p class="text">%s</p>'
        '<div class="marks">%s%s</div></article>' % (date, text, mark, tone_html)
    )


def render_page(episodes, month, kind):
    """Render the full archive HTML document (newest-first, filtered, escaped)."""
    nav = _filter_nav(episodes, month, kind)
    shown = list(reversed(filter_episodes(episodes, month, kind)))
    if not episodes:
        body = '<p class="empty">no entries yet — the pet has not written home.</p>'
    elif not shown:
        body = '<p class="empty">nothing matches that filter yet.</p>'
    else:
        body = "".join(_entry_card(ep) for ep in shown)
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        "<title>slime &mdash; journal</title><style>%s</style></head>"
        '<body><div class="wrap"><header><h1>journal</h1>'
        "<p>quiet days, remembered.</p></header>%s%s</div></body></html>" % (_STYLE, nav, body)
    )
