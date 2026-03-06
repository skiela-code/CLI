"""Tests for the contract metadata extraction rule-based engine."""

from app.services.metadata_extraction import extract_by_rules


def test_extract_effective_date():
    """Should extract effective date from contract text."""
    text = "This agreement is effective as of 15 January 2025 and shall remain in force."
    result = extract_by_rules(text)
    assert "effective_date" in result
    assert "2025" in result["effective_date"]["value"]


def test_extract_iso_date():
    """Should extract ISO format effective date."""
    text = "Effective 2025-03-01. The parties agree to the following terms."
    result = extract_by_rules(text)
    assert "effective_date" in result
    assert "2025-03-01" in result["effective_date"]["value"]


def test_extract_term_months():
    """Should extract initial term in months."""
    text = "The initial term of 24 months begins from the effective date."
    result = extract_by_rules(text)
    assert "initial_term_months" in result
    assert result["initial_term_months"]["value"] == 24


def test_extract_term_years():
    """Should convert years to months."""
    text = "This contract has an initial period of 2 years term effective immediately."
    result = extract_by_rules(text)
    assert "initial_term_months" in result
    assert result["initial_term_months"]["value"] == 24


def test_extract_notice_period():
    """Should extract notice period in days."""
    text = "Either party may terminate with 90 days prior written notice before the renewal date."
    result = extract_by_rules(text)
    assert "notice_period_days" in result
    assert result["notice_period_days"]["value"] == 90


def test_extract_auto_renew():
    """Should detect auto-renewal clause."""
    text = "This agreement shall automatically renew for successive 12-month periods."
    result = extract_by_rules(text)
    assert "auto_renew" in result
    assert result["auto_renew"]["value"] is True


def test_no_metadata_in_unrelated_text():
    """Should return empty dict for unrelated text."""
    text = "The quick brown fox jumps over the lazy dog. No contract terms here."
    result = extract_by_rules(text)
    assert "initial_term_months" not in result
    assert "notice_period_days" not in result


def test_snippets_included():
    """Each extracted field should include a source snippet."""
    text = "Notice period of 60 days is required for termination."
    result = extract_by_rules(text)
    if "notice_period_days" in result:
        assert "snippet" in result["notice_period_days"]
        assert len(result["notice_period_days"]["snippet"]) > 0
