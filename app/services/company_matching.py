"""Company matching: match documents to known companies from deals."""

import os
import re
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import log
from app.models.models import Deal


async def match_company(
    db: AsyncSession, filename: str, text: str
) -> tuple[Optional[str], float]:
    """Match document to a company by checking text against known org_names.

    Returns (org_name, confidence). Returns (None, 0) if no match.
    """
    # Load all known company names
    result = await db.execute(
        select(Deal.org_name, Deal.contact_email)
        .where(Deal.org_name.isnot(None))
        .distinct()
    )
    companies = result.all()

    if not companies:
        return None, 0.0

    text_lower = text.lower()
    filename_lower = filename.lower()
    best_match: Optional[str] = None
    best_score = 0.0

    for row in companies:
        org_name = row[0]
        contact_email = row[1]
        if not org_name:
            continue

        score = 0.0
        org_lower = org_name.lower()

        # Check filename for company name
        # Normalize both for comparison (remove common suffixes)
        org_clean = re.sub(r'\b(corp|corporation|ltd|gmbh|inc|llc|sa|ag)\b', '', org_lower).strip()
        if org_clean and org_clean in filename_lower:
            score += 0.4

        # Check document text for company name (exact match)
        if org_lower in text_lower:
            score += 0.5
            # Bonus for multiple occurrences
            count = text_lower.count(org_lower)
            if count > 2:
                score += 0.1

        # Check for email domain match
        if contact_email:
            domain = contact_email.split("@")[-1].lower()
            domain_base = domain.split(".")[0]
            if domain_base and len(domain_base) > 2 and domain_base in text_lower:
                score += 0.2

        if score > best_score:
            best_score = score
            best_match = org_name

    if best_score < 0.1:
        return None, 0.0

    return best_match, min(best_score, 1.0)
