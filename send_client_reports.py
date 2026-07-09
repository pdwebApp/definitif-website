import sys
import base64
import mimetypes
import smtplib
from email.message import EmailMessage
from pathlib import Path
import time

from playwright.sync_api import Page, sync_playwright

from config import (
    LOGIN_URL,
    GMAIL_SENDER,
    GMAIL_APP_PASSWORD,
    PLAYWRIGHT_HEADLESS,
    ARTIFACTS_DIR,
    AUTH_STATE_FILE,
)

TEST_CLIENT_LOGIN = "investments.das@gmail.com"
TEST_CLIENT_NAME = "Sabita Das"
TEST_CLIENT_EMAIL = "das.prashanta1@gmail.com"
SEND_EMAIL = True

import datetime

def format_date_with_suffix(date_obj):
    day = date_obj.day
    # Determine suffix
    if 11 <= day <= 13:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")
    
    # Build string manually
    return f"{day}{suffix} {date_obj.strftime('%B %Y')}"

today = datetime.date.today()
today_formatted = format_date_with_suffix(today)

def reset_dashboard(page: Page):
    page.reload(wait_until="load", timeout=30000)
    page.goto(LOGIN_URL, wait_until="load", timeout=30000)
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(1000)

def open_client_direct(page: Page, login: str):
    page.on("console", lambda msg: log(f"[BROWSER] {msg.type}: {msg.text}"))
    result = page.evaluate(
        """async (login) => {
            try {
                await openClientDirect(login);
                return {
                    success: true,
                    client: document.getElementById("clientNameHeader")?.textContent,
                    perfRows: document.querySelectorAll("#perfContainer tbody tr").length,
                    profitRows: document.querySelectorAll("#profitContainer tbody tr").length
                };
            } catch(e) {
                return {
                    success:false,
                    error:e.message,
                    stack:e.stack
                };
            }
        }""",
        login
    )

    log(result)

    if not result["success"]:
        raise RuntimeError(result["error"])
    page.on("pageerror", lambda exc: log(f"[PAGE ERROR] {exc}"))
    page.wait_for_function(
        "() => window.clientRenderComplete === true",
        timeout=240000,
    )

    state = page.evaluate("""
    () => ({
        ready: window.clientRenderComplete,
        overview: document.querySelector("#tab-overview")?.classList.contains("active"),
        perfRows: document.querySelectorAll("#perfContainer tbody tr").length,
        profitRows: document.querySelectorAll("#profitContainer tbody tr").length,
        perfTable: !!document.querySelector("#perfContainer table"),
        profitTable: !!document.querySelector("#profitContainer table"),
        activeTab: document.querySelector("#userTabs .tab.active")?.dataset.tab,
        client: document.getElementById("clientNameHeader")?.textContent
    })
    """)

    log(state)

def capture_pdf_via_js_function(page: Page, function_name: str, output_path: str):
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    pdf_base64 = page.evaluate(
        """async (fnName) => {
            const wait = (ms) => new Promise(resolve => setTimeout(resolve, ms));

            let capturedBase64 = null;

            const originalSaveAs = window.saveAs;
            const originalCreateObjectURL = URL.createObjectURL;

            async function blobToBase64(blob) {
                const buffer = await blob.arrayBuffer();
                const bytes = new Uint8Array(buffer);
                const chunkSize = 0x8000;
                let binary = '';

                for (let i = 0; i < bytes.length; i += chunkSize) {
                    binary += String.fromCharCode(...bytes.subarray(i, i + chunkSize));
                }

                return btoa(binary);
            }

            window.saveAs = async function(blob, filename, options) {
                if (blob instanceof Blob && blob.type === 'application/pdf') {
                    capturedBase64 = await blobToBase64(blob);
                    return;
                }
                if (typeof originalSaveAs === 'function') {
                    return originalSaveAs(blob, filename, options);
                }
            };

            URL.createObjectURL = function(obj) {
                if (obj instanceof Blob && obj.type === 'application/pdf') {
                    blobToBase64(obj).then(result => {
                        capturedBase64 = result;
                    });
                }
                return originalCreateObjectURL.call(URL, obj);
            };

            try {
                const fn = window[fnName];
                if (typeof fn !== "function") {
                    throw new Error(`${fnName} is not available on window`);
                }

                console.log("Calling", fnName);
                console.log(typeof fn);

                await fn();

                console.log("Returned from", fnName);

                for (let i = 0; i < 75; i++) {
                    if (capturedBase64) {
                        return capturedBase64;
                    }
                    await wait(200);
                }

                throw new Error(`PDF was not captured from ${fnName}`);
            } finally {
                window.saveAs = originalSaveAs;
                URL.createObjectURL = originalCreateObjectURL;
            }
        }""",
        function_name,
    )

    output.write_bytes(base64.b64decode(pdf_base64))
    return str(output)

