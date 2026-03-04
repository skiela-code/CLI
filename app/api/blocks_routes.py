"""Content blocks CRUD routes."""

import uuid

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.models import ContentBlock, User

router = APIRouter(prefix="/blocks", tags=["blocks"])


@router.get("/")
async def blocks_list(request: Request, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """List content blocks with optional category filter."""
    category = request.query_params.get("category", "")
    q = select(ContentBlock).order_by(ContentBlock.created_at.desc())
    if category:
        q = q.where(ContentBlock.category == category)
    result = await db.execute(q)
    blocks = result.scalars().all()

    # Get distinct categories
    cat_result = await db.execute(
        select(ContentBlock.category).distinct().where(ContentBlock.category.isnot(None))
    )
    categories = [c for (c,) in cat_result if c]

    from app.main import templates as tmpl
    return tmpl.TemplateResponse("pages/blocks.html", {
        "request": request,
        "user": user,
        "blocks": blocks,
        "categories": categories,
        "current_category": category,
    })


@router.get("/new")
async def new_block_page(request: Request, user: User = Depends(get_current_user)):
    from app.main import templates as tmpl
    return tmpl.TemplateResponse("pages/block_form.html", {
        "request": request,
        "user": user,
        "block": None,
    })


@router.post("/new")
async def create_block(
    request: Request,
    title: str = Form(...),
    body: str = Form(...),
    category: str = Form(""),
    tags: str = Form(""),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    block = ContentBlock(
        title=title,
        body=body,
        category=category or None,
        tags=[t.strip() for t in tags.split(",") if t.strip()] if tags else [],
    )
    db.add(block)
    await db.commit()
    return RedirectResponse(url="/blocks", status_code=302)


@router.get("/{block_id}/edit")
async def edit_block_page(
    block_id: str,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    block = await db.get(ContentBlock, uuid.UUID(block_id))
    from app.main import templates as tmpl
    return tmpl.TemplateResponse("pages/block_form.html", {
        "request": request,
        "user": user,
        "block": block,
    })


@router.post("/{block_id}/edit")
async def update_block(
    block_id: str,
    request: Request,
    title: str = Form(...),
    body: str = Form(...),
    category: str = Form(""),
    tags: str = Form(""),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    block = await db.get(ContentBlock, uuid.UUID(block_id))
    if block:
        block.title = title
        block.body = body
        block.category = category or None
        block.tags = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
        await db.commit()
    return RedirectResponse(url="/blocks", status_code=302)


@router.post("/{block_id}/delete")
async def delete_block(
    block_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    block = await db.get(ContentBlock, uuid.UUID(block_id))
    if block:
        await db.delete(block)
        await db.commit()
    return RedirectResponse(url="/blocks", status_code=302)
