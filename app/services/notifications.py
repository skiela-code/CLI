"""Notification service: multi-channel (DB inbox + SMTP + console logger)."""

import uuid
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import log
from app.models.models import Notification, NotificationType

settings = get_settings()


async def send_notification(
    db: AsyncSession,
    recipient_id: uuid.UUID,
    type_: NotificationType,
    title: str,
    body: str = "",
    link: str = "",
) -> Notification:
    """Create an in-app notification and optionally send email."""
    # 1. Persist to DB (inbox)
    notif = Notification(
        recipient_id=recipient_id,
        type=type_,
        title=title,
        body=body,
        link=link,
    )
    db.add(notif)
    await db.flush()

    # 2. Console log (always)
    log.info(
        "notification_sent",
        recipient=str(recipient_id),
        type=type_.value,
        title=title,
    )

    # 3. SMTP (if enabled)
    if settings.smtp_enabled:
        await _send_email(recipient_id, title, body)

    return notif


async def _send_email(recipient_id: uuid.UUID, subject: str, body: str) -> None:
    """Send email via SMTP. Best-effort, non-blocking."""
    import smtplib
    from email.message import EmailMessage

    try:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = settings.smtp_from
        msg["To"] = str(recipient_id)  # In prod, look up user email
        msg.set_content(body)

        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
            if settings.smtp_user:
                server.starttls()
                server.login(settings.smtp_user, settings.smtp_password)
            server.send_message(msg)
        log.info("email_sent", subject=subject)
    except Exception as e:
        log.error("email_failed", error=str(e))
