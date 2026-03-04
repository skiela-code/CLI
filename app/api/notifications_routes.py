"""Notifications routes."""

import uuid

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.models import Notification, User

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("/")
async def notifications_page(request: Request, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Notification)
        .where(Notification.recipient_id == user.id)
        .order_by(Notification.created_at.desc())
        .limit(50)
    )
    notifications = result.scalars().all()
    from app.main import templates as tmpl
    return tmpl.TemplateResponse("pages/notifications.html", {
        "request": request,
        "user": user,
        "notifications": notifications,
    })


@router.post("/{notif_id}/read")
async def mark_read(
    notif_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    notif = await db.get(Notification, uuid.UUID(notif_id))
    if notif and notif.recipient_id == user.id:
        notif.is_read = True
        await db.commit()
    return RedirectResponse(url="/notifications", status_code=302)


async def get_unread_count(db: AsyncSession, user_id: uuid.UUID) -> int:
    result = await db.execute(
        select(func.count(Notification.id))
        .where(Notification.recipient_id == user_id, Notification.is_read == False)
    )
    return result.scalar() or 0
