import os
import smtplib
from email import policy
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from email.mime.text import MIMEText
from email.utils import formatdate, make_msgid

from dotenv import load_dotenv


class EmailError(Exception):
    """The mail server could not be reached or refused the message."""


def _smtp_settings() -> tuple[str, str, str, int]:
    """(from, password, host, port) from the environment; raises EmailError when incomplete."""
    load_dotenv()
    email_from = os.getenv('EMAIL_FROM')
    email_password = os.getenv('EMAIL_PASSWORD')
    smtp_host = os.getenv('SMTP_HOST')
    try:
        smtp_port = int(os.getenv('SMTP_PORT'))
    except (TypeError, ValueError):
        raise EmailError("SMTP_PORT is not configured")
    if not (email_from and smtp_host):
        raise EmailError("EMAIL_FROM and SMTP_HOST must be configured")
    return email_from, email_password, smtp_host, smtp_port


def send_message(email_to: str, subject: str, text: str, html: str | None = None) -> None:
    """Send a plain (optionally HTML) message, e.g. a sign-in code. Raises EmailError."""
    email_from, email_password, smtp_host, smtp_port = _smtp_settings()
    msg = MIMEMultipart('alternative', policy=policy.SMTP)
    msg['From'] = email_from
    msg['To'] = email_to
    msg['Subject'] = subject
    msg['Date'] = formatdate(localtime=True)
    msg['Message-ID'] = make_msgid(domain=email_from.split('@')[1])
    msg.attach(MIMEText(text, 'plain', 'utf-8'))
    if html:
        msg.attach(MIMEText(html, 'html', 'utf-8'))
    try:
        server = smtplib.SMTP(smtp_host, smtp_port)
        server.ehlo()
        server.starttls()
        server.login(email_from, email_password)
        server.send_message(msg)
        server.quit()
    except Exception as e:
        raise EmailError(f"Failed to send email: {e}") from e


def send_email(email_to: str, attachment_path: str) -> None:
    """
    Send an email with attachment to the specified recipient.

    Args:
        email_to (str): The recipient's email address
        attachment_path (str): Path to the file to be attached

    Returns:
        None

    Raises:
        EmailError: If the email could not be sent
    """
    email_from, email_password, smtp_host, smtp_port = _smtp_settings()

    # Create message
    msg = MIMEMultipart(policy=policy.SMTP)
    msg['From'] = email_from
    msg['To'] = email_to
    msg['Subject'] = "convert"

    body = MIMEText("Please convert this file.", "plain", "utf-8")
    msg.attach(body)

    # Add attachment
    with open(attachment_path, 'rb') as f:
        attachment = MIMEApplication(f.read(), _subtype="epub")
        attachment.add_header('Content-Disposition', 'attachment', filename=os.path.basename(attachment_path))
        msg.attach(attachment)

    # Set headers to avoid manual approval
    msg['Date'] = formatdate(localtime=True)
    msg['X-Mailer'] = 'Roundcube Webmail 1.4.13'
    sender_domain = email_from.split('@')[1]
    msg['Message-ID'] = make_msgid(domain=sender_domain)

    # Send email
    try:
        server = smtplib.SMTP(smtp_host, smtp_port)
        server.ehlo('webmail.'+sender_domain)
        server.starttls()
        server.login(email_from, email_password)
        server.send_message(msg)
        server.quit()
    except Exception as e:
        raise EmailError(f"Failed to send email: {e}") from e
