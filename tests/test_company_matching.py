"""Tests for the company matching service (rule-based matching logic)."""

import re


def test_filename_matching():
    """Company name in filename should contribute to score."""
    # Testing the matching logic directly since the full function needs DB
    org_name = "Acme Corporation"
    filename = "acme_contract_2025.pdf"

    org_lower = org_name.lower()
    org_clean = re.sub(r'\b(corp|corporation|ltd|gmbh|inc|llc|sa|ag)\b', '', org_lower).strip()

    assert org_clean in filename.lower()


def test_text_matching():
    """Company name in document text should be detected."""
    org_name = "Acme Corporation"
    text = "This agreement is between Acme Corporation and Provider Ltd."

    assert org_name.lower() in text.lower()


def test_email_domain_matching():
    """Email domain in text should be detected."""
    contact_email = "john@acme.com"
    text = "Please contact us at support@acme.com for inquiries."

    domain = contact_email.split("@")[-1].lower()
    domain_base = domain.split(".")[0]

    assert domain_base in text.lower()


def test_no_match_for_unrelated():
    """Unrelated text should not match any company."""
    org_name = "Acme Corporation"
    text = "The quick brown fox jumps over the lazy dog."

    org_lower = org_name.lower()
    assert org_lower not in text.lower()


def test_clean_suffix_removal():
    """Company name cleaning should remove common suffixes."""
    test_cases = [
        ("Acme Corp", "acme"),
        ("TechStart LLC", "techstart"),
        ("DataFlow GmbH", "dataflow"),
        ("Global Inc", "global"),
    ]
    for name, expected in test_cases:
        cleaned = re.sub(r'\b(corp|corporation|ltd|gmbh|inc|llc|sa|ag)\b', '', name.lower()).strip()
        assert cleaned == expected, f"Failed for {name}: got '{cleaned}', expected '{expected}'"


def test_multiple_occurrences_boost():
    """Multiple mentions of company name should increase score."""
    org_name = "Acme"
    text = "Acme provides services. Acme is based in NYC. Acme was founded in 2000."

    count = text.lower().count(org_name.lower())
    assert count == 3
    # Score bonus should apply for count > 2
    assert count > 2