def expand_all_if_present(page: Page, panel_selector: str):
    expand_button = page.locator(f"{panel_selector} .expand-all").first

    try:
        expand_button.wait_for(state="attached", timeout=5000)
    except Exception:
        print(f"expand_all_if_present: no expand-all button for {panel_selector}", file=sys.stderr, flush=True)
        return False

    try:
        expand_button.scroll_into_view_if_needed()
        expand_button.click(timeout=5000)
    except Exception:
        try:
            expand_button.evaluate("(el) => el.click()")
        except Exception as e:
            print(f"expand_all_if_present failed for {panel_selector}: {repr(e)}", file=sys.stderr, flush=True)
            return False

    try:
        page.wait_for_function(
            """
            (panelSelector) => {
                const panel = document.querySelector(panelSelector);
                if (!panel) return false;
                return panel.querySelectorAll('tbody tr').length > 0;
            }
            """,
            arg=panel_selector,
            timeout=10000,
        )
    except Exception:
        pass

    return True
    
def generate_client_reports(page: Page, client_login: str, client_name: str, output_dir: str):
    import time
    log(">>>>>>>> ENTER generate_client_reports()")
    log("=" * 80)
    log("GENERATE REPORTS STARTED")
    log(client_name)

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    safe_name = "".join(c if c.isalnum() else "_" for c in client_name).strip("_")

    performance_pdf = str(out_dir / f"Performance_{safe_name}.pdf")
    profitbook_pdf = str(out_dir / f"Profitbook_{safe_name}.pdf")

    generated_performance_pdf = None
    generated_profitbook_pdf = None

    # ---------------------------------------------------------
    # OPEN CLIENT ONLY ONCE
    # ---------------------------------------------------------
    try:
        t = time.time()
        log("About to call open_client_direct()")
        open_client_direct(
            page,
            client_login,
        )

        log("Returned from open_client_direct()")
        log("Waiting for perf rows")
        page.wait_for_function(
            """
            () => {
                const t = document.querySelector("#perfContainer table tbody");
                return t && t.children.length > 0;
            }
            """,
            timeout=30000,
        )
        log("Perf rows found")
        log("CLIENT LOADED")

        state =  page.evaluate("""
            () => ({
                perfRows: document.querySelectorAll("#perfContainer tbody tr").length,
                profitRows: document.querySelectorAll("#profitContainer tbody tr").length,
            })
            """)
        log(state)

        log(f"TIMING: open_client_direct took {time.time()-t:.2f}s")

    except Exception as e:
        log(f"Failed opening client {client_name}: {repr(e)}")
        try:
            state = page.evaluate("""
            () => ({
                url: location.href,
                renderComplete: window.clientRenderComplete,
                activeTab: document.querySelector("#userTabs .tab.active")?.dataset.tab,
                perfRows: document.querySelectorAll("#perfContainer tbody tr").length,
                profitRows: document.querySelectorAll("#profitContainer tbody tr").length,
                client: document.getElementById("clientNameHeader")?.textContent
            })
            """)
            log(f"PAGE STATE: {state}")
        except Exception as ex:
            log(f"Unable to inspect page: {repr(ex)}")
        raise
        
    # ---------------------------------------------------------
    # PERFORMANCE PDF
    # ---------------------------------------------------------
    try:
        performance_tab = page.locator(
            '#userTabs .tab[data-tab="performance"]'
        )

        performance_tab.wait_for(
            state="visible",
            timeout=240_000,
        )

        performance_tab.click()

        state = page.evaluate("""
        () => ({
            activeTab: document.querySelector("#userTabs .tab.active")?.dataset.tab,
            performanceDisplay: getComputedStyle(document.querySelector("#tab-performance")).display,
            performanceClass: document.querySelector("#tab-performance").className,
            rows: document.querySelectorAll("#perfContainer tbody tr").length,
            downloadFn: typeof window.downloadPrefPDF
        })
        """)

        log("PERFORMANCE STATE")
        log(state)

        performance_panel = page.locator("#tab-performance")

        performance_panel.wait_for(
            state="visible",
            timeout=240_000,
        )

        page.wait_for_timeout(1500)

        expanders = page.evaluate("""
        () => document.querySelectorAll(
        '#tab-performance button, #tab-performance .expand, #tab-performance .toggle'
        ).length
        """)

        log(f"Expand buttons: {expanders}")

        state = page.evaluate("""
        () => ({
            activeTab: document.querySelector("#userTabs .tab.active")?.dataset.tab,
            toggles: document.querySelectorAll("#tab-performance .ui-toggle").length,
            rows: document.querySelectorAll("#perfContainer tbody tr").length
        })
        """)

        log(state)

        expand_all_if_present(page, "#tab-performance")

        performance_available = page.evaluate(
            """() => {
                const container = document.querySelector('#perfContainer');
                if (!container) return false;

                const table = container.querySelector('table');
                if (!table) return false;

                return table.querySelectorAll('tbody tr').length > 0;
            }"""
        )

        log(f"performance_available={performance_available}")

        if performance_available:
            try:
                t = time.time()

                page.wait_for_timeout(1500)

                log("Calling downloadPrefPDF()")

                capture_pdf_via_js_function(
                    page,
                    "downloadPrefPDF",
                    performance_pdf,
                )

                log("Returned from downloadPrefPDF()")

                log(f"TIMING: performance PDF took {time.time()-t:.2f}s")

                generated_performance_pdf = performance_pdf

            except Exception as e:
                log(f"Performance PDF skipped for {client_name}: {repr(e)}")
        else:
            print(
                f"Performance PDF skipped for {client_name}: no exportable table found.",
                file=sys.stderr,
                flush=True,
            )

    except Exception as e:
        print(
            f"Performance PDF skipped for {client_name}: {repr(e)}",
            file=sys.stderr,
            flush=True,
        )

    # ---------------------------------------------------------
    # PROFITBOOK PDF
    # REUSE SAME CLIENT DASHBOARD
    # ---------------------------------------------------------
    try:
        print(
            "Reusing already-open client dashboard for Profitbook",
            file=sys.stderr,
            flush=True,
        )

        profit_tab = page.locator(
            '#userTabs .tab[data-tab="profit"]'
        )

        profit_tab.wait_for(
            state="visible",
            timeout=240_000,
        )

        profit_tab.click()

        profit_panel = page.locator("#tab-profit")

        profit_panel.wait_for(
            state="visible",
            timeout=240_000,
        )

        page.wait_for_timeout(1500)

        expand_all_if_present(page, "#tab-profit")

        page.wait_for_timeout(1500)

        profitbook_available = page.evaluate(
            """() => {
                const container = document.querySelector('#profitContainer');
                if (!container) return false;

                const table = container.querySelector('table');
                if (!table) return false;

                return table.querySelectorAll('tbody tr').length > 0;
            }"""
        )

        log(f"profitbook_available={profitbook_available}")

        if profitbook_available:
            try:
                t = time.time()

                capture_pdf_via_js_function(
                    page,
                    "downloadProfitPDF",
                    profitbook_pdf,
                )

                log(f"TIMING: profitbook PDF took {time.time()-t:.2f}s")

                generated_profitbook_pdf = profitbook_pdf

            except Exception as e:
                print(
                    f"Profitbook PDF skipped for {client_name}: {repr(e)}",
                    file=sys.stderr,
                    flush=True,
                )

        else:
            print(
                f"Profitbook PDF skipped for {client_name}: no exportable table found.",
                file=sys.stderr,
                flush=True,
            )

    except Exception as e:
        print(
            f"Profitbook PDF skipped for {client_name}: {repr(e)}",
            file=sys.stderr,
            flush=True,
        )

    return {
        "performance_pdf": generated_performance_pdf,
        "profitbook_pdf": generated_profitbook_pdf,
    }


