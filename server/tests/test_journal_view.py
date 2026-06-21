from app import journal_view


def _ep(date, **kw):
    base = {
        "date": date,
        "weather": "clear",
        "moon": 2,
        "presence": "idle",
        "calendar": None,
        "inbox": "clear",
        "tone": "quiet",
        "journal": None,
    }
    base.update(kw)
    return base


def test_available_months_distinct_desc():
    eps = [_ep("2026-05-02T08:00"), _ep("2026-06-01T08:00"), _ep("2026-06-20T08:00")]
    assert journal_view.available_months(eps) == ["2026-06", "2026-05"]


def test_present_kinds_distinct():
    eps = [
        _ep("2026-06-01", weather="storm_incoming"),
        _ep("2026-06-02", moon=4),
        _ep("2026-06-03"),
    ]
    kinds = journal_view.present_kinds(eps)
    assert "storm" in kinds and "full_moon" in kinds


def test_filter_episodes_by_month_and_kind():
    eps = [
        _ep("2026-05-30", weather="storm_incoming"),
        _ep("2026-06-10", weather="storm_incoming"),
        _ep("2026-06-11", moon=4),
    ]
    assert [e["date"] for e in journal_view.filter_episodes(eps, "2026-06", None)] == [
        "2026-06-10",
        "2026-06-11",
    ]
    assert [e["date"] for e in journal_view.filter_episodes(eps, None, "storm")] == [
        "2026-05-30",
        "2026-06-10",
    ]
    assert journal_view.filter_episodes(eps, "2026-06", "storm")[0]["date"] == "2026-06-10"
    assert journal_view.filter_episodes(eps, "1999-01", None) == []


def test_entry_text_prefers_journal_then_kind_then_default():
    assert journal_view.entry_text(_ep("2026-06-01", journal="we napped in the sun")) == (
        "we napped in the sun"
    )
    assert journal_view.entry_text(_ep("2026-06-01", weather="storm_incoming")) == (
        "the day a desert storm rolled in"
    )
    assert journal_view.entry_text(_ep("2026-06-01")) == "a quiet, ordinary day"


def test_render_page_escapes_and_orders_newest_first():
    eps = [
        _ep("2026-06-01T08:00", journal="first day"),
        _ep("2026-06-20T08:00", journal="<script>alert(1)</script>"),
    ]
    html = journal_view.render_page(eps, None, None)
    assert "<!doctype html>" in html.lower()
    assert "&lt;script&gt;" in html  # escaped
    assert "<script>alert(1)</script>" not in html  # raw injection absent
    # newest-first: the 06-20 entry appears before the 06-01 entry
    assert html.index("2026-06-20") < html.index("2026-06-01")


def test_render_page_empty_state():
    html = journal_view.render_page([], None, None)
    assert "no entries yet" in html.lower()


def test_render_page_filtered_empty_note():
    html = journal_view.render_page([_ep("2026-06-01")], "1999-01", None)
    assert "nothing matches" in html.lower()
