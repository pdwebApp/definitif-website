import json
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright
from config import AUTH_STATE_FILE, PLAYWRIGHT_HEADLESS, LOGIN_URL
from send_client_reports import (
    run_client_report_job,
    open_client_direct,
)
from supabase_storage import fetch_json
from datetime import datetime, timezone

def log(msg):
    print(
        f"[{datetime.now(timezone.utc).isoformat()}] {msg}",
        file=sys.stderr,
        flush=True
    )

def load_clients_map():
    data = fetch_json("users_index.json")
    print(f"load_clients_map: top-level type={type(data).__name__}", file=sys.stderr, flush=True)
    if not data:
        print("load_clients_map: users_index.json missing or empty", file=sys.stderr, flush=True)
        return {}

    users = data.get("users", [])
    print(f"load_clients_map: user count={len(users)}", file=sys.stderr, flush=True)
    clients_map = {}

    for user in users:
        login = user.get("login")
        user_type = str(user.get("type", "")).lower()
        print(
            f"load_clients_map: raw user login={login!r}, type={user_type!r}, file={user.get('file')!r}",
            file=sys.stderr,
            flush=True,
        )

        if user_type in {"admin", "family"}:
            continue

        if not login:
            continue

        portfolio_file = user.get("file") or f"{login}.json"

        try:
            portfolio = fetch_json(portfolio_file) or {}
        except Exception:
            portfolio = {}

        clients_map[login] = {
            "login": login,
            "name": portfolio.get("name") or user.get("name") or login,
            "email_connect": (
                portfolio.get("email_connect")
                or portfolio.get("emailconnect")
                or user.get("email_connect")
                or user.get("emailconnect")
                or ""
            ),
        }
    print(f"load_clients_map: built keys={list(clients_map.keys())[:20]}", file=sys.stderr, flush=True)
    return clients_map


def main():
    try:
        payload = json.load(sys.stdin)
        print("batch: parsed payload", file=sys.stderr, flush=True)
    except Exception:
        print(json.dumps({
            "success": False,
            "message": "Invalid JSON payload"
        }))
        sys.exit(1)

    client_logins = payload.get("clientLogins", [])
    recipient_mode = payload.get("recipientMode", "default")
    manual_emails = payload.get("manualEmails", [])

    if not isinstance(client_logins, list) or not client_logins:
        print(json.dumps({
            "success": False,
            "message": "clientLogins is required"
        }))
        sys.exit(1)

    if recipient_mode not in {"default", "manual"}:
        print(json.dumps({
            "success": False,
            "message": "recipientMode must be 'default' or 'manual'"
        }))
        sys.exit(1)

    if recipient_mode == "manual":
        if not isinstance(manual_emails, list) or not manual_emails:
            print(json.dumps({
                "success": False,
                "message": "manualEmails is required for manual mode"
            }))
            sys.exit(1)

    if not Path(AUTH_STATE_FILE).exists():
        print(json.dumps({
            "success": False,
            "message": f"Missing auth state file: {AUTH_STATE_FILE}"
        }))
        sys.exit(1)

    clients_map = load_clients_map()
    print("batch: loaded clients map", file=sys.stderr, flush=True)

    results = []

    log("launching playwright")
    with sync_playwright() as p:
        log("launching browser")
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-setuid-sandbox"
            ]
        )

        log("browser launched")

        log(f"AUTH_STATE_FILE={AUTH_STATE_FILE}")

        auth_exists = Path(AUTH_STATE_FILE).exists()
        log(f"AUTH_STATE_EXISTS={auth_exists}")

        if auth_exists:
            log(f"AUTH_STATE_SIZE={Path(AUTH_STATE_FILE).stat().st_size}")

        log("creating browser context")

        context = browser.new_context(
            storage_state=str(AUTH_STATE_FILE),
            accept_downloads=True,
        )

        page = context.new_page()

        log("page created")

        page.set_default_timeout(240_000)

        REPORT_URL = f"{LOGIN_URL}?report=1"

        page.goto(
            REPORT_URL,
            wait_until="domcontentloaded",
            timeout=240000,
        )

        for login in client_logins:
            log(f"processing {login}")

            client = clients_map.get(login)

            if not client:
                results.append({
                    "login": login,
                    "success": False,
                    "message": "Client not found"
                })
                continue

            recipients = (
                [client.get("email_connect")] if recipient_mode == "default" else manual_emails
            )
            recipients = [str(x).strip() for x in recipients if str(x).strip()]

            try:
                result = run_client_report_job(
                    page=page,
                    client_login=client["login"],
                    client_name=client.get("name") or client["login"],
                    recipients=recipients,
                )
                result["success"] = True
                result["message"] = "Processed successfully"
                results.append(result)
            except Exception as e:
                results.append({
                    "login": login,
                    "clientName": client.get("name") or login,
                    "success": False,
                    "message": repr(e)
                })

        context.close()
        browser.close()

    emailed_count = sum(1 for r in results if r.get("emailSent"))
    log(f"Processed {len(results)} client(s), emailed {emailed_count}.")

    print(json.dumps({
        "success": True,
        "message": f"Processed {len(results)} client(s), emailed {emailed_count}.",
        "results": results
    }))


if __name__ == "__main__":
    main()