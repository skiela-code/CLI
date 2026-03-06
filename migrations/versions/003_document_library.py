"""Document Library: add library fields, contract_metadata, services, relationships, import_jobs.

Revision ID: 003
Revises: 002
Create Date: 2026-03-05
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- import_jobs (must be created before documents FK) ---
    op.create_table(
        "import_jobs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("total_files", sa.Integer, server_default="0"),
        sa.Column("processed_files", sa.Integer, server_default="0"),
        sa.Column("status", sa.String(20), server_default="processing"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime, nullable=True),
    )

    # --- Add library columns to documents ---
    op.add_column("documents", sa.Column("source", sa.String(20), server_default="generated"))
    op.add_column("documents", sa.Column("file_path", sa.String(1000), nullable=True))
    op.add_column("documents", sa.Column("extracted_text", sa.Text, nullable=True))
    op.add_column("documents", sa.Column("company_name", sa.String(500), nullable=True))
    op.add_column("documents", sa.Column("company_match_confidence", sa.Float, nullable=True))
    op.add_column("documents", sa.Column("classification_confidence", sa.Float, nullable=True))
    op.add_column("documents", sa.Column("import_status", sa.String(20), nullable=True))
    op.add_column("documents", sa.Column("import_job_id", UUID(as_uuid=True),
                                         sa.ForeignKey("import_jobs.id"), nullable=True))
    op.create_index("ix_documents_company", "documents", ["company_name"])
    op.create_index("ix_documents_source", "documents", ["source"])

    # Add 'other' to doc_type enum
    op.execute("ALTER TYPE doctype ADD VALUE IF NOT EXISTS 'other'")

    # --- contract_metadata ---
    op.create_table(
        "contract_metadata",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("document_id", UUID(as_uuid=True),
                  sa.ForeignKey("documents.id", ondelete="CASCADE"), unique=True),
        sa.Column("effective_date", sa.Date, nullable=True),
        sa.Column("signed_date", sa.Date, nullable=True),
        sa.Column("initial_term_months", sa.Integer, nullable=True),
        sa.Column("renewal_term_months", sa.Integer, nullable=True),
        sa.Column("auto_renew", sa.Boolean, server_default=sa.text("true")),
        sa.Column("notice_period_days", sa.Integer, nullable=True),
        sa.Column("pricing_summary", sa.Text, nullable=True),
        sa.Column("extraction_confidence", JSONB, nullable=True),
        sa.Column("extraction_snippets", JSONB, nullable=True),
        sa.Column("metadata_status", sa.String(20), server_default="imported"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )

    # --- service_catalog ---
    op.create_table(
        "service_catalog",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), unique=True, nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )

    # --- document_services ---
    op.create_table(
        "document_services",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("document_id", UUID(as_uuid=True),
                  sa.ForeignKey("documents.id", ondelete="CASCADE")),
        sa.Column("service_id", UUID(as_uuid=True),
                  sa.ForeignKey("service_catalog.id", ondelete="CASCADE")),
        sa.Column("confidence", sa.Float, nullable=True),
        sa.Column("source_snippet", sa.Text, nullable=True),
    )

    # --- document_relationships ---
    op.create_table(
        "document_relationships",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("parent_id", UUID(as_uuid=True),
                  sa.ForeignKey("documents.id", ondelete="CASCADE")),
        sa.Column("child_id", UUID(as_uuid=True),
                  sa.ForeignKey("documents.id", ondelete="CASCADE")),
        sa.Column("relationship_type", sa.String(50), server_default="annex"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )

    # Update FTS trigger for documents to include extracted_text and company_name
    op.execute("""
        CREATE OR REPLACE FUNCTION update_documents_search() RETURNS trigger AS $$
        BEGIN
            NEW.search_vector := to_tsvector('english',
                coalesce(NEW.title, '') || ' ' ||
                coalesce(NEW.company_name, '') || ' ' ||
                coalesce(left(NEW.extracted_text, 50000), '')
            );
            RETURN NEW;
        END $$ LANGUAGE plpgsql;
    """)


def downgrade() -> None:
    # Restore original FTS trigger
    op.execute("""
        CREATE OR REPLACE FUNCTION update_documents_search() RETURNS trigger AS $$
        BEGIN
            NEW.search_vector := to_tsvector('english',
                coalesce(NEW.title, '')
            );
            RETURN NEW;
        END $$ LANGUAGE plpgsql;
    """)

    op.drop_table("document_relationships")
    op.drop_table("document_services")
    op.drop_table("service_catalog")
    op.drop_table("contract_metadata")

    op.drop_index("ix_documents_source")
    op.drop_index("ix_documents_company")
    op.drop_column("documents", "import_job_id")
    op.drop_column("documents", "import_status")
    op.drop_column("documents", "classification_confidence")
    op.drop_column("documents", "company_match_confidence")
    op.drop_column("documents", "company_name")
    op.drop_column("documents", "extracted_text")
    op.drop_column("documents", "file_path")
    op.drop_column("documents", "source")

    op.drop_table("import_jobs")
