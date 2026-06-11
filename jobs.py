# jobs.py
from dashboard_reports import generate_client_reports
from mailer import send_email_with_attachments
from templates import build_email_subject, build_email_html
from user_data import find_user_record, load_client_json, get_client_name, get_recipient_email, get_valuation_date

def process_client_job(login_id: str, user_index: dict, users_dir: str, custom_message: str = "") -> dict:
    user_record = find_user_record(user_index, login_id)
    if not user_record:
        return {"login_id": login_id, "status": "failed", "reason": "User not found in user index"}

    to_email = get_recipient_email(user_record)
    if not to_email:
        return {"login_id": login_id, "status": "failed", "reason": "No email_connect found"}

    client_json = load_client_json(users_dir, user_record["file"])
    client_name = get_client_name(client_json)
    valuation_date = get_valuation_date(client_json)

    reports = generate_client_reports(login_id)

    subject = build_email_subject(client_name, valuation_date)
    html = build_email_html(client_name, valuation_date, custom_message)

    attachments = [reports["performance_pdf"]]
    if reports.get("profitbook_pdf"):
        attachments.append(reports["profitbook_pdf"])

    send_email_with_attachments(to_email, subject, html, attachments)

    return {
        "login_id": login_id,
        "client_name": client_name,
        "email": to_email,
        "status": "sent"
    }