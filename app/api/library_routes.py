"""Document Library routes: upload, import, queue, detail, renewals."""

import os
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.auth import get_current_user
from app.core.config import get_settings
from app.core.database import get_db
from app.models.models import (
    AuditLog, ContractMetadata, DocStatus, DocType, Document,
    DocumentRelationship, DocumentService, ImportJob, ServiceCatalog, User,
)
from app.services.import_pipeline import start_import, extract_zip, get_import_status
from app.services.renewal_service import compute_renewal

router = APIRouter(prefix="/library", tags=["library"])
settings = get_settings()


@router.get("/")
async def library_list(
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List uploaded library documents."""
    doc_type = request.query_params.get("doc_type")
    company = request.query_params.get("company")
    status = request.query_params.get("import_status")

    q = select(Document).where(Document.source == "uploaded").order_by(Document.created_at.desc())

    if doc_type:
        q = q.where(Document.doc_type == doc_type)
    if company:
        q = q.where(Document.company_name == company)
    if status:
        q = q.where(Document.import_status == status)

    result = await db.execute(q.limit(100))
    docs = result.scalars().all()

    # Get unique companies for filter
    companies_q = await db.execute(
        select(Document.company_name)
        .where(Document.source == "uploaded", Document.company_name.isnot(None))
        .distinct()
    )
    companies = sorted([r[0] for r in companies_q.all() if r[0]])

    from app.main import templates as tmpl
    return tmpl.TemplateResponse("pages/library.html", {
        "request": request, "user": user, "documents": docs,
        "companies": companies,
        "doc_types": [e.value for e in DocType],
        "current_type": doc_type, "current_company": company,
        "current_status": status,
    })


@router.get("/upload")
async def upload_page(request: Request, user: User = Depends(get_current_user)):
    from app.main import templates as tmpl
    return tmpl.TemplateResponse("pages/library_upload.html", {
        "request": request, "user": user,
    })


@router.post("/upload")
async def upload_files(
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Handle multi-file upload (PDF, DOCX, ZIP)."""
    form = await request.form()
    files = form.getlist("files")

    if not files:
        raise HTTPException(400, "No files uploaded")

    upload_dir = os.path.join(settings.upload_path, "library", uuid.uuid4().hex)
    os.makedirs(upload_dir, exist_ok=True)

    file_paths = []
    for f in files:
        if not hasattr(f, 'filename') or not f.filename:
            continue
        filename = f.filename
        file_path = os.path.join(upload_dir, filename)
        content = await f.read()
        with open(file_path, "wb") as out:
            out.write(content)

        ext = os.path.splitext(filename)[1].lower()
        if ext == ".zip":
            # Extract ZIP and add contained files
            extracted = extract_zip(file_path, upload_dir)
            file_paths.extend(extracted)
        elif ext in (".pdf", ".docx"):
            file_paths.append(file_path)

    if not file_paths:
        raise HTTPException(400, "No valid PDF or DOCX files found")

    job_id = await start_import(db, file_paths, user.id)

    db.add(AuditLog(user_id=user.id, action="library_upload", details={"file_count": len(file_paths)}))
    await db.commit()

    return RedirectResponse(url=f"/library/import/{job_id}", status_code=302)


@router.get("/import/{job_id}")
async def import_progress(
    job_id: str,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Import progress page."""
    job = await db.get(ImportJob, uuid.UUID(job_id))
    if not job:
        raise HTTPException(404)

    status = get_import_status(job_id)

    from app.main import templates as tmpl
    return tmpl.TemplateResponse("pages/library_import_progress.html", {
        "request": request, "user": user, "job": job,
        "live_status": status.get("status", job.status),
    })


@router.get("/queue")
async def import_queue(
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Import queue: documents awaiting approval."""
    q = (
        select(Document)
        .where(Document.source == "uploaded", Document.import_status == "queued")
        .order_by(Document.created_at.desc())
    )
    result = await db.execute(q)
    docs = result.scalars().all()

    # Load contract metadata for renewal info
    doc_metadata = {}
    for doc in docs:
        if doc.doc_type == DocType.CONTRACT or (isinstance(doc.doc_type, str) and doc.doc_type == "contract"):
            cm_result = await db.execute(
                select(ContractMetadata).where(ContractMetadata.document_id == doc.id)
            )
            cm = cm_result.scalar_one_or_none()
            if cm:
                renewal = compute_renewal(
                    cm.effective_date, cm.initial_term_months,
                    cm.renewal_term_months, cm.auto_renew, cm.notice_period_days,
                )
                doc_metadata[str(doc.id)] = {"metadata": cm, "renewal": renewal}

    from app.main import templates as tmpl
    return tmpl.TemplateResponse("pages/library_queue.html", {
        "request": request, "user": user, "documents": docs,
        "doc_metadata": doc_metadata,
    })


@router.post("/queue/{doc_id}/approve")
async def approve_document(
    doc_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    doc = await db.get(Document, uuid.UUID(doc_id))
    if not doc:
        raise HTTPException(404)
    doc.import_status = "approved"
    db.add(AuditLog(user_id=user.id, action="library_approve", entity_type="document", entity_id=doc_id))
    await db.commit()
    return RedirectResponse(url="/library/queue", status_code=302)


@router.post("/queue/{doc_id}/reject")
async def reject_document(
    doc_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    doc = await db.get(Document, uuid.UUID(doc_id))
    if not doc:
        raise HTTPException(404)
    doc.import_status = "rejected"
    db.add(AuditLog(user_id=user.id, action="library_reject", entity_type="document", entity_id=doc_id))
    await db.commit()
    return RedirectResponse(url="/library/queue", status_code=302)


@router.post("/queue/{doc_id}/update")
async def update_queued_document(
    doc_id: str,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update metadata of a queued document before approval."""
    doc = await db.get(Document, uuid.UUID(doc_id))
    if not doc:
        raise HTTPException(404)

    form = await request.form()
    if form.get("title"):
        doc.title = str(form.get("title"))
    if form.get("doc_type"):
        doc.doc_type = DocType(str(form.get("doc_type")))
    if form.get("company_name"):
        doc.company_name = str(form.get("company_name"))

    # Update contract metadata
    if form.get("effective_date") or form.get("initial_term_months"):
        cm_result = await db.execute(
            select(ContractMetadata).where(ContractMetadata.document_id == doc.id)
        )
        cm = cm_result.scalar_one_or_none()
        if not cm:
            cm = ContractMetadata(document_id=doc.id)
            db.add(cm)
        if form.get("effective_date"):
            from datetime import date
            try:
                cm.effective_date = date.fromisoformat(str(form.get("effective_date")))
            except ValueError:
                pass
        if form.get("initial_term_months"):
            try:
                cm.initial_term_months = int(form.get("initial_term_months"))
            except ValueError:
                pass
        if form.get("notice_period_days"):
            try:
                cm.notice_period_days = int(form.get("notice_period_days"))
            except ValueError:
                pass
        cm.metadata_status = "approved"

    await db.commit()
    return RedirectResponse(url="/library/queue", status_code=302)


@router.get("/renewals")
async def renewal_dashboard(
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Renewal dashboard showing upcoming contract renewals."""
    period = request.query_params.get("period", "90")

    q = (
        select(Document, ContractMetadata)
        .join(ContractMetadata, ContractMetadata.document_id == Document.id)
        .where(Document.source == "uploaded", Document.import_status == "approved")
        .where(Document.doc_type == DocType.CONTRACT)
    )
    result = await db.execute(q)
    rows = result.all()

    renewals = []
    for doc, cm in rows:
        renewal = compute_renewal(
            cm.effective_date, cm.initial_term_months,
            cm.renewal_term_months, cm.auto_renew, cm.notice_period_days,
        )
        renewals.append({
            "document": doc,
            "metadata": cm,
            "renewal": renewal,
        })

    # Sort by next renewal date
    renewals.sort(key=lambda r: r["renewal"].get("current_term_end") or "9999-12-31")

    from app.main import templates as tmpl
    return tmpl.TemplateResponse("pages/renewal_dashboard.html", {
        "request": request, "user": user, "renewals": renewals,
        "current_period": period,
    })


@router.get("/{doc_id}")
async def library_detail(
    doc_id: str,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Library document detail page."""
    doc = await db.get(Document, uuid.UUID(doc_id))
    if not doc:
        raise HTTPException(404)

    # Contract metadata
    cm = None
    renewal = None
    if doc.doc_type == DocType.CONTRACT or (isinstance(doc.doc_type, str) and doc.doc_type == "contract"):
        cm_result = await db.execute(
            select(ContractMetadata).where(ContractMetadata.document_id == doc.id)
        )
        cm = cm_result.scalar_one_or_none()
        if cm:
            renewal = compute_renewal(
                cm.effective_date, cm.initial_term_months,
                cm.renewal_term_months, cm.auto_renew, cm.notice_period_days,
            )

    # Services
    svc_result = await db.execute(
        select(DocumentService, ServiceCatalog)
        .join(ServiceCatalog, DocumentService.service_id == ServiceCatalog.id)
        .where(DocumentService.document_id == doc.id)
    )
    services = svc_result.all()

    # Relationships
    children_result = await db.execute(
        select(DocumentRelationship, Document)
        .join(Document, DocumentRelationship.child_id == Document.id)
        .where(DocumentRelationship.parent_id == doc.id)
    )
    children = children_result.all()

    parents_result = await db.execute(
        select(DocumentRelationship, Document)
        .join(Document, DocumentRelationship.parent_id == Document.id)
        .where(DocumentRelationship.child_id == doc.id)
    )
    parents = parents_result.all()

    # Other documents for relating
    other_docs = await db.execute(
        select(Document)
        .where(Document.source == "uploaded", Document.id != doc.id)
        .order_by(Document.title)
        .limit(50)
    )

    from app.main import templates as tmpl
    return tmpl.TemplateResponse("pages/library_detail.html", {
        "request": request, "user": user, "doc": doc,
        "contract_metadata": cm, "renewal": renewal,
        "services": services, "children": children, "parents": parents,
        "other_docs": other_docs.scalars().all(),
        "doc_types": [e.value for e in DocType],
    })


@router.post("/{doc_id}/metadata")
async def update_metadata(
    doc_id: str,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Edit document metadata."""
    doc = await db.get(Document, uuid.UUID(doc_id))
    if not doc:
        raise HTTPException(404)

    form = await request.form()
    if form.get("title"):
        doc.title = str(form.get("title"))
    if form.get("doc_type"):
        doc.doc_type = DocType(str(form.get("doc_type")))
    if form.get("company_name"):
        doc.company_name = str(form.get("company_name"))

    await db.commit()
    return RedirectResponse(url=f"/library/{doc_id}", status_code=302)


@router.post("/{doc_id}/relate")
async def create_relationship(
    doc_id: str,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a document relationship."""
    form = await request.form()
    related_id = str(form.get("related_id", ""))
    rel_type = str(form.get("relationship_type", "annex"))

    if not related_id:
        raise HTTPException(400, "Related document required")

    rel = DocumentRelationship(
        parent_id=uuid.UUID(doc_id),
        child_id=uuid.UUID(related_id),
        relationship_type=rel_type,
    )
    db.add(rel)
    await db.commit()
    return RedirectResponse(url=f"/library/{doc_id}", status_code=302)


@router.get("/{doc_id}/download")
async def download_library_doc(
    doc_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Download an uploaded library document."""
    doc = await db.get(Document, uuid.UUID(doc_id))
    if not doc or not doc.file_path or not os.path.exists(doc.file_path):
        raise HTTPException(404, "File not found")
    return FileResponse(doc.file_path, filename=doc.title)
