"""Customer profile routes: list and detail views."""

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select, func, distinct, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.models import (
    ContractMetadata, Deal, DocType, Document,
    DocumentService, ServiceCatalog, User,
)
from app.services.renewal_service import compute_renewal

router = APIRouter(prefix="/customers", tags=["customers"])


@router.get("/")
async def customer_list(
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all customers (grouped by org_name from deals + documents)."""
    # Get unique company names from both deals and documents
    deal_companies = await db.execute(
        select(Deal.org_name).where(Deal.org_name.isnot(None)).distinct()
    )
    doc_companies = await db.execute(
        select(Document.company_name)
        .where(Document.company_name.isnot(None), Document.source == "uploaded")
        .distinct()
    )

    all_names = set()
    for row in deal_companies.all():
        if row[0]:
            all_names.add(row[0])
    for row in doc_companies.all():
        if row[0]:
            all_names.add(row[0])

    # For each company, get document count and latest contract info
    customers = []
    for name in sorted(all_names):
        doc_count = await db.execute(
            select(func.count(Document.id))
            .where(Document.company_name == name, Document.source == "uploaded")
        )
        count = doc_count.scalar() or 0

        # Check for active contracts
        contract_q = await db.execute(
            select(Document, ContractMetadata)
            .join(ContractMetadata, ContractMetadata.document_id == Document.id, isouter=True)
            .where(Document.company_name == name, Document.source == "uploaded",
                   Document.doc_type == DocType.CONTRACT)
            .order_by(Document.created_at.desc())
            .limit(1)
        )
        contract_row = contract_q.first()

        renewal_status = None
        next_renewal = None
        if contract_row and contract_row[1]:
            cm = contract_row[1]
            r = compute_renewal(
                cm.effective_date, cm.initial_term_months,
                cm.renewal_term_months, cm.auto_renew, cm.notice_period_days,
            )
            renewal_status = r.get("renewal_status")
            next_renewal = r.get("next_renewal_date")

        customers.append({
            "name": name,
            "doc_count": count,
            "renewal_status": renewal_status,
            "next_renewal": next_renewal,
        })

    from app.main import templates as tmpl
    return tmpl.TemplateResponse("pages/customers.html", {
        "request": request, "user": user, "customers": customers,
    })


@router.get("/{org_name:path}")
async def customer_profile(
    org_name: str,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Customer profile page."""
    tab = request.query_params.get("tab", "overview")

    # Get deals for this company
    deals_result = await db.execute(
        select(Deal).where(Deal.org_name == org_name).order_by(Deal.created_at.desc())
    )
    deals = deals_result.scalars().all()

    # Get all documents (both uploaded and generated)
    docs_result = await db.execute(
        select(Document)
        .where(Document.company_name == org_name)
        .order_by(Document.created_at.desc())
    )
    all_docs = docs_result.scalars().all()

    # Also get generated documents linked via deals
    deal_ids = [d.id for d in deals]
    if deal_ids:
        gen_docs_result = await db.execute(
            select(Document)
            .where(Document.deal_id.in_(deal_ids), Document.source == "generated")
            .order_by(Document.created_at.desc())
        )
        gen_docs = gen_docs_result.scalars().all()
        existing_ids = {d.id for d in all_docs}
        for gd in gen_docs:
            if gd.id not in existing_ids:
                all_docs.append(gd)

    # Current contract and renewal
    current_contract = None
    renewal_info = None
    contract_metadata = None

    for doc in all_docs:
        if doc.doc_type == DocType.CONTRACT or (isinstance(doc.doc_type, str) and doc.doc_type == "contract"):
            cm_result = await db.execute(
                select(ContractMetadata).where(ContractMetadata.document_id == doc.id)
            )
            cm = cm_result.scalar_one_or_none()
            if cm and cm.effective_date:
                r = compute_renewal(
                    cm.effective_date, cm.initial_term_months,
                    cm.renewal_term_months, cm.auto_renew, cm.notice_period_days,
                )
                if r.get("renewal_status") != "expired":
                    current_contract = doc
                    renewal_info = r
                    contract_metadata = cm
                    break

    # Services across all documents
    services = []
    service_ids = set()
    for doc in all_docs:
        svc_result = await db.execute(
            select(DocumentService, ServiceCatalog)
            .join(ServiceCatalog, DocumentService.service_id == ServiceCatalog.id)
            .where(DocumentService.document_id == doc.id)
        )
        for ds, sc in svc_result.all():
            if sc.id not in service_ids:
                services.append(sc)
                service_ids.add(sc.id)

    # Risk alerts
    alerts = []
    if renewal_info:
        if renewal_info.get("renewal_status") == "expired":
            alerts.append({"level": "danger", "message": "Contract expired"})
        elif renewal_info.get("renewal_status") == "expiring_soon":
            alerts.append({"level": "warning", "message": f"Renewal approaching: {renewal_info.get('current_term_end')}"})
        if renewal_info.get("cancel_by_date"):
            from datetime import date as dt_date
            if renewal_info["cancel_by_date"] <= dt_date.today():
                alerts.append({"level": "danger", "message": "Notice period has passed"})

    # Check for missing signed copies
    has_signed = False
    for doc in all_docs:
        if doc.doc_type == DocType.CONTRACT:
            cm_result = await db.execute(
                select(ContractMetadata).where(ContractMetadata.document_id == doc.id)
            )
            cm = cm_result.scalar_one_or_none()
            if cm and cm.signed_date:
                has_signed = True
                break
    if current_contract and not has_signed:
        alerts.append({"level": "info", "message": "No signed contract copy on file"})

    # Group documents by type
    docs_by_type = {}
    for doc in all_docs:
        dt = doc.doc_type if isinstance(doc.doc_type, str) else doc.doc_type.value
        docs_by_type.setdefault(dt, []).append(doc)

    from app.main import templates as tmpl
    return tmpl.TemplateResponse("pages/customer_profile.html", {
        "request": request, "user": user, "org_name": org_name,
        "deals": deals, "all_docs": all_docs, "docs_by_type": docs_by_type,
        "current_contract": current_contract, "renewal_info": renewal_info,
        "contract_metadata": contract_metadata,
        "services": services, "alerts": alerts, "tab": tab,
    })
