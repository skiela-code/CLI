"""Setup wizard routes — accessible without auth until setup is complete."""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.password import hash_password
from app.core.logging import log
from app.models.models import User, UserRole, AuditLog
from app.services.settings_service import set_setting, is_setup_complete

router = APIRouter(prefix="/setup", tags=["setup"])


@router.get("/")
async def setup_page(request: Request, db: AsyncSession = Depends(get_db)):
    if await is_setup_complete(db):
        return RedirectResponse(url="/")
    from app.main import templates
    return templates.TemplateResponse("pages/setup_wizard.html", {"request": request})


@router.post("/step/admin")
async def setup_admin(request: Request, db: AsyncSession = Depends(get_db)):
    """Step 1: Create admin account."""
    if await is_setup_complete(db):
        return HTMLResponse('<div class="alert alert-info">Setup already complete.</div>')
    form = await request.form()
    email = str(form.get("email", "")).strip()
    password = str(form.get("password", ""))
    name = str(form.get("name", "")).strip() or email.split("@")[0].title()

    if not email or not password or len(password) < 8:
        return HTMLResponse(
            '<div class="alert alert-danger">Email required and password must be at least 8 characters.</div>'
        )

    user = User(
        email=email, name=name, role=UserRole.ADMIN,
        password_hash=hash_password(password),
    )
    db.add(user)
    await db.flush()

    request.session["user_id"] = str(user.id)
    db.add(AuditLog(user_id=user.id, action="setup_admin_created"))
    await db.commit()

    return HTMLResponse(
        '<div class="alert alert-success">Admin account created!</div>'
        '<script>document.getElementById("step-1").classList.add("d-none");'
        'document.getElementById("step-2").classList.remove("d-none");</script>'
    )


@router.post("/step/ai-provider")
async def setup_ai_provider(request: Request, db: AsyncSession = Depends(get_db)):
    """Step 2: AI Provider configuration."""
    form = await request.form()
    mock_mode = form.get("mock_mode") == "on"

    if mock_mode:
        await set_setting(db, "ai_primary_provider", "mock")
        await set_setting(db, "ai_fallback_provider", "mock")
    else:
        primary = str(form.get("primary_provider", "anthropic"))
        await set_setting(db, "ai_primary_provider", primary)

        if primary == "anthropic":
            api_key = str(form.get("anthropic_api_key", "")).strip()
            model = str(form.get("anthropic_model", "claude-sonnet-4-20250514")).strip()
            if api_key:
                await set_setting(db, "anthropic_api_key", api_key)
            if model:
                await set_setting(db, "anthropic_model", model)
        elif primary == "openrouter":
            api_key = str(form.get("openrouter_api_key", "")).strip()
            model = str(form.get("openrouter_model", "")).strip()
            if api_key:
                await set_setting(db, "openrouter_api_key", api_key)
            if model:
                await set_setting(db, "openrouter_model", model)
            base_url = str(form.get("openrouter_base_url", "")).strip()
            if base_url:
                await set_setting(db, "openrouter_base_url", base_url)

        fallback = str(form.get("fallback_provider", "mock"))
        await set_setting(db, "ai_fallback_provider", fallback)

    await db.commit()
    return HTMLResponse(
        '<div class="alert alert-success">AI provider configured!</div>'
        '<script>document.getElementById("step-2").classList.add("d-none");'
        'document.getElementById("step-3").classList.remove("d-none");</script>'
    )


@router.post("/step/ai-test")
async def test_ai_provider(request: Request, db: AsyncSession = Depends(get_db)):
    """HTMX endpoint: test a provider connection."""
    form = await request.form()
    provider_type = str(form.get("provider", "mock"))

    if provider_type == "mock":
        return HTMLResponse('<span class="badge bg-success">Mock provider OK</span>')

    try:
        if provider_type == "anthropic":
            from app.integrations.claude_ai import ClaudeProvider
            api_key = str(form.get("api_key", "")).strip()
            model = str(form.get("model", "claude-sonnet-4-20250514")).strip()
            provider = ClaudeProvider(api_key=api_key, model=model)
        elif provider_type == "openrouter":
            from app.integrations.openrouter_provider import OpenRouterProvider
            api_key = str(form.get("api_key", "")).strip()
            model = str(form.get("model", "")).strip()
            provider = OpenRouterProvider(api_key=api_key, model=model)
        else:
            return HTMLResponse('<span class="badge bg-warning">Unknown provider</span>')

        result = await provider.test_connection()
        if result["ok"]:
            return HTMLResponse(f'<span class="badge bg-success">Connected: {result["message"][:60]}</span>')
        else:
            return HTMLResponse(f'<span class="badge bg-danger">Failed: {result["message"][:80]}</span>')
    except Exception as e:
        return HTMLResponse(f'<span class="badge bg-danger">Error: {str(e)[:80]}</span>')


@router.post("/step/integrations")
async def setup_integrations(request: Request, db: AsyncSession = Depends(get_db)):
    """Step 3: Optional integrations (Pipedrive)."""
    form = await request.form()
    pipedrive_mock = form.get("pipedrive_mock_mode") == "on"
    await set_setting(db, "pipedrive_mock_mode", str(pipedrive_mock).lower())
    if not pipedrive_mock:
        token = str(form.get("pipedrive_api_token", "")).strip()
        if token:
            await set_setting(db, "pipedrive_api_token", token)
    await db.commit()
    return HTMLResponse(
        '<div class="alert alert-success">Integrations configured!</div>'
        '<script>document.getElementById("step-3").classList.add("d-none");'
        'document.getElementById("step-4").classList.remove("d-none");</script>'
    )


@router.post("/step/finish")
async def setup_finish(request: Request, db: AsyncSession = Depends(get_db)):
    """Step 4: Mark setup complete."""
    await set_setting(db, "setup_complete", "true")
    await db.commit()
    log.info("setup_complete")
    # Reset the middleware cache
    from app.core.setup_middleware import _setup_done
    import app.core.setup_middleware
    app.core.setup_middleware._setup_done = True
    return RedirectResponse(url="/", status_code=302)
