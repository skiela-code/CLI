"""Service extraction: match document text against service catalog."""

import json
import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import log
from app.models.models import ServiceCatalog


async def extract_services(db: AsyncSession, text: str) -> list[dict[str, Any]]:
    """Extract services from document text against the catalog.

    Returns list of {service_id, service_name, confidence, source_snippet}.
    """
    # Load catalog
    result = await db.execute(select(ServiceCatalog).where(ServiceCatalog.is_active == True))
    catalog = result.scalars().all()

    if not catalog or not text.strip():
        return []

    # Rule-based: simple text matching first
    text_lower = text.lower()
    matches = []
    matched_ids = set()

    for service in catalog:
        name_lower = service.name.lower()
        if name_lower in text_lower:
            # Find snippet
            idx = text_lower.find(name_lower)
            snippet = text[max(0, idx - 50):idx + len(service.name) + 50]
            matches.append({
                "service_id": str(service.id),
                "service_name": service.name,
                "confidence": 0.8,
                "source_snippet": snippet.strip(),
            })
            matched_ids.add(str(service.id))

    # AI extraction for additional matches
    if catalog:
        try:
            from app.integrations.llm_router import get_llm_router
            router = get_llm_router()
            catalog_names = [s.name for s in catalog]
            system = (
                "You are a service identifier. Given a document and a service catalog, "
                "identify which services from the catalog are mentioned or referenced. "
                "Return a JSON array of service names that are mentioned. "
                "ONLY return services from the provided catalog. Return ONLY valid JSON."
            )
            user_prompt = (
                f"Service catalog: {json.dumps(catalog_names)}\n\n"
                f"Document text (first 4000 chars):\n{text[:4000]}"
            )
            result_text = await router.generate(system, user_prompt, max_tokens=200)

            # Parse response
            json_match = re.search(r'\[.*\]', result_text, re.DOTALL)
            if json_match:
                ai_services = json.loads(json_match.group())
                for svc_name in ai_services:
                    # Find matching catalog entry
                    for service in catalog:
                        if service.name.lower() == svc_name.lower() and str(service.id) not in matched_ids:
                            matches.append({
                                "service_id": str(service.id),
                                "service_name": service.name,
                                "confidence": 0.6,
                                "source_snippet": "",
                            })
                            matched_ids.add(str(service.id))
                            break
        except Exception as e:
            log.warning("ai_service_extraction_failed", error=str(e))

    return matches
