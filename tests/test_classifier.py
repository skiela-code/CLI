"""Tests for the document classifier rule-based engine."""

from app.services.document_classifier import classify_by_rules


def test_contract_by_filename():
    """Filename containing 'contract' should classify as contract."""
    doc_type, confidence = classify_by_rules("Service_Contract_2025.pdf", "")
    assert doc_type == "contract"
    assert confidence >= 0.4


def test_nda_by_filename():
    """Filename containing 'nda' should classify as NDA."""
    doc_type, confidence = classify_by_rules("NDA_Acme.docx", "")
    assert doc_type == "nda"
    assert confidence >= 0.4


def test_contract_by_keywords():
    """Text with contract keywords should classify as contract."""
    text = (
        "This agreement is entered into between Party A and Party B. "
        "The terms and conditions set forth herein shall be governed by "
        "applicable law. The effective date of this agreement is January 1, 2025. "
        "The term of this agreement shall be 12 months."
    )
    doc_type, confidence = classify_by_rules("document.pdf", text)
    assert doc_type == "contract"
    assert confidence > 0.2


def test_nda_by_keywords():
    """Text with NDA keywords should classify as NDA."""
    text = (
        "This non-disclosure agreement protects confidential information "
        "shared between the disclosing party and the receiving party. "
        "All confidentiality obligations shall survive termination."
    )
    doc_type, confidence = classify_by_rules("document.pdf", text)
    assert doc_type == "nda"
    assert confidence > 0.2


def test_commercial_offer_by_filename():
    """Filename containing 'proposal' should classify as commercial offer."""
    doc_type, confidence = classify_by_rules("Proposal_2025.pdf", "")
    assert doc_type == "commercial_offer"
    assert confidence >= 0.4


def test_unknown_document():
    """Document with no matching signals should return 'other'."""
    doc_type, confidence = classify_by_rules(
        "random_file.pdf",
        "The quick brown fox jumps over the lazy dog."
    )
    assert doc_type == "other"
    assert confidence < 0.5


def test_combined_filename_and_keywords():
    """Both filename and keyword signals should increase confidence."""
    text = (
        "This service agreement outlines the terms and conditions "
        "between the parties. The effective date is March 1, 2025."
    )
    doc_type, confidence = classify_by_rules("Master_Agreement.pdf", text)
    assert doc_type == "contract"
    assert confidence >= 0.5


def test_annex_by_filename():
    """Filename containing 'annex' should classify as purchase_annex."""
    doc_type, confidence = classify_by_rules("Pricing_Annex_v2.docx", "")
    assert doc_type == "purchase_annex"
    assert confidence >= 0.4
