"""Contract metadata extraction: rule-based scanning + AI structured extraction."""

import json
import re
from typing import Any

from app.core.logging import log

# Patterns for date extraction
_DATE_PATTERNS = [
    re.compile(r"effective\s+(?:date|as\s+of)[:\s]*(\d{1,2}[\s/.-]\w+[\s/.-]\d{2,4})", re.I),
    re.compile(r"dated?\s+(?:this\s+)?(\d{1,2}[\s/.-]\w+[\s/.-]\d{2,4})", re.I),
    re.compile(r"effective\s+(\d{4}-\d{2}-\d{2})", re.I),
    re.compile(r"(\d{1,2}\s+\w+\s+\d{4})", re.I),
]

# Patterns for term extraction
_TERM_PATTERNS = [
    re.compile(r"(?:initial\s+)?term\s+(?:of\s+)?(\d+)\s*months?", re.I),
    re.compile(r"(\d+)\s*(?:month|year)s?\s+(?:initial\s+)?term", re.I),
    re.compile(r"period\s+of\s+(\d+)\s*months?", re.I),
]

# Patterns for notice period
_NOTICE_PATTERNS = [
    re.compile(r"(\d+)\s*(?:calendar\s+)?days?\s*(?:prior\s+)?(?:written\s+)?notice", re.I),
    re.compile(r"notice\s+(?:period\s+)?(?:of\s+)?(\d+)\s*days?", re.I),
]

# Keywords to extract relevant paragraphs
_RELEVANT_KEYWORDS = [
    "effective date", "term", "renewal", "notice", "auto-renew",
    "automatically renew", "termination", "initial period",
    "signed date", "commencement", "expiry", "expires",
]


def _extract_relevant_snippets(text: str) -> list[str]:
    """Extract paragraphs containing relevant contract keywords."""
    paragraphs = text.split("\n")
    snippets = []
    for para in paragraphs:
        para_lower = para.lower()
        if any(kw in para_lower for kw in _RELEVANT_KEYWORDS):
            snippets.append(para.strip())
    return snippets[:20]  # Limit to 20 most relevant snippets


def extract_by_rules(text: str) -> dict[str, Any]:
    """Rule-based metadata extraction. Returns dict of {field: {value, confidence, snippet}}."""
    result = {}

    # Extract dates
    for pattern in _DATE_PATTERNS:
        match = pattern.search(text)
        if match:
            result["effective_date"] = {
                "value": match.group(1),
                "confidence": 0.5,
                "snippet": text[max(0, match.start()-50):match.end()+50],
            }
            break

    # Extract term
    for pattern in _TERM_PATTERNS:
        match = pattern.search(text)
        if match:
            months = int(match.group(1))
            # Detect if "year" was mentioned — convert
            context = text[max(0, match.start()-20):match.end()+20].lower()
            if "year" in context:
                months = months * 12
            result["initial_term_months"] = {
                "value": months,
                "confidence": 0.6,
                "snippet": text[max(0, match.start()-50):match.end()+50],
            }
            break

    # Extract notice period
    for pattern in _NOTICE_PATTERNS:
        match = pattern.search(text)
        if match:
            result["notice_period_days"] = {
                "value": int(match.group(1)),
                "confidence": 0.6,
                "snippet": text[max(0, match.start()-50):match.end()+50],
            }
            break

    # Check for auto-renew
    text_lower = text.lower()
    if "automatically renew" in text_lower or "auto-renew" in text_lower or "auto renew" in text_lower:
        result["auto_renew"] = {"value": True, "confidence": 0.7, "snippet": ""}
        # Find the snippet
        for kw in ["automatically renew", "auto-renew", "auto renew"]:
            idx = text_lower.find(kw)
            if idx >= 0:
                result["auto_renew"]["snippet"] = text[max(0, idx-50):idx+100]
                break

    return result


async def extract_contract_metadata(text: str) -> dict[str, Any]:
    """Extract structured contract metadata using rules + AI."""
    # Step 1: Rule-based
    rule_result = extract_by_rules(text)
    snippets = _extract_relevant_snippets(text)

    # Step 2: AI extraction for missing fields or higher confidence
    if snippets:
        try:
            from app.integrations.llm_router import get_llm_router
            router = get_llm_router()
            system = (
                "You are a contract metadata extractor. Extract the following fields from the contract text. "
                "Return a JSON object with these fields (use null if not found):\n"
                '- effective_date: ISO date string (YYYY-MM-DD)\n'
                '- signed_date: ISO date string (YYYY-MM-DD)\n'
                '- initial_term_months: integer\n'
                '- renewal_term_months: integer\n'
                '- auto_renew: boolean\n'
                '- notice_period_days: integer\n'
                '- pricing_summary: brief text summary of pricing\n'
                "Return ONLY valid JSON, no other text."
            )
            user_prompt = "Contract text snippets:\n\n" + "\n---\n".join(snippets)
            result = await router.generate(system, user_prompt, max_tokens=500)

            # Parse AI response
            # Try to find JSON in the response
            json_match = re.search(r'\{[^{}]*\}', result, re.DOTALL)
            if json_match:
                ai_data = json.loads(json_match.group())
                # Merge AI results with rule results, preferring higher confidence
                for field in ["effective_date", "signed_date", "initial_term_months",
                              "renewal_term_months", "auto_renew", "notice_period_days",
                              "pricing_summary"]:
                    if field in ai_data and ai_data[field] is not None:
                        existing = rule_result.get(field, {})
                        existing_conf = existing.get("confidence", 0) if existing else 0
                        ai_conf = 0.7  # AI baseline confidence
                        if existing_conf < ai_conf:
                            rule_result[field] = {
                                "value": ai_data[field],
                                "confidence": ai_conf,
                                "snippet": existing.get("snippet", ""),
                            }
        except Exception as e:
            log.warning("ai_metadata_extraction_failed", error=str(e))

    return rule_result
