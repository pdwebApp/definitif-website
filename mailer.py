# mailer.py
import mimetypes
import smtplib
from email.message import EmailMessage

from config import GMAIL_SMTP_HOST, GMAIL_SMTP_PORT, GMAIL_SENDER, GMAIL_APP_PASSWORD

def send_email_with_attachments(to_email: str, subject: str, html_body: str, attachment_paths: list[str]):
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = GMAIL_SENDER
    msg["To"] = to_email
    msg.set_content("Please view this email in HTML format.")
    msg.add_alternative(html_body, subtype="html")

    for path in attachment_paths:
        mime_type, _ = mimetypes.guess_type(path)
        maintype, subtype = (mime_type or "application/octet-stream").split("/", 1)

        with open(path, "rb") as f:
            msg.add_attachment(
                f.read(),
                maintype=maintype,
                subtype=subtype,
                filename=path.split("/")[-1]
            )

    with smtplib.SMTP(GMAIL_SMTP_HOST, GMAIL_SMTP_PORT) as server:
        server.starttls()
        server.login(GMAIL_SENDER, GMAIL_APP_PASSWORD)
        server.send_message(msg)