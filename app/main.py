"""CLM-lite + Proposal Generator — FastAPI application."""

import uuid

from fastapi import Depends, FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.core.logging import setup_logging
from app.core.auth import get_optional_user
from app.models.models import Notification, User

setup_logging()
settings = get_settings()

app = FastAPI(title="CLM-lite + Proposal Generator", version="1.0.0")

# Middleware
app.add_middleware(SessionMiddleware, secret_key=settings.app_secret_key)

# Static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Templates
templates = Jinja2Templates(directory="app/templates")

# Register routes
from app.api.auth_routes import router as auth_router
from app.api.deals_routes import router as deals_router
from app.api.templates_routes import router as templates_router
from app.api.blocks_routes import router as blocks_router
from app.api.pricing_routes import router as pricing_router
from app.api.documents_routes import router as documents_router
from app.api.approvals_routes import router as approvals_router
from app.api.search_routes import router as search_router
from app.api.notifications_routes import router as notifications_router

app.include_router(auth_router)
app.include_router(deals_router)
app.include_router(templates_router)
app.include_router(blocks_router)
app.include_router(pricing_router)
app.include_router(documents_router)
app.include_router(approvals_router)
app.include_router(search_router)
app.include_router(notifications_router)


@app.get("/")
async def index(request: Request, user: User = Depends(get_optional_user), db: AsyncSession = Depends(get_db)):
    """Dashboard / home page."""
    if not user:
        return RedirectResponse(url="/auth/login")

    # Get notification count
    unread_count = 0
    if user:
        result = await db.execute(
            select(func.count(Notification.id))
            .where(Notification.recipient_id == user.id, Notification.is_read == False)
        )
        unread_count = result.scalar() or 0

    return templates.TemplateResponse("pages/dashboard.html", {
        "request": request,
        "user": user,
        "unread_count": unread_count,
    })
