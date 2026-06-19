from app.inbox import _internaldate_epoch, summarize

NOW = 1781889000  # arbitrary UTC epoch


def test_inbox_load_buckets():
    assert summarize(0, None, NOW)["inbox_load"] == "clear"
    assert summarize(1, NOW, NOW)["inbox_load"] == "light"
    assert summarize(10, NOW, NOW)["inbox_load"] == "light"
    assert summarize(11, NOW, NOW)["inbox_load"] == "busy"
    assert summarize(30, NOW, NOW)["inbox_load"] == "busy"
    assert summarize(31, NOW, NOW)["inbox_load"] == "flooded"


def test_fresh_mail_window():
    assert summarize(3, NOW - 600, NOW)["fresh_mail"] is True
    assert summarize(3, NOW - 5400, NOW)["fresh_mail"] is False
    assert summarize(3, NOW - 3600, NOW)["fresh_mail"] is True
    assert summarize(3, NOW + 1, NOW)["fresh_mail"] is False


def test_fresh_false_when_no_unread_or_no_date():
    assert summarize(0, None, NOW)["fresh_mail"] is False
    assert summarize(5, None, NOW)["fresh_mail"] is False


def test_internaldate_epoch_parses_imap_response():
    resp = b'1 (INTERNALDATE "01-Jun-2026 10:00:00 +0000")'
    out = _internaldate_epoch([resp])
    assert isinstance(out, int)


def test_internaldate_epoch_none_on_garbage():
    assert _internaldate_epoch([None]) is None
    assert _internaldate_epoch([b"nonsense"]) is None
