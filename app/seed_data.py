"""Seed data: creates admin user, sample template, sample block, sample pricing table."""

import asyncio
import os
import uuid

from sqlalchemy import select

from app.core.database import async_session_factory, engine
from app.core.logging import log
from app.models.models import (
    ContentBlock, Deal, PricingLineItem, PricingTable,
    Template, TemplatePlaceholder, PlaceholderSource, User, UserRole,
)
from app.services.template_engine import create_sample_template


async def seed():
    async with async_session_factory() as db:
        # If setup wizard has already run, don't seed
        from app.services.settings_service import is_setup_complete
        if await is_setup_complete(db):
            log.info("seed_skipped", reason="setup already complete")
            return

        # Check if already seeded
        result = await db.execute(select(User).limit(1))
        if result.scalar_one_or_none():
            log.info("seed_skipped", reason="data already exists")
            return

        log.info("seeding_database")

        # 1. Admin user
        admin = User(
            id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
            email="admin@clm.local",
            name="Admin User",
            role=UserRole.ADMIN,
        )
        db.add(admin)

        # Second user (for approval testing)
        reviewer = User(
            id=uuid.UUID("00000000-0000-0000-0000-000000000002"),
            email="reviewer@clm.local",
            name="Reviewer User",
            role=UserRole.MANAGER,
        )
        db.add(reviewer)

        # 2. Sample content blocks
        block1 = ContentBlock(
            id=uuid.UUID("00000000-0000-0000-0000-000000000010"),
            title="Standard SLA Terms",
            body=(
                "The Provider guarantees 99.9% uptime for all production services. "
                "Planned maintenance windows will be communicated at least 48 hours in advance. "
                "In the event of service disruption, the Provider will initiate incident response "
                "within 15 minutes and provide status updates every 30 minutes until resolution."
            ),
            category="Legal",
            tags=["SLA", "uptime", "support"],
            is_approved=True,
        )
        db.add(block1)

        block2 = ContentBlock(
            id=uuid.UUID("00000000-0000-0000-0000-000000000011"),
            title="Data Protection Clause",
            body=(
                "Both parties shall comply with applicable data protection legislation including GDPR. "
                "Personal data shared under this agreement shall be processed only for the purposes "
                "outlined herein. Each party shall implement appropriate technical and organizational "
                "measures to ensure a level of security appropriate to the risk."
            ),
            category="Legal",
            tags=["GDPR", "privacy", "compliance"],
            is_approved=True,
        )
        db.add(block2)

        block3 = ContentBlock(
            id=uuid.UUID("00000000-0000-0000-0000-000000000012"),
            title="Implementation Methodology",
            body=(
                "Our implementation follows a proven 4-phase methodology: "
                "1) Discovery & Planning — requirements gathering and project plan creation. "
                "2) Configuration & Development — platform setup and customization. "
                "3) Testing & Training — UAT, data migration validation, and user training. "
                "4) Go-Live & Support — production deployment with 30-day hypercare period."
            ),
            category="Technical",
            tags=["implementation", "methodology", "project"],
            is_approved=True,
        )
        db.add(block3)

        # 3. Sample deal (synced from mock Pipedrive)
        deal = Deal(
            id=uuid.UUID("00000000-0000-0000-0000-000000000020"),
            pipedrive_id=1001,
            title="Acme Corp — Enterprise License",
            org_name="Acme Corporation",
            contact_name="John Smith",
            contact_email="john.smith@acme.com",
            value=125000,
            currency="EUR",
            status="open",
            custom_fields={"industry": "Technology", "region": "EMEA"},
        )
        db.add(deal)

        # 4. Sample pricing table
        pt = PricingTable(
            id=uuid.UUID("00000000-0000-0000-0000-000000000030"),
            name="Acme Enterprise License — Best",
            deal_id=deal.id,
            tier="best",
            currency="EUR",
        )
        db.add(pt)
        await db.flush()

        items = [
            PricingLineItem(pricing_table_id=pt.id, description="Platform License (Annual)", quantity=1, unit_price=75000, discount_pct=0, sort_order=0),
            PricingLineItem(pricing_table_id=pt.id, description="Implementation Services", quantity=1, unit_price=30000, discount_pct=10, sort_order=1),
            PricingLineItem(pricing_table_id=pt.id, description="Training (5 sessions)", quantity=5, unit_price=2000, discount_pct=0, sort_order=2),
            PricingLineItem(pricing_table_id=pt.id, description="Premium Support (Annual)", quantity=1, unit_price=15000, discount_pct=5, sort_order=3),
        ]
        for item in items:
            db.add(item)

        # 5. Sample templates (generate DOCX files)
        for doc_type in ["contract", "nda", "commercial_offer", "purchase_annex"]:
            file_path = create_sample_template(doc_type)
            tmpl = Template(
                name=f"Sample {doc_type.replace('_', ' ').title()}",
                doc_type=doc_type,
                description=f"Auto-generated sample {doc_type} template with standard placeholders.",
                file_path=file_path,
            )
            db.add(tmpl)
            await db.flush()

            # Extract and create placeholder records
            from app.services.template_engine import extract_placeholders
            tokens = extract_placeholders(file_path)
            for token in tokens:
                ph = TemplatePlaceholder(
                    template_id=tmpl.id,
                    token=token,
                    label=token.strip("{}").replace("_", " ").title(),
                    source=PlaceholderSource.MANUAL,
                )
                # Auto-map some common ones
                token_clean = token.strip("{}")
                if token_clean == "CLIENT_NAME":
                    ph.source = PlaceholderSource.CLIENT_FIELD
                    ph.source_field = "deal.org_name"
                elif token_clean == "DEAL_TITLE":
                    ph.source = PlaceholderSource.DEAL_FIELD
                    ph.source_field = "deal.title"
                elif token_clean == "DATE":
                    ph.source = PlaceholderSource.MANUAL
                    ph.default_value = "2026-03-04"
                elif token_clean.startswith("AI_"):
                    ph.source = PlaceholderSource.AI_GENERATED
                    ph.ai_prompt = f"Generate a professional {token_clean.replace('AI_', '').replace('_', ' ').lower()} section."

                db.add(ph)

        await db.commit()
        log.info("seed_complete")


if __name__ == "__main__":
    asyncio.run(seed())
