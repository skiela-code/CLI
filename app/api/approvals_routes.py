"""Approval routes: inbox, approve/reject."""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.models import (
    Approval, ApprovalStatus, AuditLog, DocStatus, Document,
    Notification, NotificationType, User,
)
from app.services.notifications import send_notification

router = APIRouter(prefix="/approvals", tags=["approvals"])


@router.get("/")
async def approvals_inbox(request: Request, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Approver inbox: list pending approvals for current user."""
    result = await db.execute(
        select(Approval)
        .where(Approval.approver_id == user.id)
        .order_by(Approval.created_at.desc())
    )
    approvals = result.scalars().all()

    # Load related documents
    approval_data = []
    for a in approvals:
        doc = await db.get(Document, a.document_id)
        approval_data.append({"approval": a, "document": doc})

    from app.main import templates as tmpl
    return tmpl.TemplateResponse("pages/approvals.html", {
        "request": request,
        "user": user,
        "approval_data": approval_data,
    })


@router.post("/{approval_id}/decide")
async def decide_approval(
    approval_id: str,
    request: Request,
    decision: str = Form(...),
    comment: str = Form(""),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    approval = await db.get(Approval, uuid.UUID(approval_id))
    if not approval or approval.approver_id != user.id:
        raise HTTPException(403, "Not authorized")

    if decision == "approve":
        approval.status = ApprovalStatus.APPROVED
    else:
        approval.status = ApprovalStatus.REJECTED

    approval.comment = comment
    approval.decided_at = datetime.utcnow()

    # Update document status
    doc = await db.get(Document, approval.document_id)
    if doc:
        if decision == "approve":
            doc.status = DocStatus.APPROVED
        else:
            doc.status = DocStatus.REJECTED

        # Notify document creator
        if doc.created_by:
            await send_notification(
                db,
                recipient_id=doc.created_by,
                type_=NotificationType.APPROVAL_DECISION,
                title=f"Document {decision}d: {doc.title}",
                body=f"Your document '{doc.title}' was {decision}d by {user.name}."
                     + (f" Comment: {comment}" if comment else ""),
                link=f"/documents/{doc.id}",
            )

    db.add(AuditLog(
        user_id=user.id, action=f"approval_{decision}",
        entity_type="approval", entity_id=approval_id,
        details={"comment": comment},
    ))
    await db.commit()

    return RedirectResponse(url="/approvals", status_code=302)