def build_email_html(client_name: str, today_format: str):
    return f"""
    <html>
      <body style="font-family: Arial, sans-serif; color: #222;">
        <p>Dear {client_name},</p>
        <p>Please find attached the Statements as on {today_format}. Parameters in the report are briefly explained below.<br><br>
            1. Return: depicts the absolute return on the current holdings<br>
            2. XIRR (Holdings): depicts the annual return generated by the current portfolio<br>
            3. XIRR (SI): depicts the annual return generated since inception<br>
            4. For Summary, Asset Class and Strategy breakup, visit www.definitif.app/dashboard<br>
        </p>
        
        <p>
        Note:<br>
        - Valuations might get delayed by 1 business day in some occations.<br>
        - Data is updated on every Tuesday and at the end of every month.
        </p>
        <p>Regards,</p>

        <!-- Signature block -->
        <table role="presentation" cellpadding="0" cellspacing="0" border="0" 
               style="font-family: Arial, Helvetica, sans-serif; font-size: 13px; color: #222; line-height: 1.4; width:auto;">
          <tr>
            <td valign="middle" style="padding-right:10px; border-right:1px solid #e5e5e5; text-align:left; white-space:nowrap;">
              <div style="font-weight:700; font-size:16px; color:#111; margin-bottom:2px;">
                Prashanta Das
              </div>
              <div style="font-size:11px; color:#777; margin-bottom:6px;">
                Investment Manager
              </div>
              <img src="cid:definitiflogo" alt="définitif logo" width="100"
                   style="display:block; border:0; margin-left:0px; outline:0; text-decoration:none;">
            </td>
            <td valign="middle" style="padding-left:10px; text-align:left; white-space:nowrap;">
              <img src="cid:definitifbrand" alt="définitif investments logo" width="80"
                    style="display:block; border:0; outline:0; text-decoration:none;">
              <div style="font-size:8px; color:#777; margin-top:0px; margin-left:4px;">
                ... by définitif investments
              </div>
              <div style="font-size:9px; color:#777; margin-top:4px; margin-left:2px;">
                www.definitif.app | definitif.investments@gmail.com
              </div>
            </td>
          </tr>
        </table>
      </body>
    </html>
    """


