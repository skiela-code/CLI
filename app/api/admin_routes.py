"""Admin settings and health dashboard routes."""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select, text, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import require_role
from app.core.database import get_db
from app.models.models import UserRole, AICall, User
from app.services.settings_service import (
    get_setting, set_setting, get_all_settings, mask_key, SECRET_KEYS,
)

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/settings")
async def settings_page(
    request: Request,
    user: User = Depends(require_role(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    """Admin settings page."""
    all_settings = await get_all_settings(db)
    display_settings = {}
    for k, v in all_settings.items():
        display_settings[k] = mask_key(v) if k in SECRET_KEYS else v

    total_result = await db.execute(select(func.count(AICall.id)))
    fallback_result = await db.execute(
        select(func.count(AICall.id)).where(AICall.fallback_used == True)
    )

    from app.main import templates
    return templates.TemplateResponse("pages/admin_settings.html", {
        "request": request,
        "user": user,
        "settings": display_settings,
        "total_ai_calls": total_result.scalar() or 0,
        "fallback_ai_calls": fallback_result.scalar() or 0,
    })


@router.post("/settings/ai")
async def save_ai_settings(
    request: Request,
    user: User = Depends(require_role(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    """Save AI provider settings."""
    form = await request.form()

    primary = str(form.get("ai_primary_provider", "mock"))
    await set_setting(db, "ai_primary_provider", primary)

    if primary == "anthropic":
        key_val = str(form.get("anthropic_api_key", ""))
        if key_val and not key_val.startswith("*"):
            await set_setting(db, "anthropic_api_key", key_val)
        model_val = str(form.get("anthropic_model", ""))
        if model_val:
            await set_setting(db, "anthropic_model", model_val)
    elif primary == "openrouter":
        key_val = str(form.get("openrouter_api_key", ""))
        if key_val and not key_val.startswith("*"):
            await set_setting(db, "openrouter_api_key", key_val)
        model_val = str(form.get("openrouter_model", ""))
        if model_val:
            await set_setting(db, "openrouter_model", model_val)
        base_url = str(form.get("openrouter_base_url", "")).strip()
        if base_url:
            await set_setting(db, "openrouter_base_url", base_url)

    fallback = str(form.get("ai_fallback_provider", "mock"))
    await set_setting(db, "ai_fallback_provider", fallback)

    await db.commit()
    return RedirectResponse(url="/admin/settings", status_code=302)


@router.post("/settings/ai/test")
async def test_provider(
    request: Request,
    user: User = Depends(require_role(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    """HTMX: Test a provider connection."""
    form = await request.form()
    provider_type = str(form.get("provider", "mock"))

    if provider_type == "mock":
        return HTMLResponse('<span class="badge bg-success">Mock OK</span>')

    try:
        if provider_type == "anthropic":
            from app.integrations.claude_ai import ClaudeProvider
            api_key = await get_setting(db, "anthropic_api_key") or ""
            model = await get_setting(db, "anthropic_model") or "claude-sonnet-4-20250514"
            provider = ClaudeProvider(api_key=api_key, model=model)
        elif provider_type == "openrouter":
            from app.integrations.openrouter_provider import OpenRouterProvider
            api_key = await get_setting(db, "openrouter_api_key") or ""
            model = await get_setting(db, "openrouter_model") or ""
            base_url = await get_setting(db, "openrouter_base_url")
            provider = OpenRouterProvider(api_key=api_key, model=model, base_url=base_url)
        else:
            return HTMLResponse('<span class="badge bg-warning">Unknown</span>')

        result = await provider.test_connection()
        if result["ok"]:
            return HTMLResponse(f'<span class="badge bg-success">{result["message"][:60]}</span>')
        return HTMLResponse(f'<span class="badge bg-danger">{result["message"][:80]}</span>')
    except Exception as e:
        return HTMLResponse(f'<span class="badge bg-danger">Error: {str(e)[:80]}</span>')


@router.get("/health")
async def health_page(
    request: Request,
    user: User = Depends(require_role(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    """Health dashboard."""
    checks = {}

    # DB check
    try:
        await db.execute(text("SELECT 1"))
        checks["database"] = {"status": "ok", "message": "Connected"}
    except Exception as e:
        checks["database"] = {"status": "error", "message": str(e)}

    # Migrations
    try:
        result = await db.execute(text("SELECT version_num FROM alembic_version"))
        version = result.scalar()
        checks["migrations"] = {"status": "ok", "message": f"Current: {version}"}
    except Exception:
        checks["migrations"] = {"status": "error", "message": "Cannot read alembic_version"}

    # Primary provider
    primary_type = await get_setting(db, "ai_primary_provider")
    checks["ai_primary"] = {
        "status": "ok" if primary_type else "warning",
        "message": primary_type or "Not configured",
    }

    # Fallback provider
    fallback_type = await get_setting(db, "ai_fallback_provider")
    checks["ai_fallback"] = {
        "status": "ok" if fallback_type else "info",
        "message": fallback_type or "Not configured",
    }

    # Pipedrive
    pd_mock = await get_setting(db, "pipedrive_mock_mode")
    checks["pipedrive"] = {"status": "ok", "message": f"Mock: {pd_mock or 'true'}"}

    from app.main import templates
    return templates.TemplateResponse("pages/admin_health.html", {
        "request": request, "user": user, "checks": checks,
    })
