"""Deals routes: list/search from Pipedrive, sync to local DB."""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.database import get_db
from app.integrations.pipedrive import PipedriveClient
from app.models.models import AuditLog, Deal, User

router = APIRouter(prefix="/deals", tags=["deals"])


@router.get("/")
async def deals_page(request: Request, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Deals list page."""
    search = request.query_params.get("search", "")
    source = request.query_params.get("source", "pipedrive")

    deals = []
    local_deals = []

    # Always load local deals
    q = select(Deal).order_by(Deal.created_at.desc())
    result = await db.execute(q)
    local_deals = [
        {
            "id": str(d.id),
            "pipedrive_id": d.pipedrive_id,
            "title": d.title,
            "org_name": d.org_name or "",
            "contact_name": d.contact_name or "",
            "value": d.value or 0,
            "currency": d.currency,
            "status": d.status,
            "synced": True,
        }
        for d in result.scalars()
    ]

    # Load from Pipedrive if requested
    if source == "pipedrive":
        client = PipedriveClient()
        pd_deals = await client.list_deals(search=search if search else None)
        synced_ids = {d["pipedrive_id"] for d in local_deals if d["pipedrive_id"]}
        deals = [
            {**d, "synced": d["id"] in synced_ids}
            for d in pd_deals
        ]

    from app.main import templates as tmpl
    return tmpl.TemplateResponse("pages/deals.html", {
        "request": request,
        "user": user,
        "deals": deals,
        "local_deals": local_deals,
        "search": search,
        "source": source,
    })


@router.post("/sync/{pipedrive_id}")
async def sync_deal(
    pipedrive_id: int,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Sync a Pipedrive deal into local DB."""
    # Check if already synced
    result = await db.execute(select(Deal).where(Deal.pipedrive_id == pipedrive_id))
    existing = result.scalar_one_or_none()

    client = PipedriveClient()
    pd_deal = await client.get_deal(pipedrive_id)

    if existing:
        existing.title = pd_deal["title"]
        existing.org_name = pd_deal.get("org_name", "")
        existing.contact_name = pd_deal.get("person_name", "")
        existing.contact_email = pd_deal.get("person_email", "")
        existing.value = pd_deal.get("value", 0)
        existing.currency = pd_deal.get("currency", "EUR")
        existing.status = pd_deal.get("status", "open")
        existing.custom_fields = pd_deal.get("custom_fields", {})
        existing.synced_at = datetime.utcnow()
        deal = existing
    else:
        deal = Deal(
            pipedrive_id=pipedrive_id,
            title=pd_deal["title"],
            org_name=pd_deal.get("org_name", ""),
            contact_name=pd_deal.get("person_name", ""),
            contact_email=pd_deal.get("person_email", ""),
            value=pd_deal.get("value", 0),
            currency=pd_deal.get("currency", "EUR"),
            status=pd_deal.get("status", "open"),
            custom_fields=pd_deal.get("custom_fields", {}),
            synced_at=datetime.utcnow(),
        )
        db.add(deal)

    db.add(AuditLog(user_id=user.id, action="sync_deal", entity_type="deal", entity_id=str(pipedrive_id)))
    await db.commit()

    from app.main import templates as tmpl
    return tmpl.TemplateResponse("components/deal_row.html", {
        "request": request,
        "deal": {
            "id": str(deal.id),
            "pipedrive_id": deal.pipedrive_id,
            "title": deal.title,
            "org_name": deal.org_name,
            "contact_name": deal.contact_name,
            "value": deal.value,
            "currency": deal.currency,
            "status": deal.status,
            "synced": True,
        },
    })
