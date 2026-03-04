"""Pricing table routes: CRUD for quote builder."""

import uuid

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.models import Deal, PricingLineItem, PricingTable, User

router = APIRouter(prefix="/pricing", tags=["pricing"])


@router.get("/")
async def pricing_list(request: Request, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(PricingTable).order_by(PricingTable.created_at.desc()))
    tables = result.scalars().all()
    from app.main import templates as tmpl
    return tmpl.TemplateResponse("pages/pricing.html", {
        "request": request,
        "user": user,
        "tables": tables,
    })


@router.get("/new")
async def new_pricing_page(request: Request, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    deals_result = await db.execute(select(Deal).order_by(Deal.title))
    deals = deals_result.scalars().all()
    from app.main import templates as tmpl
    return tmpl.TemplateResponse("pages/pricing_form.html", {
        "request": request,
        "user": user,
        "table": None,
        "items": [],
        "deals": deals,
    })


@router.post("/new")
async def create_pricing(
    request: Request,
    name: str = Form(...),
    deal_id: str = Form(""),
    tier: str = Form("standard"),
    currency: str = Form("EUR"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    pt = PricingTable(
        name=name,
        deal_id=uuid.UUID(deal_id) if deal_id else None,
        tier=tier,
        currency=currency,
    )
    db.add(pt)
    await db.commit()
    return RedirectResponse(url=f"/pricing/{pt.id}", status_code=302)


@router.get("/{table_id}")
async def pricing_detail(
    table_id: str,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    pt = await db.get(PricingTable, uuid.UUID(table_id))
    if not pt:
        from fastapi import HTTPException
        raise HTTPException(404)
    items_result = await db.execute(
        select(PricingLineItem).where(PricingLineItem.pricing_table_id == pt.id).order_by(PricingLineItem.sort_order)
    )
    items = items_result.scalars().all()
    grand_total = sum(i.quantity * i.unit_price * (1 - i.discount_pct / 100) for i in items)

    deals_result = await db.execute(select(Deal).order_by(Deal.title))
    deals = deals_result.scalars().all()

    from app.main import templates as tmpl
    return tmpl.TemplateResponse("pages/pricing_form.html", {
        "request": request,
        "user": user,
        "table": pt,
        "items": items,
        "deals": deals,
        "grand_total": grand_total,
    })


@router.post("/{table_id}/item")
async def add_line_item(
    table_id: str,
    request: Request,
    description: str = Form(...),
    quantity: float = Form(1),
    unit_price: float = Form(0),
    discount_pct: float = Form(0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Get max sort order
    items_result = await db.execute(
        select(PricingLineItem).where(PricingLineItem.pricing_table_id == uuid.UUID(table_id))
    )
    items = items_result.scalars().all()
    max_order = max((i.sort_order for i in items), default=-1) + 1

    item = PricingLineItem(
        pricing_table_id=uuid.UUID(table_id),
        description=description,
        quantity=quantity,
        unit_price=unit_price,
        discount_pct=discount_pct,
        sort_order=max_order,
    )
    db.add(item)
    await db.commit()
    return RedirectResponse(url=f"/pricing/{table_id}", status_code=302)


@router.post("/{table_id}/item/{item_id}/delete")
async def delete_line_item(
    table_id: str,
    item_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    item = await db.get(PricingLineItem, uuid.UUID(item_id))
    if item:
        await db.delete(item)
        await db.commit()
    return RedirectResponse(url=f"/pricing/{table_id}", status_code=302)