from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from email.mime.base import MIMEBase
from email import encoders

def send_email_with_attachments(
    recipient_email,
    subject: str,
    html_body: str,
    attachment_paths: list[str],
):
    if isinstance(recipient_email, list):
        recipients = [str(x).strip() for x in recipient_email if str(x).strip()]
    else:
        recipients = [str(recipient_email).strip()] if str(recipient_email).strip() else []

    if not recipients:
        raise ValueError("At least one recipient email is required")

    valid_attachments = []
    for file_path in attachment_paths:
        if not file_path:
            continue
        path = Path(file_path)
        if path.exists() and path.is_file():
            valid_attachments.append(path)

    # Root message: multipart/related
    msg = MIMEMultipart("related")
    msg["Subject"] = subject
    msg["From"] = GMAIL_SENDER
    msg["To"] = ", ".join(recipients)

    # Alternative part for HTML body
    alt_part = MIMEMultipart("alternative")
    alt_part.attach(MIMEText(html_body, "html"))
    msg.attach(alt_part)

    # Inline logos
    logo_path = Path("static/email/sign_brand_logo.png")
    brand_path = Path("static/email/sign_echo_logo.png")

    for cid, path in [("definitiflogo", logo_path), ("definitifbrand", brand_path)]:
        if path.exists():
            with open(path, "rb") as f:
                img = MIMEImage(f.read(), _subtype="png")
                img.add_header("Content-ID", f"<{cid}>")
                img.add_header("Content-Disposition", "inline", filename=path.name)
                msg.attach(img)

    # Attach PDFs
    for path in valid_attachments:
        with open(path, "rb") as f:
            payload = MIMEBase("application", "octet-stream", Name=path.name)
            payload.set_payload(f.read())
            encoders.encode_base64(payload)
            payload.add_header("Content-Disposition", "attachment", filename=path.name)
            msg.attach(payload)

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(GMAIL_SENDER, GMAIL_APP_PASSWORD)
        server.sendmail(GMAIL_SENDER, recipients, msg.as_string())

