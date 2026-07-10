# dashboard_reports.py
from pathlib import Path
from playwright.sync_api import sync_playwright

from config import LOGIN_URL, ADMIN_LOGIN_ID, ADMIN_PASSWORD, ARTIFACTS_DIR, PLAYWRIGHT_HEADLESS

LOGIN_ID_SELECTOR = "#loginid"
PASSWORD_SELECTOR = "#password"
LOGIN_BUTTON_SELECTOR = "#loginBtn"

ADMIN_CLIENTS_TAB_SELECTOR = '#adminTabs .tab[data-admin="clients"]'
ADMIN_CLIENT_SEARCH_SELECTOR = "#adminClientSearch"

PERFORMANCE_TAB_SELECTOR = '#userTabs .tab[data-tab="performance"]'
PERFORMANCE_PANEL_SELECTOR = "#tab-performance"
PERFORMANCE_EXPAND_SELECTOR = "#tab-performance .expand-all"
PERFORMANCE_TABLE_SELECTOR = "#perfContainer table"

PROFITBOOK_TAB_SELECTOR = '#userTabs .tab[data-tab="profit"]'
PROFITBOOK_PANEL_SELECTOR = "#tab-profit"
PROFITBOOK_EXPAND_SELECTOR = "#tab-profit .expand-all"
PROFITBOOK_TABLE_SELECTOR = "#profitContainer table"

def _login_as_admin(page):
    page.goto(LOGIN_URL, wait_until="domcontentloaded")
    page.locator(LOGIN_ID_SELECTOR).fill(ADMIN_LOGIN_ID)
    page.locator(PASSWORD_SELECTOR).fill(ADMIN_PASSWORD)
    page.locator(LOGIN_BUTTON_SELECTOR).click()
    page.locator(ADMIN_CLIENTS_TAB_SELECTOR).wait_for(state="visible")

def _open_client(page, client_login: str):
    page.locator(ADMIN_CLIENTS_TAB_SELECTOR).click()
    page.locator(ADMIN_CLIENT_SEARCH_SELECTOR).fill(client_login)
    row = page.locator(f'.admin-client-row[data-login="{client_login}"]')
    row.wait_for(state="visible")
    row.click()

def _export_panel_pdf(page, tab_selector: str, panel_selector: str, expand_selector: str, content_selector: str, output_path: str):
    page.locator(tab_selector).click()
    page.locator(panel_selector).wait_for(state="visible")

    if page.locator(expand_selector).count() > 0:
        page.locator(expand_selector).click()

    if page.locator(content_selector).count() > 0:
        page.locator(content_selector).first.wait_for(state="visible")
    else:
        page.wait_for_timeout(1500)

    page.emulate_media(media="screen")
    page.pdf(
        path=output_path,
        format="A4",
        landscape=True,
        print_background=True,
        margin={"top": "12mm", "right": "8mm", "bottom": "12mm", "left": "8mm"}
    )

def generate_client_reports(client_login: str) -> dict:
    client_dir = ARTIFACTS_DIR / client_login
    client_dir.mkdir(parents=True, exist_ok=True)

    perf_pdf = str(client_dir / f"{client_login}_performance.pdf")
    profit_pdf = str(client_dir / f"{client_login}_profitbook.pdf")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=PLAYWRIGHT_HEADLESS)
        page = browser.new_page()

        _login_as_admin(page)
        _open_client(page, client_login)

        _export_panel_pdf(
            page,
            PERFORMANCE_TAB_SELECTOR,
            PERFORMANCE_PANEL_SELECTOR,
            PERFORMANCE_EXPAND_SELECTOR,
            PERFORMANCE_TABLE_SELECTOR,
            perf_pdf
        )

        page.locator(ADMIN_CLIENTS_TAB_SELECTOR).count()  # harmless noop for clarity

        _export_panel_pdf(
            page,
            PROFITBOOK_TAB_SELECTOR,
            PROFITBOOK_PANEL_SELECTOR,
            PROFITBOOK_EXPAND_SELECTOR,
            PROFITBOOK_TABLE_SELECTOR,
            profit_pdf
        )

        browser.close()

    return {
        "performance_pdf": perf_pdf,
        "profitbook_pdf": profit_pdf
    }