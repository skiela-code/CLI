"""Template routes: list, upload, view placeholders, builder."""

import os
import uuid

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.config import get_settings
from app.core.database import get_db
from app.models.models import (
    AuditLog, ContentBlock, DocType, PlaceholderSource,
    Template, TemplatePlaceholder, User,
)
from app.services.template_engine import extract_placeholders

router = APIRouter(prefix="/templates", tags=["templates"])
settings = get_settings()


@router.get("/")
async def templates_list(request: Request, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """List all templates."""
    result = await db.execute(select(Template).order_by(Template.created_at.desc()))
    templates_list = result.scalars().all()
    from app.main import templates as tmpl
    return tmpl.TemplateResponse("pages/templates.html", {
        "request": request,
        "user": user,
        "templates": templates_list,
    })


@router.get("/upload")
async def upload_page(request: Request, user: User = Depends(get_current_user)):
    from app.main import templates as tmpl
    return tmpl.TemplateResponse("pages/template_upload.html", {
        "request": request,
        "user": user,
        "doc_types": [e.value for e in DocType],
    })


@router.post("/upload")
async def upload_template(
    request: Request,
    name: str = Form(...),
    doc_type: str = Form(...),
    description: str = Form(""),
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Upload a DOCX template and extract placeholders."""
    os.makedirs(settings.upload_path, exist_ok=True)
    file_id = uuid.uuid4().hex
    file_path = os.path.join(settings.upload_path, f"{file_id}_{file.filename}")

    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    # Extract placeholders
    tokens = extract_placeholders(file_path)

    # Create template
    template = Template(
        name=name,
        doc_type=DocType(doc_type),
        description=description,
        file_path=file_path,
    )
    db.add(template)
    await db.flush()

    # Create placeholder records
    for token in tokens:
        ph = TemplatePlaceholder(
            template_id=template.id,
            token=token,
            label=token.strip("{}").replace("_", " ").title(),
        )
        db.add(ph)

    db.add(AuditLog(user_id=user.id, action="upload_template", entity_type="template", entity_id=str(template.id)))
    await db.commit()

    return RedirectResponse(url=f"/templates/{template.id}", status_code=302)


@router.get("/{template_id}")
async def template_detail(
    template_id: str,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """View template details and placeholders."""
    template = await db.get(Template, uuid.UUID(template_id))
    if not template:
        from fastapi import HTTPException
        raise HTTPException(404, "Template not found")

    ph_result = await db.execute(
        select(TemplatePlaceholder).where(TemplatePlaceholder.template_id == template.id)
    )
    placeholders = ph_result.scalars().all()

    from app.main import templates as tmpl
    return tmpl.TemplateResponse("pages/template_detail.html", {
        "request": request,
        "user": user,
        "template": template,
        "placeholders": placeholders,
    })


@router.get("/{template_id}/builder")
async def template_builder(
    template_id: str,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Template builder: map placeholders to fields/blocks/AI."""
    template = await db.get(Template, uuid.UUID(template_id))
    if not template:
        from fastapi import HTTPException
        raise HTTPException(404, "Template not found")

    ph_result = await db.execute(
        select(TemplatePlaceholder).where(TemplatePlaceholder.template_id == template.id)
    )
    placeholders = ph_result.scalars().all()

    blocks_result = await db.execute(select(ContentBlock).order_by(ContentBlock.title))
    blocks = blocks_result.scalars().all()

    sources = [s.value for s in PlaceholderSource]

    # Deal fields available for mapping
    deal_fields = [
        "deal.title", "deal.org_name", "deal.contact_name", "deal.contact_email",
        "deal.value", "deal.currency", "deal.status",
        "custom.industry", "custom.region",
    ]

    from app.main import templates as tmpl
    return tmpl.TemplateResponse("pages/template_builder.html", {
        "request": request,
        "user": user,
        "template": template,
        "placeholders": placeholders,
        "blocks": blocks,
        "sources": sources,
        "deal_fields": deal_fields,
    })


@router.post("/{template_id}/builder")
async def save_mappings(
    template_id: str,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Save placeholder mappings."""
    form = await request.form()
    template = await db.get(Template, uuid.UUID(template_id))
    if not template:
        from fastapi import HTTPException
        raise HTTPException(404, "Template not found")

    ph_result = await db.execute(
        select(TemplatePlaceholder).where(TemplatePlaceholder.template_id == template.id)
    )
    for ph in ph_result.scalars():
        source = form.get(f"source_{ph.id}", "manual")
        ph.source = PlaceholderSource(source)
        ph.source_field = form.get(f"field_{ph.id}", "")
        ph.default_value = form.get(f"default_{ph.id}", "")
        ph.ai_prompt = form.get(f"ai_prompt_{ph.id}", "")
        block_id = form.get(f"block_{ph.id}", "")
        ph.content_block_id = uuid.UUID(block_id) if block_id else None

    db.add(AuditLog(user_id=user.id, action="save_mappings", entity_type="template", entity_id=template_id))
    await db.commit()

    return RedirectResponse(url=f"/templates/{template_id}", status_code=302)
