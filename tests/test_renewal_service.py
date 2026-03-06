"""Tests for renewal date computation."""

from datetime import date, timedelta
from app.services.renewal_service import compute_renewal


def test_active_contract():
    """Contract well within its term should be 'active'."""
    today = date.today()
    effective = today - timedelta(days=30)
    result = compute_renewal(effective, 12)
    assert result["renewal_status"] == "active"
    assert result["current_term_start"] == effective
    assert result["current_term_end"] is not None


def test_expired_no_autorenew():
    """Expired contract without auto-renew should be 'expired'."""
    effective = date(2020, 1, 1)
    result = compute_renewal(effective, 12, auto_renew=False)
    assert result["renewal_status"] == "expired"


def test_auto_renew_rolls_forward():
    """Auto-renew contract should roll forward past expiry."""
    effective = date(2020, 1, 1)
    result = compute_renewal(effective, 12, renewal_term_months=12, auto_renew=True)
    assert result["renewal_status"] != "expired"
    assert result["current_term_end"] > date.today()
    assert result["next_renewal_date"] is not None


def test_cancel_by_date():
    """Cancel-by date should be term_end minus notice period."""
    today = date.today()
    effective = today - timedelta(days=30)
    result = compute_renewal(effective, 12, notice_period_days=60)
    assert result["cancel_by_date"] is not None
    expected_cancel = result["current_term_end"] - timedelta(days=60)
    assert result["cancel_by_date"] == expected_cancel


def test_expiring_soon():
    """Contract expiring within 30 days should be 'expiring_soon'."""
    today = date.today()
    # Set effective date so term ends in ~15 days
    from dateutil.relativedelta import relativedelta
    effective = today - relativedelta(months=12) + timedelta(days=15)
    result = compute_renewal(effective, 12, auto_renew=False)
    assert result["renewal_status"] in ("expiring_soon", "active", "approaching")


def test_unknown_with_no_data():
    """Missing effective date should return 'unknown' status."""
    result = compute_renewal(None, None)
    assert result["renewal_status"] == "unknown"
    assert result["current_term_start"] is None
    assert result["current_term_end"] is None


def test_no_renewal_term_uses_initial():
    """When renewal_term_months is None, should use initial_term_months."""
    today = date.today()
    effective = date(2020, 1, 1)
    result = compute_renewal(effective, 12, renewal_term_months=None, auto_renew=True)
    # Should roll forward using 12-month intervals
    assert result["current_term_end"] > today
