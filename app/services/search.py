"""Postgres Full-Text Search across documents, templates, and content blocks."""

from typing import Any

from sqlalchemy import func, select, text, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import ContentBlock, Deal, Document, Template


async def global_search(
    db: AsyncSession,
    query: str,
    filters: dict[str, Any] | None = None,
) -> dict[str, list[dict]]:
    """Search across documents, templates, content blocks, and deals using Postgres FTS.

    Args:
        db: Async database session.
        query: Search query string.
        filters: Optional filters — doc_type, status, category.

    Returns:
        Dict with keys: documents, templates, blocks, deals — each a list of result dicts.
    """
    filters = filters or {}
    ts_query = func.plainto_tsquery("english", query)

    results: dict[str, list[dict]] = {
        "documents": [],
        "templates": [],
        "blocks": [],
        "deals": [],
    }

    # --- Documents ---
    doc_q = select(Document).where(
        Document.search_vector.op("@@")(ts_query)
    )
    if filters.get("doc_type"):
        doc_q = doc_q.where(Document.doc_type == filters["doc_type"])
    if filters.get("status"):
        doc_q = doc_q.where(Document.status == filters["status"])
    doc_rows = await db.execute(doc_q.limit(20))
    for doc in doc_rows.scalars():
        results["documents"].append({
            "id": str(doc.id),
            "title": doc.title,
            "type": "document",
            "doc_type": doc.doc_type if isinstance(doc.doc_type, str) else doc.doc_type.value,
            "status": doc.status if isinstance(doc.status, str) else doc.status.value,
        })

    # --- Templates ---
    tmpl_q = select(Template).where(
        Template.search_vector.op("@@")(ts_query)
    )
    tmpl_rows = await db.execute(tmpl_q.limit(20))
    for t in tmpl_rows.scalars():
        results["templates"].append({
            "id": str(t.id),
            "title": t.name,
            "type": "template",
            "doc_type": t.doc_type if isinstance(t.doc_type, str) else t.doc_type.value,
        })

    # --- Content Blocks ---
    block_q = select(ContentBlock).where(
        ContentBlock.search_vector.op("@@")(ts_query)
    )
    if filters.get("category"):
        block_q = block_q.where(ContentBlock.category == filters["category"])
    block_rows = await db.execute(block_q.limit(20))
    for b in block_rows.scalars():
        results["blocks"].append({
            "id": str(b.id),
            "title": b.title,
            "type": "content_block",
            "category": b.category,
        })

    # --- Deals ---
    deal_q = select(Deal).where(
        Deal.search_vector.op("@@")(ts_query)
    )
    deal_rows = await db.execute(deal_q.limit(20))
    for d in deal_rows.scalars():
        results["deals"].append({
            "id": str(d.id),
            "title": d.title,
            "type": "deal",
            "org_name": d.org_name,
        })

    return results
