"""Red-flags checker: pre-send validation for documents."""

import re
from typing import Any


FORBIDDEN_TERMS = [
    "guaranteed",
    "unlimited liability",
    "irrevocable",
    "in perpetuity",
    "waive all rights",
    "no refund",
]


def check_red_flags(
    content: dict[str, str],
    deal: dict[str, Any] | None = None,
    pricing: list[dict] | None = None,
) -> dict[str, list[dict]]:
    """Run red-flag checks and return structured results.

    Args:
        content: Dict mapping section_name -> section text.
        deal: Deal context dict (for name/date consistency checks).
        pricing: List of pricing line item dicts.

    Returns:
        {"flags": [...], "summary": {"total": N, "critical": N, "warning": N}}
    """
    flags: list[dict] = []

    all_text = " ".join(content.values())

    # 1. Missing placeholders
    remaining = re.findall(r"\{\{[A-Z_]+\}\}", all_text)
    if remaining:
        flags.append({
            "type": "critical",
            "category": "missing_placeholder",
            "message": f"Unreplaced placeholders found: {', '.join(set(remaining))}",
            "details": list(set(remaining)),
        })

    # 2. Forbidden terms
    for term in FORBIDDEN_TERMS:
        if term.lower() in all_text.lower():
            flags.append({
                "type": "warning",
                "category": "forbidden_term",
                "message": f"Forbidden term detected: '{term}'",
                "details": {"term": term},
            })

    # 3. Name consistency
    if deal:
        client_name = deal.get("org_name") or deal.get("contact_name") or ""
        if client_name and client_name not in all_text:
            flags.append({
                "type": "warning",
                "category": "name_mismatch",
                "message": f"Client name '{client_name}' not found in document text",
                "details": {"expected": client_name},
            })

    # 4. Date checks — look for obviously wrong dates
    date_matches = re.findall(r"\b(20\d{2})\b", all_text)
    years = {int(y) for y in date_matches}
    if years:
        import datetime
        current_year = datetime.date.today().year
        old = [y for y in years if y < current_year - 1]
        if old:
            flags.append({
                "type": "warning",
                "category": "date_issue",
                "message": f"Document references old year(s): {old}",
                "details": {"years": old},
            })

    # 5. Pricing mismatch between table and narrative
    if pricing and content:
        total_from_table = sum(
            item.get("quantity", 1) * item.get("unit_price", 0) * (1 - item.get("discount_pct", 0) / 100)
            for item in pricing
        )
        # Look for currency amounts in narrative
        amounts = re.findall(r"[\$€£]\s*([0-9,]+(?:\.[0-9]{1,2})?)", all_text)
        amounts += re.findall(r"([0-9,]+(?:\.[0-9]{1,2})?)\s*(?:EUR|USD|GBP)", all_text)
        parsed = []
        for a in amounts:
            try:
                parsed.append(float(a.replace(",", "")))
            except ValueError:
                pass

        if parsed:
            for amt in parsed:
                if abs(amt - total_from_table) > 1 and amt > 100:
                    # Only flag if we find an amount that doesn't match and is significant
                    flags.append({
                        "type": "warning",
                        "category": "pricing_mismatch",
                        "message": f"Amount {amt} in narrative doesn't match table total {total_from_table:.2f}",
                        "details": {"narrative_amount": amt, "table_total": total_from_table},
                    })
                    break

    # 6. Empty sections
    for section_name, text in content.items():
        stripped = text.strip()
        if not stripped or stripped in ("N/A", "TBD", "TODO"):
            flags.append({
                "type": "warning",
                "category": "empty_section",
                "message": f"Section '{section_name}' appears empty or placeholder",
                "details": {"section": section_name},
            })

    critical = sum(1 for f in flags if f["type"] == "critical")
    warning = sum(1 for f in flags if f["type"] == "warning")

    return {
        "flags": flags,
        "summary": {"total": len(flags), "critical": critical, "warning": warning},
    }
