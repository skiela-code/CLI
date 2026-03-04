"""Global search route."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.models import User
from app.services.search import global_search

router = APIRouter(prefix="/search", tags=["search"])


@router.get("/")
async def search_page(request: Request, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    query = request.query_params.get("q", "")
    doc_type = request.query_params.get("doc_type", "")
    status = request.query_params.get("status", "")
    category = request.query_params.get("category", "")

    results = None
    if query:
        filters = {}
        if doc_type:
            filters["doc_type"] = doc_type
        if status:
            filters["status"] = status
        if category:
            filters["category"] = category
        results = await global_search(db, query, filters)

    from app.main import templates as tmpl
    return tmpl.TemplateResponse("pages/search.html", {
        "request": request,
        "user": user,
        "query": query,
        "results": results,
        "doc_type": doc_type,
        "status": status,
        "category": category,
    })
