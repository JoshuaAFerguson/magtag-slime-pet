"""Assemble the /oracle payload from weather + moon + presence."""


def build(weather, moon, presence, calendar=None, ts=0):
    """Return the compact oracle payload served to the device.

    The `calendar` block is included only when present (calendar is not None)."""
    payload = {"weather": weather, "moon": moon, "presence": presence, "ts": ts}
    if calendar is not None:
        payload["calendar"] = calendar
    return payload
