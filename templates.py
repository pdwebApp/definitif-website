# templates.py
def build_email_subject(client_name: str, valuation_date: str) -> str:
    if valuation_date:
        return f"Your Performance and Profitbook Reports - {client_name} - {valuation_date}"
    return f"Your Performance and Profitbook Reports - {client_name}"

def build_email_html(client_name: str, valuation_date: str, custom_message: str = "") -> str:
    valuation_html = f"<p><strong>Valuation Date:</strong> {valuation_date}</p>" if valuation_date else ""
    message_html = f"<p>{custom_message}</p>" if custom_message else ""

    return f"""
    <html>
      <body style="font-family: Arial, sans-serif; color: #1f2937; line-height: 1.6;">
        <p>Dear {client_name},</p>
        <p>Please find attached your latest Performance and Profitbook reports.</p>
        {valuation_html}
        {message_html}
        <p>Regards,<br>Definitif Team</p>
      </body>
    </html>
    """