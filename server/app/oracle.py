"""Assemble the /oracle payload from weather + moon + presence."""


def build(weather, moon, presence, ts):
    """Return the compact oracle payload served to the device."""
    return {"weather": weather, "moon": moon, "presence": presence, "ts": ts}
