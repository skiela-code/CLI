"""Tests for the red flags checker service."""

from app.services.red_flags import check_red_flags


def test_missing_placeholders():
    content = {"body": "Hello {{CLIENT_NAME}}, this is a {{MISSING_FIELD}} test."}
    result = check_red_flags(content)
    assert result["summary"]["total"] >= 1
    placeholder_flags = [f for f in result["flags"] if f["category"] == "missing_placeholder"]
    assert len(placeholder_flags) == 1
    assert "{{CLIENT_NAME}}" in placeholder_flags[0]["details"]


def test_forbidden_terms():
    content = {"body": "We offer guaranteed results with unlimited liability coverage."}
    result = check_red_flags(content)
    forbidden_flags = [f for f in result["flags"] if f["category"] == "forbidden_term"]
    assert len(forbidden_flags) >= 2


def test_clean_document():
    content = {"body": "This is a clean document without any issues or placeholders."}
    result = check_red_flags(content)
    critical_count = result["summary"]["critical"]
    assert critical_count == 0


def test_empty_section():
    content = {"introduction": "Good intro", "terms": "TBD"}
    result = check_red_flags(content)
    empty_flags = [f for f in result["flags"] if f["category"] == "empty_section"]
    assert len(empty_flags) == 1
    assert empty_flags[0]["details"]["section"] == "terms"


def test_pricing_mismatch():
    content = {"body": "The total investment is 50,000 EUR for the complete package."}
    pricing = [
        {"description": "License", "quantity": 1, "unit_price": 75000, "discount_pct": 0},
    ]
    result = check_red_flags(content, pricing=pricing)
    mismatch_flags = [f for f in result["flags"] if f["category"] == "pricing_mismatch"]
    assert len(mismatch_flags) >= 1
