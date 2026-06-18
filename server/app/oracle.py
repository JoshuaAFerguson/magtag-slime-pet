"""Assemble the /oracle payload from weather + moon."""


def build(weather, moon, ts):
    """Return the compact oracle payload served to the device."""
    return {"weather": weather, "moon": moon, "ts": ts}
