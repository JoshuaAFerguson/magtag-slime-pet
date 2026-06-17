"""Hardware adapter: WiFi + NTP -> epoch seconds (UTC). Device-only. Never raises into the loop."""

import os
import time


def sync():
    """Return current epoch seconds from NTP, or None if WiFi/NTP is unavailable."""
    try:
        import adafruit_ntp
        import socketpool
        import wifi

        ssid = os.getenv("WIFI_SSID")
        password = os.getenv("WIFI_PASSWORD")
        if not ssid:
            return None
        wifi.radio.connect(ssid, password)
        pool = socketpool.SocketPool(wifi.radio)
        ntp = adafruit_ntp.NTP(pool, tz_offset=0)
        return int(time.mktime(ntp.datetime))
    except Exception:
        return None


def tz_offset_hours():
    """Timezone offset from settings.toml (default -7, Phoenix)."""
    try:
        value = os.getenv("TZ_OFFSET")
        return float(value) if value is not None else -7.0
    except Exception:
        return -7.0
