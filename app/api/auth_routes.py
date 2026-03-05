"""Authentication routes: OIDC + dev login fallback."""

import uuid

from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.core.logging import log
from app.models.models import AuditLog, User, UserRole

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()

# OIDC setup
oauth = OAuth()
if settings.oidc_client_id:
    oauth.register(
        name="oidc",
        client_id=settings.oidc_client_id,
        client_secret=settings.oidc_client_secret,
        server_metadata_url=f"{settings.oidc_provider_url}/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"},
    )


@router.get("/login")
async def login(request: Request):
    """Redirect to OIDC provider or show dev login."""
    if settings.dev_login_enabled:
        return RedirectResponse(url="/auth/dev-login")
    if not settings.oidc_client_id:
        raise HTTPException(400, "OIDC not configured and dev login is disabled")
    redirect_uri = settings.oidc_redirect_uri
    return await oauth.oidc.authorize_redirect(request, redirect_uri)


@router.get("/callback")
async def callback(request: Request, db: AsyncSession = Depends(get_db)):
    """OIDC callback handler."""
    try:
        token = await oauth.oidc.authorize_access_token(request)
    except Exception as e:
        log.error("oidc_callback_failed", error=str(e))
        raise HTTPException(400, f"OIDC error: {e}")

    userinfo = token.get("userinfo", {})
    sub = userinfo.get("sub", "")
    email = userinfo.get("email", "")
    name = userinfo.get("name", email)

    # Find or create user
    result = await db.execute(select(User).where(User.oidc_sub == sub))
    user = result.scalar_one_or_none()

    if not user:
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()

    if not user:
        user = User(email=email, name=name, oidc_sub=sub, role=UserRole.USER)
        db.add(user)
        await db.flush()

    if not user.oidc_sub:
        user.oidc_sub = sub
        await db.flush()

    request.session["user_id"] = str(user.id)
    db.add(AuditLog(user_id=user.id, action="login", details={"method": "oidc"}))
    await db.commit()

    return RedirectResponse(url="/", status_code=302)


@router.get("/dev-login")
async def dev_login_page(request: Request):
    """Show dev login form (only when DEV_LOGIN_ENABLED=true)."""
    if not settings.dev_login_enabled:
        raise HTTPException(403, "Dev login is disabled")
    from app.main import templates
    return templates.TemplateResponse("pages/dev_login.html", {"request": request})


@router.post("/dev-login")
async def dev_login_submit(request: Request, db: AsyncSession = Depends(get_db)):
    """Process dev login."""
    if not settings.dev_login_enabled:
        raise HTTPException(403, "Dev login is disabled")

    form = await request.form()
    email = form.get("email", "admin@clm.local")

    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user:
        user = User(
            email=str(email),
            name=str(email).split("@")[0].title(),
            role=UserRole.ADMIN,
        )
        db.add(user)
        await db.flush()

    # If user has a password (created via setup wizard), verify it
    password = form.get("password", "")
    if user.password_hash and password:
        from app.core.password import verify_password
        if not verify_password(str(password), user.password_hash):
            from app.main import templates
            return templates.TemplateResponse("pages/dev_login.html", {
                "request": request, "error": "Invalid password",
            })

    request.session["user_id"] = str(user.id)
    db.add(AuditLog(user_id=user.id, action="login", details={"method": "dev_login"}))
    await db.commit()

    return RedirectResponse(url="/", status_code=302)


@router.get("/logout")
async def logout(request: Request):
    """Clear session."""
    request.session.clear()
    return RedirectResponse(url="/auth/login", status_code=302)
