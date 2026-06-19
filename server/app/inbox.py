"""IMAP inbox -> a privacy-safe inbox-presence signal. summarize() is pure.

Reads INBOX read-only and derives only buckets — never senders, subjects, or bodies.
"""

import imaplib
import time

_LIGHT_MAX = 10
_BUSY_MAX = 30
_FRESH_MIN = 60


def _internaldate_epoch(fetch_data: list | None) -> int | None:
    """Parse the newest message's INTERNALDATE (UTC epoch int), or None on any problem."""
    for part in fetch_data or ():
        raw = part[0] if isinstance(part, tuple) else part
        if not raw:
            continue
        if isinstance(raw, str):
            raw = raw.encode()
        try:
            t = imaplib.Internaldate2tuple(raw)
        except Exception:
            t = None
        if t:
            return int(time.mktime(t))
    return None


def fetch_counts(host: str, user: str, password: str) -> tuple[int, int | None]:
    """Read-only IMAP INBOX -> (unread_count, newest_unseen_epoch_or_None).

    Connects over SSL, counts UNSEEN, and reads only the newest unseen message's
    INTERNALDATE for freshness. Logs out in a finally.
    """
    m = imaplib.IMAP4_SSL(host)
    try:
        m.login(user, password)
        m.select("INBOX", readonly=True)
        _typ, data = m.search(None, "UNSEEN")
        ids = data[0].split() if data and data[0] else []
        unread = len(ids)
        newest_epoch = None
        if ids:
            _typ, fd = m.fetch(ids[-1], "(INTERNALDATE)")
            newest_epoch = _internaldate_epoch(fd)
        return unread, newest_epoch
    finally:
        try:
            m.logout()
        except Exception:
            pass


def summarize(unread: int, newest_unseen_epoch: int | None, now_epoch: int) -> dict[str, object]:
    """Pure: unread count + newest-unseen epoch + now epoch -> {inbox_load, fresh_mail}."""
    if unread <= 0:
        load = "clear"
    elif unread <= _LIGHT_MAX:
        load = "light"
    elif unread <= _BUSY_MAX:
        load = "busy"
    else:
        load = "flooded"
    fresh = (
        unread > 0
        and newest_unseen_epoch is not None
        and 0 <= now_epoch - newest_unseen_epoch <= _FRESH_MIN * 60
    )
    return {"inbox_load": load, "fresh_mail": bool(fresh)}
