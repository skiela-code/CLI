"""Middleware that redirects to /setup if initial setup is not complete."""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import RedirectResponse

from app.core.database import async_session_factory
from app.services.settings_service import is_setup_complete

EXEMPT_PREFIXES = ("/setup", "/static", "/docs", "/openapi.json")

_setup_done = False


class SetupMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        global _setup_done
        if _setup_done:
            return await call_next(request)

        path = request.url.path
        if any(path.startswith(p) for p in EXEMPT_PREFIXES):
            return await call_next(request)

        async with async_session_factory() as db:
            complete = await is_setup_complete(db)

        if complete:
            _setup_done = True
            return await call_next(request)

        return RedirectResponse(url="/setup", status_code=302)
