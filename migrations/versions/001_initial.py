"""Initial schema.

Revision ID: 001
Revises:
Create Date: 2024-01-01
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB, TSVECTOR

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- users ---
    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), unique=True, nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("role", sa.String(20), server_default="user"),
        sa.Column("oidc_sub", sa.String(255), unique=True, nullable=True),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )

    # --- deals ---
    op.create_table(
        "deals",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("pipedrive_id", sa.Integer, unique=True, nullable=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("org_name", sa.String(500)),
        sa.Column("contact_name", sa.String(500)),
        sa.Column("contact_email", sa.String(255)),
        sa.Column("value", sa.Float),
        sa.Column("currency", sa.String(10), server_default="EUR"),
        sa.Column("status", sa.String(50), server_default="open"),
        sa.Column("custom_fields", JSONB, server_default="{}"),
        sa.Column("synced_at", sa.DateTime, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("search_vector", TSVECTOR),
    )
    op.create_index("ix_deals_search", "deals", ["search_vector"], postgresql_using="gin")

    # --- templates ---
    op.create_table(
        "templates",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(500), nullable=False),
        sa.Column("doc_type", sa.String(30), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("file_path", sa.String(1000)),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("search_vector", TSVECTOR),
    )
    op.create_index("ix_templates_search", "templates", ["search_vector"], postgresql_using="gin")

    # --- content_blocks ---
    op.create_table(
        "content_blocks",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("category", sa.String(255)),
        sa.Column("tags", JSONB, server_default="[]"),
        sa.Column("is_approved", sa.Boolean, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("search_vector", TSVECTOR),
    )
    op.create_index("ix_content_blocks_search", "content_blocks", ["search_vector"], postgresql_using="gin")

    # --- template_placeholders ---
    op.create_table(
        "template_placeholders",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("template_id", UUID(as_uuid=True), sa.ForeignKey("templates.id", ondelete="CASCADE")),
        sa.Column("token", sa.String(255), nullable=False),
        sa.Column("label", sa.String(255)),
        sa.Column("source", sa.String(30), server_default="manual"),
        sa.Column("source_field", sa.String(255)),
        sa.Column("content_block_id", UUID(as_uuid=True), sa.ForeignKey("content_blocks.id"), nullable=True),
        sa.Column("ai_prompt", sa.Text),
        sa.Column("default_value", sa.Text),
    )

    # --- pricing_tables ---
    op.create_table(
        "pricing_tables",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(500), nullable=False),
        sa.Column("deal_id", UUID(as_uuid=True), sa.ForeignKey("deals.id"), nullable=True),
        sa.Column("tier", sa.String(50), server_default="standard"),
        sa.Column("currency", sa.String(10), server_default="EUR"),
        sa.Column("notes", sa.Text),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )

    # --- pricing_line_items ---
    op.create_table(
        "pricing_line_items",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("pricing_table_id", UUID(as_uuid=True), sa.ForeignKey("pricing_tables.id", ondelete="CASCADE")),
        sa.Column("description", sa.String(1000), nullable=False),
        sa.Column("quantity", sa.Float, server_default="1"),
        sa.Column("unit_price", sa.Float, nullable=False),
        sa.Column("discount_pct", sa.Float, server_default="0"),
        sa.Column("sort_order", sa.Integer, server_default="0"),
    )

    # --- documents ---
    op.create_table(
        "documents",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("doc_type", sa.String(30), nullable=False),
        sa.Column("status", sa.String(30), server_default="draft"),
        sa.Column("deal_id", UUID(as_uuid=True), sa.ForeignKey("deals.id"), nullable=True),
        sa.Column("template_id", UUID(as_uuid=True), sa.ForeignKey("templates.id"), nullable=True),
        sa.Column("pricing_table_id", UUID(as_uuid=True), sa.ForeignKey("pricing_tables.id"), nullable=True),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("red_flags", JSONB),
        sa.Column("metadata", JSONB, server_default="{}"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("search_vector", TSVECTOR),
    )
    op.create_index("ix_documents_search", "documents", ["search_vector"], postgresql_using="gin")

    # --- document_versions ---
    op.create_table(
        "document_versions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("document_id", UUID(as_uuid=True), sa.ForeignKey("documents.id", ondelete="CASCADE")),
        sa.Column("version_number", sa.Integer, nullable=False),
        sa.Column("file_path", sa.String(1000), nullable=False),
        sa.Column("generated_content", JSONB),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )

    # --- approvals ---
    op.create_table(
        "approvals",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("document_id", UUID(as_uuid=True), sa.ForeignKey("documents.id", ondelete="CASCADE")),
        sa.Column("version_id", UUID(as_uuid=True), sa.ForeignKey("document_versions.id")),
        sa.Column("approver_id", UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("status", sa.String(20), server_default="pending"),
        sa.Column("comment", sa.Text),
        sa.Column("decided_at", sa.DateTime, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )

    # --- notifications ---
    op.create_table(
        "notifications",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("recipient_id", UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("type", sa.String(30)),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("body", sa.Text),
        sa.Column("link", sa.String(1000)),
        sa.Column("is_read", sa.Boolean, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )

    # --- audit_log ---
    op.create_table(
        "audit_log",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("action", sa.String(255), nullable=False),
        sa.Column("entity_type", sa.String(100)),
        sa.Column("entity_id", sa.String(255)),
        sa.Column("details", JSONB),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )

    # --- FTS triggers ---
    op.execute("""
        CREATE OR REPLACE FUNCTION update_deals_search() RETURNS trigger AS $$
        BEGIN
            NEW.search_vector := to_tsvector('english',
                coalesce(NEW.title, '') || ' ' ||
                coalesce(NEW.org_name, '') || ' ' ||
                coalesce(NEW.contact_name, '')
            );
            RETURN NEW;
        END $$ LANGUAGE plpgsql;

        CREATE TRIGGER deals_search_update BEFORE INSERT OR UPDATE ON deals
        FOR EACH ROW EXECUTE FUNCTION update_deals_search();
    """)

    op.execute("""
        CREATE OR REPLACE FUNCTION update_templates_search() RETURNS trigger AS $$
        BEGIN
            NEW.search_vector := to_tsvector('english',
                coalesce(NEW.name, '') || ' ' ||
                coalesce(NEW.description, '')
            );
            RETURN NEW;
        END $$ LANGUAGE plpgsql;

        CREATE TRIGGER templates_search_update BEFORE INSERT OR UPDATE ON templates
        FOR EACH ROW EXECUTE FUNCTION update_templates_search();
    """)

    op.execute("""
        CREATE OR REPLACE FUNCTION update_content_blocks_search() RETURNS trigger AS $$
        BEGIN
            NEW.search_vector := to_tsvector('english',
                coalesce(NEW.title, '') || ' ' ||
                coalesce(NEW.body, '') || ' ' ||
                coalesce(NEW.category, '')
            );
            RETURN NEW;
        END $$ LANGUAGE plpgsql;

        CREATE TRIGGER content_blocks_search_update BEFORE INSERT OR UPDATE ON content_blocks
        FOR EACH ROW EXECUTE FUNCTION update_content_blocks_search();
    """)

    op.execute("""
        CREATE OR REPLACE FUNCTION update_documents_search() RETURNS trigger AS $$
        BEGIN
            NEW.search_vector := to_tsvector('english',
                coalesce(NEW.title, '')
            );
            RETURN NEW;
        END $$ LANGUAGE plpgsql;

        CREATE TRIGGER documents_search_update BEFORE INSERT OR UPDATE ON documents
        FOR EACH ROW EXECUTE FUNCTION update_documents_search();
    """)


def downgrade() -> None:
    for t in [
        "audit_log", "notifications", "approvals", "document_versions",
        "documents", "pricing_line_items", "pricing_tables",
        "template_placeholders", "content_blocks", "templates", "deals", "users",
    ]:
        op.drop_table(t)
