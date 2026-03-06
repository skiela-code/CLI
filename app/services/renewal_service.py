"""Renewal computation from contract metadata."""

from datetime import date, timedelta
from typing import Any, Optional

from dateutil.relativedelta import relativedelta


def compute_renewal(
    effective_date: Optional[date],
    initial_term_months: Optional[int],
    renewal_term_months: Optional[int] = None,
    auto_renew: bool = True,
    notice_period_days: Optional[int] = None,
) -> dict[str, Any]:
    """Compute renewal dates from contract metadata.

    Returns dict with: current_term_start, current_term_end,
    next_renewal_date, cancel_by_date, renewal_status.
    """
    if not effective_date or not initial_term_months:
        return {
            "current_term_start": None,
            "current_term_end": None,
            "next_renewal_date": None,
            "cancel_by_date": None,
            "renewal_status": "unknown",
        }

    today = date.today()
    term_months = renewal_term_months or initial_term_months

    # Calculate initial term end
    term_end = effective_date + relativedelta(months=initial_term_months)
    current_start = effective_date

    # Roll forward if auto-renew and past initial term
    if auto_renew and term_end <= today:
        while term_end <= today:
            current_start = term_end
            term_end = term_end + relativedelta(months=term_months)

    # Compute cancel_by date
    cancel_by = None
    if notice_period_days and term_end:
        cancel_by = term_end - timedelta(days=notice_period_days)

    # Determine status
    if term_end < today:
        status = "expired"
    elif term_end <= today + timedelta(days=30):
        status = "expiring_soon"
    elif term_end <= today + timedelta(days=90):
        status = "approaching"
    else:
        status = "active"

    return {
        "current_term_start": current_start,
        "current_term_end": term_end,
        "next_renewal_date": term_end if auto_renew else None,
        "cancel_by_date": cancel_by,
        "renewal_status": status,
    }
