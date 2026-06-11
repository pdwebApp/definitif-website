import os
from pathlib import Path

def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value

BASE_URL = "https://www.definitif.app"
LOGIN_URL = f"{BASE_URL}/dashboard"

ADMIN_LOGIN_ID = require_env("ADMIN_LOGIN_ID")
ADMIN_PASSWORD = require_env("ADMIN_PASSWORD")
GMAIL_SENDER = require_env("GMAIL_SENDER")
GMAIL_APP_PASSWORD = require_env("GMAIL_APP_PASSWORD")
PLAYWRIGHT_HEADLESS = os.getenv("PLAYWRIGHT_HEADLESS", "true").lower() == "true"

ARTIFACTS_DIR = Path("output/email_reports")
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

AUTH_STATE_FILE = Path("playwright/.auth/admin.json")
AUTH_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)