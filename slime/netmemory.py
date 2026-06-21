"""Hardware adapter: post a day-memory to the home server. Device-only. Never raises.

Mirrors netdream/netoracle: scheme-aware ORACLE_HOST, optional bearer, fire-and-forget.
"""

import os


def post(context):
    """POST `context` to <ORACLE_HOST>/remember; return True on apparent success, else False."""
    try:
        import json as _json
        import ssl

        import adafruit_requests
        import socketpool
        import wifi

        host = os.getenv("ORACLE_HOST")
        if not host:
            return False
        base = host if host.startswith(("http://", "https://")) else "http://" + host
        pool = socketpool.SocketPool(wifi.radio)
        session = adafruit_requests.Session(pool, ssl.create_default_context())
        headers = {"Content-Type": "application/json"}
        token = os.getenv("ORACLE_TOKEN")
        if token:
            headers["Authorization"] = "Bearer " + token
        resp = session.post(
            base.rstrip("/") + "/remember",
            data=_json.dumps(context),
            headers=headers,
            timeout=10,
        )
        resp.close()
        return True
    except Exception:
        return False
