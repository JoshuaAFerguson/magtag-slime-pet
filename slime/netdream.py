"""Hardware adapter: fetch an LLM dream line from the home server. Device-only. Never raises.

Assumes WiFi is already connected (nettime.sync connects it at boot). POSTs the derived
context to <ORACLE_HOST>/dream; returns the dream line or None on any failure/empty.
"""

import os


def fetch(context):
    """POST `context` to http://<ORACLE_HOST>/dream; return the dream line or None."""
    try:
        import json as _json
        import ssl

        import adafruit_requests
        import socketpool
        import wifi

        host = os.getenv("ORACLE_HOST")
        if not host:
            return None
        # Honor an explicit scheme in ORACLE_HOST so a TLS-fronted server (and any bearer
        # token) can ride https; a bare LAN host:port still defaults to http.
        base = host if host.startswith(("http://", "https://")) else "http://" + host
        pool = socketpool.SocketPool(wifi.radio)
        session = adafruit_requests.Session(pool, ssl.create_default_context())
        headers = {"Content-Type": "application/json"}
        token = os.getenv("ORACLE_TOKEN")
        if token:
            headers["Authorization"] = "Bearer " + token
        resp = session.post(
            base.rstrip("/") + "/dream",
            data=_json.dumps(context),
            headers=headers,
            timeout=25,
        )
        data = resp.json()
        resp.close()
        line = data.get("dream")
        return line if line else None
    except Exception:
        return None
