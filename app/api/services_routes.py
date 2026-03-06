"""Service catalog management routes."""

import uuid

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user, require_role
from app.core.database import get_db
from app.models.models import ServiceCatalog, User, UserRole

router = APIRouter(prefix="/services", tags=["services"])


@router.get("/")
async def service_catalog_page(
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Service catalog management page."""
    result = await db.execute(
        select(ServiceCatalog).order_by(ServiceCatalog.name)
    )
    services = result.scalars().all()

    from app.main import templates as tmpl
    return tmpl.TemplateResponse("pages/service_catalog.html", {
        "request": request, "user": user, "services": services,
    })


@router.post("/")
async def create_service(
    request: Request,
    name: str = Form(...),
    description: str = Form(""),
    user: User = Depends(require_role(UserRole.ADMIN, UserRole.MANAGER)),
    db: AsyncSession = Depends(get_db),
):
    """Add a service to the catalog."""
    service = ServiceCatalog(name=name.strip(), description=description.strip() or None)
    db.add(service)
    await db.commit()
    return RedirectResponse(url="/services", status_code=302)


@router.post("/{service_id}/delete")
async def delete_service(
    service_id: str,
    user: User = Depends(require_role(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    """Remove a service from the catalog."""
    svc = await db.get(ServiceCatalog, uuid.UUID(service_id))
    if not svc:
        raise HTTPException(404)
    await db.delete(svc)
    await db.commit()
    return RedirectResponse(url="/services", status_code=302)