import json

def log(msg):
    if isinstance(msg, (dict, list)):
        msg = json.dumps(msg, indent=2, default=str)

    print(
        f"[{datetime.datetime.now(datetime.timezone.utc).isoformat()}] {msg}",
        file=sys.stderr,
        flush=True,
    )

def run_client_report_job(
    page: Page,
    client_login: str,
    client_name: str,
    recipients: list[str],
):
    log(f"START client={client_login}")
    log(f"Generating reports for {client_name}")

    reports = None
    try:
        reports = generate_client_reports(
            page=page,
            client_login=client_login,
            client_name=client_name,
            output_dir=str(Path(ARTIFACTS_DIR) / "email_reports" / client_login),
        )
        log(reports)

        log(
            f"Reports generated. "
            f"performance={reports['performance_pdf']} "
            f"profitbook={reports['profitbook_pdf']}"
        )

        attachments = [
            p for p in [reports["performance_pdf"], reports["profitbook_pdf"]] if p
        ]

        log(f"Attachments found: {len(attachments)}")

        email_sent = False

        if recipients:
            log(f"Recipients: {recipients}")
        else:
            log("No recipients")

        if recipients and attachments:
            log("Starting email send")
            send_email_with_attachments(
                recipient_email=recipients,
                subject=f"Portfolio Statements as on {today_formatted} - {client_name}",
                html_body=build_email_html(client_name, today_formatted),
                attachment_paths=attachments,
            )
            log("Email send completed")
            email_sent = True
        else:
            log("Skipping email send")

        log(f"END client={client_login}")

        return {
            "login": client_login,
            "clientName": client_name,
            "recipients": recipients,
            "performancePdf": bool(reports["performance_pdf"]),
            "profitbookPdf": bool(reports["profitbook_pdf"]),
            "emailSent": email_sent,
            "attachments": attachments,
        }

    finally:
        try:
            reset_dashboard(page)
            log("Dashboard reset completed")
        except Exception as e:
            log(f"Dashboard reset failed: {repr(e)}")

def main():
    if not Path(AUTH_STATE_FILE).exists():
        raise FileNotFoundError(
            f"Missing auth state file: {AUTH_STATE_FILE}. "
            "Create it first using a separate login/save-auth script."
        )

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=PLAYWRIGHT_HEADLESS,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ]
        )
        context = browser.new_context(
            storage_state=str(AUTH_STATE_FILE),
            accept_downloads=True,
        )
        page = context.new_page()
        page.set_default_timeout(240_000)

        page.on(
            "console",
            lambda msg: log(f"[BROWSER] {msg.type}: {msg.text}")
        )

        REPORT_URL = f"{LOGIN_URL}?report=1"
        log(f"LOGIN_URL : {LOGIN_URL}")
        log(f"REPORT_URL: {REPORT_URL}")

        # page.goto(
        #     REPORT_URL,
        #     wait_until="domcontentloaded",
        #     timeout=240000,
        # )

        page.goto(
            REPORT_URL,
            wait_until="networkidle",
            timeout=240000,
        )
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(3000)

        log(f"Current URL: {page.url}")

        if "github.com/login" in page.url:
            raise Exception("Playwright is not authenticated to GitHub Codespaces")

        page.screenshot(path="dashboard.png", full_page=True)
        log(page.evaluate("""
        () => ({
            openClientDirect: typeof openClientDirect,
            startReportSession: typeof startReportSession,
            loadUserForAdminOnly: typeof loadUserForAdminOnly,
            renderLoadedUser: typeof renderLoadedUser,
            waitFor: typeof waitFor,
            isAdmin: typeof isAdmin
        })
        """))

        log(page.url)
        result = run_client_report_job(
            page=page,
            client_login=TEST_CLIENT_LOGIN,
            client_name=TEST_CLIENT_NAME,
            recipients=[TEST_CLIENT_EMAIL] if SEND_EMAIL else [],
        )

        log(f"Generated result: {result}")

        context.close()
        browser.close()


if __name__ == "__main__":
    main()