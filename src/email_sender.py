import os
import smtplib
from email import policy
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from email.mime.text import MIMEText
from email.utils import formatdate, make_msgid

from dotenv import load_dotenv


def send_email(email_to: str, attachment_path: str) -> None:
    """
    Send an email with attachment to the specified recipient.

    Args:
        email_to (str): The recipient's email address
        attachment_path (str): Path to the file to be attached

    Returns:
        None

    Raises:
        Exception: If email sending fails
    """
    load_dotenv()

    # Get email configuration from environment variables
    email_from = os.getenv('EMAIL_FROM')
    email_password = os.getenv('EMAIL_PASSWORD')
    smtp_host = os.getenv('SMTP_HOST')
    smtp_port = int(os.getenv('SMTP_PORT'))

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
        raise Exception(f"Failed to send email: {str(e)}")
