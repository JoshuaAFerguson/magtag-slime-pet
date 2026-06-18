"""Hardware adapter: fetch /oracle over WiFi. Device-only. Never raises into the loop.

Assumes WiFi is already connected (nettime.sync connects it at boot). ORACLE_HOST is the
Pi's mDNS name or IP:port from settings.toml, e.g. "slime-oracle.local:8080" or "192.168.0.50:8080".
"""

import os


def fetch():
    """GET http://<ORACLE_HOST>/oracle. Returns the parsed dict, or None on any failure."""
    try:
        import ssl

        import adafruit_requests
        import socketpool
        import wifi

        host = os.getenv("ORACLE_HOST")
        if not host:
            return None
        pool = socketpool.SocketPool(wifi.radio)
        session = adafruit_requests.Session(pool, ssl.create_default_context())
        headers = {}
        token = os.getenv("ORACLE_TOKEN")
        if token:
            headers["Authorization"] = "Bearer " + token
        resp = session.get("http://" + host + "/oracle", headers=headers, timeout=10)
        data = resp.json()
        resp.close()
        return data
    except Exception:
        return None
