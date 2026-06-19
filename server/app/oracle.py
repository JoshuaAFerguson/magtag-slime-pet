"""Assemble the /oracle payload from weather + moon + presence."""


def build(weather, moon, presence, calendar=None, inbox=None, ts=0):
    """Return the compact oracle payload served to the device.

    The `calendar` and `inbox` blocks are included only when present (not None)."""
    payload = {"weather": weather, "moon": moon, "presence": presence, "ts": ts}
    if calendar is not None:
        payload["calendar"] = calendar
    if inbox is not None:
        payload["inbox"] = inbox
    return payload
