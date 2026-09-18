import logging
import smtplib
from email.message import EmailMessage

from apps.api.config import settings


logger = logging.getLogger(__name__)


def send_password_reset_email(to_email: str, reset_url: str) -> None:
    subject = "Reset your password"
    body = (
        "We received a request to reset your password.\n\n"
        f"Reset your password using this link: {reset_url}\n\n"
        "This link expires shortly and can only be used once. If you "
        "did not request this, you can safely ignore this email."
    )

    if not settings.smtp_host:
        # No mail provider configured (e.g. local dev/test) — log the
        # email instead of failing the request. Logged at WARNING so it
        # is visible under default logging config (this codepath means
        # no email was actually sent).
        logger.warning(
            "Password reset email (SMTP not configured): to=%s body=%s",
            to_email,
            body,
        )
        return

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = settings.smtp_from_email
    message["To"] = to_email
    message.set_content(body)

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
        if settings.smtp_use_tls:
            server.starttls()

        if settings.smtp_username and settings.smtp_password:
            server.login(settings.smtp_username, settings.smtp_password)

        server.send_message(message)
