"""Server configuration from environment variables."""

import os

LAT = float(os.getenv("SLIME_LAT", "33.4484"))  # Phoenix
LON = float(os.getenv("SLIME_LON", "-112.0740"))
TZ = os.getenv("SLIME_TZ", "America/Phoenix")
ORACLE_TOKEN = os.getenv("ORACLE_TOKEN", "")  # empty -> no auth on the LAN
GITHUB_USER = os.getenv("GITHUB_USER", "")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
