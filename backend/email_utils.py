"""
Sends transactional emails (verification links, password reset links) via
SMTP if configured, otherwise prints the email content to the console.

The console fallback matters: it means email verification and password reset
work end-to-end in local dev / a quick demo without needing a real mail
provider set up. In production, set these env vars to a real SMTP provider
(Gmail SMTP with an app password, SendGrid, Mailgun, Resend, etc.):

  SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, FROM_EMAIL

If SMTP_HOST is unset, email verification enforcement is also skipped
entirely (see auth_deps.py) - so the app doesn't lock out real users while
you haven't set up an email provider yet during initial deployment.
"""

import os
import smtplib
from email.mime.text import MIMEText

SMTP_HOST = os.environ.get("SMTP_HOST", "")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
FROM_EMAIL = os.environ.get("FROM_EMAIL", SMTP_USER or "noreply@example.com")

EMAIL_ENABLED = bool(SMTP_HOST)


def send_email(to_email: str, subject: str, body: str):
    if not EMAIL_ENABLED:
        print(f"\n[EMAIL - SMTP not configured, printing instead]\nTo: {to_email}\nSubject: {subject}\n{body}\n")
        return

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = FROM_EMAIL
    msg["To"] = to_email

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.sendmail(FROM_EMAIL, [to_email], msg.as_string())


def send_verification_email(to_email: str, frontend_url: str, token: str):
    link = f"{frontend_url}/?verify_token={token}"
    send_email(
        to_email,
        "Verify your email - Ambulance Routing System",
        f"Click the link below to verify your email address:\n\n{link}\n\n"
        f"If you didn't create this account, you can ignore this email.",
    )


def send_password_reset_email(to_email: str, frontend_url: str, token: str):
    link = f"{frontend_url}/?reset_token={token}"
    send_email(
        to_email,
        "Reset your password - Ambulance Routing System",
        f"Click the link below to reset your password. This link expires in 1 hour.\n\n{link}\n\n"
        f"If you didn't request this, you can ignore this email.",
    )
