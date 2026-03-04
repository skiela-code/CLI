"""Document routes: generate, list, view, download, approve, attach to Pipedrive."""

import os
import uuid

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.database import get_db
from app.integrations.pipedrive import PipedriveClient
from app.models.models import (
    AuditLog, Approval, ApprovalStatus, Deal, DocStatus, DocType,
    Document, DocumentVersion, Notification, NotificationType,
    PricingTable, Template, User,
)
from app.services.doc_generator import get_task_status, start_generation
from app.services.notifications import send_notification

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("/")
async def documents_list(request: Request, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """List all documents."""
    result = await db.execute(select(Document).order_by(Document.created_at.desc()))
    docs = result.scalars().all()
    from app.main import templates as tmpl
    return tmpl.TemplateResponse("pages/documents.html", {
        "request": request,
        "user": user,
        "documents": docs,
    })


@router.get("/generate")
async def generate_page(request: Request, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Document generation form."""
    deals = (await db.execute(select(Deal).order_by(Deal.title))).scalars().all()
    templates_q = (await db.execute(select(Template).where(Template.is_active == True).order_by(Template.name))).scalars().all()
    pricing = (await db.execute(select(PricingTable).order_by(PricingTable.name))).scalars().all()

    from app.main import templates as tmpl
    return tmpl.TemplateResponse("pages/document_generate.html", {
        "request": request,
        "user": user,
        "deals": deals,
        "templates_list": templates_q,
        "pricing_tables": pricing,
        "doc_types": [e.value for e in DocType],
    })


@router.post("/generate")
async def generate_document(
    request: Request,
    title: str = Form(...),
    doc_type: str = Form(...),
    deal_id: str = Form(""),
    template_id: str = Form(""),
    pricing_table_id: str = Form(""),
    length: str = Form("medium"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create document and start generation."""
    doc = Document(
        title=title,
        doc_type=DocType(doc_type),
        deal_id=uuid.UUID(deal_id) if deal_id else None,
        template_id=uuid.UUID(template_id) if template_id else None,
        pricing_table_id=uuid.UUID(pricing_table_id) if pricing_table_id else None,
        created_by=user.id,
        status=DocStatus.DRAFT,
    )
    db.add(doc)
    db.add(AuditLog(user_id=user.id, action="generate_document", entity_type="document"))
    await db.commit()
    await db.refresh(doc)

    await start_generation(db, doc.id, options={"length": length})

    return RedirectResponse(url=f"/documents/{doc.id}", status_code=302)


@router.get("/{doc_id}")
async def document_detail(
    doc_id: str,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    doc = await db.get(Document, uuid.UUID(doc_id))
    if not doc:
        raise HTTPException(404)

    versions = (await db.execute(
        select(DocumentVersion).where(DocumentVersion.document_id == doc.id).order_by(DocumentVersion.version_number.desc())
    )).scalars().all()

    approvals = (await db.execute(
        select(Approval).where(Approval.document_id == doc.id).order_by(Approval.created_at.desc())
    )).scalars().all()

    users_q = (await db.execute(select(User).where(User.is_active == True))).scalars().all()

    task_status = get_task_status(doc_id)

    from app.main import templates as tmpl
    return tmpl.TemplateResponse("pages/document_detail.html", {
        "request": request,
        "user": user,
        "doc": doc,
        "versions": versions,
        "approvals": approvals,
        "users": users_q,
        "task_status": task_status,
    })


@router.get("/{doc_id}/download/{version_id}")
async def download_version(
    doc_id: str,
    version_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    version = await db.get(DocumentVersion, uuid.UUID(version_id))
    if not version or not os.path.exists(version.file_path):
        raise HTTPException(404, "File not found")
    return FileResponse(
        version.file_path,
        filename=f"document_{version.version_number}.docx",
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


@router.post("/{doc_id}/approve/request")
async def request_approval(
    doc_id: str,
    request: Request,
    approver_id: str = Form(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    doc = await db.get(Document, uuid.UUID(doc_id))
    if not doc:
        raise HTTPException(404)

    # Get latest version
    latest = (await db.execute(
        select(DocumentVersion)
        .where(DocumentVersion.document_id == doc.id)
        .order_by(DocumentVersion.version_number.desc())
        .limit(1)
    )).scalar_one_or_none()

    if not latest:
        raise HTTPException(400, "No version generated yet")

    approval = Approval(
        document_id=doc.id,
        version_id=latest.id,
        approver_id=uuid.UUID(approver_id),
    )
    db.add(approval)
    doc.status = DocStatus.PENDING_APPROVAL

    await send_notification(
        db,
        recipient_id=uuid.UUID(approver_id),
        type_=NotificationType.APPROVAL_REQUEST,
        title=f"Approval requested: {doc.title}",
        body=f"{user.name} has requested your approval for '{doc.title}'.",
        link=f"/documents/{doc.id}",
    )

    db.add(AuditLog(user_id=user.id, action="request_approval", entity_type="document", entity_id=doc_id))
    await db.commit()

    return RedirectResponse(url=f"/documents/{doc_id}", status_code=302)


@router.post("/{doc_id}/attach-pipedrive")
async def attach_to_pipedrive(
    doc_id: str,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Attach generated file to deal in Pipedrive."""
    doc = await db.get(Document, uuid.UUID(doc_id))
    if not doc or not doc.deal_id:
        raise HTTPException(400, "No deal associated")

    deal = await db.get(Deal, doc.deal_id)
    if not deal or not deal.pipedrive_id:
        raise HTTPException(400, "Deal not synced to Pipedrive")

    latest = (await db.execute(
        select(DocumentVersion)
        .where(DocumentVersion.document_id == doc.id)
        .order_by(DocumentVersion.version_number.desc())
        .limit(1)
    )).scalar_one_or_none()

    if not latest or not os.path.exists(latest.file_path):
        raise HTTPException(400, "No file to attach")

    client = PipedriveClient()
    await client.attach_file(deal.pipedrive_id, latest.file_path, f"{doc.title}.docx")
    await client.create_note(deal.pipedrive_id, f"Document '{doc.title}' v{latest.version_number} attached via CLM-lite.")

    db.add(AuditLog(user_id=user.id, action="attach_pipedrive", entity_type="document", entity_id=doc_id))
    await db.commit()

    return RedirectResponse(url=f"/documents/{doc_id}", status_code=302)
