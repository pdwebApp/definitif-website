from pathlib import Path
from playwright.sync_api import sync_playwright
from config import (
    LOGIN_URL,
    ADMIN_LOGIN_ID,
    ADMIN_PASSWORD,
    PLAYWRIGHT_HEADLESS,
    AUTH_STATE_FILE,
)

AUTH_STATE_FILE = Path(AUTH_STATE_FILE)
AUTH_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=PLAYWRIGHT_HEADLESS)
        context = browser.new_context()
        page = context.new_page()
        page.set_default_timeout(240_000)

        page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=240_000)
        page.get_by_placeholder("Login-Id").fill(ADMIN_LOGIN_ID)
        page.locator("#password").fill(ADMIN_PASSWORD)
        page.locator("#loginBtn").click()

        page.locator('#adminTabs .tab[data-admin="clients"]').wait_for(
            state="visible",
            timeout=240_000
        )

        context.storage_state(path=str(AUTH_STATE_FILE))
        print(f"Saved auth state to: {AUTH_STATE_FILE}")

        context.close()
        browser.close()


if __name__ == "__main__":
    main()