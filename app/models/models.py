"""SQLAlchemy async models for CLM-lite."""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SAEnum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------
import enum


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    MANAGER = "manager"
    USER = "user"


class DocType(str, enum.Enum):
    CONTRACT = "contract"
    NDA = "nda"
    PURCHASE_ANNEX = "purchase_annex"
    COMMERCIAL_OFFER = "commercial_offer"


class DocStatus(str, enum.Enum):
    DRAFT = "draft"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    SENT = "sent"


class ApprovalStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class PlaceholderSource(str, enum.Enum):
    DEAL_FIELD = "deal_field"
    CLIENT_FIELD = "client_field"
    CONTENT_BLOCK = "content_block"
    AI_GENERATED = "ai_generated"
    MANUAL = "manual"


class NotificationType(str, enum.Enum):
    APPROVAL_REQUEST = "approval_request"
    APPROVAL_DECISION = "approval_decision"
    DOCUMENT_READY = "document_ready"


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(SAEnum(UserRole), default=UserRole.USER)
    oidc_sub: Mapped[Optional[str]] = mapped_column(String(255), unique=True, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    documents = relationship("Document", back_populates="created_by_user", foreign_keys="Document.created_by")
    notifications = relationship("Notification", back_populates="recipient_user")


class Deal(Base):
    __tablename__ = "deals"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pipedrive_id: Mapped[Optional[int]] = mapped_column(Integer, unique=True, nullable=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    org_name: Mapped[Optional[str]] = mapped_column(String(500))
    contact_name: Mapped[Optional[str]] = mapped_column(String(500))
    contact_email: Mapped[Optional[str]] = mapped_column(String(255))
    value: Mapped[Optional[float]] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(10), default="EUR")
    status: Mapped[str] = mapped_column(String(50), default="open")
    custom_fields: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    synced_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    # FTS
    search_vector: Mapped[Optional[str]] = mapped_column(TSVECTOR)

    __table_args__ = (
        Index("ix_deals_search", "search_vector", postgresql_using="gin"),
    )


class Template(Base):
    __tablename__ = "templates"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    doc_type: Mapped[DocType] = mapped_column(SAEnum(DocType), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    file_path: Mapped[Optional[str]] = mapped_column(String(1000))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    # FTS
    search_vector: Mapped[Optional[str]] = mapped_column(TSVECTOR)

    placeholders = relationship("TemplatePlaceholder", back_populates="template", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_templates_search", "search_vector", postgresql_using="gin"),
    )


class TemplatePlaceholder(Base):
    __tablename__ = "template_placeholders"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    template_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("templates.id", ondelete="CASCADE"))
    token: Mapped[str] = mapped_column(String(255), nullable=False)  # e.g. {{CLIENT_NAME}}
    label: Mapped[Optional[str]] = mapped_column(String(255))
    source: Mapped[PlaceholderSource] = mapped_column(SAEnum(PlaceholderSource), default=PlaceholderSource.MANUAL)
    source_field: Mapped[Optional[str]] = mapped_column(String(255))  # e.g. "deal.org_name"
    content_block_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("content_blocks.id"), nullable=True)
    ai_prompt: Mapped[Optional[str]] = mapped_column(Text)  # prompt if AI_GENERATED
    default_value: Mapped[Optional[str]] = mapped_column(Text)

    template = relationship("Template", back_populates="placeholders")


class ContentBlock(Base):
    __tablename__ = "content_blocks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[Optional[str]] = mapped_column(String(255))
    tags: Mapped[Optional[list]] = mapped_column(JSONB, default=list)
    is_approved: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    # FTS
    search_vector: Mapped[Optional[str]] = mapped_column(TSVECTOR)

    __table_args__ = (
        Index("ix_content_blocks_search", "search_vector", postgresql_using="gin"),
    )


class PricingTable(Base):
    __tablename__ = "pricing_tables"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    deal_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("deals.id"), nullable=True)
    tier: Mapped[str] = mapped_column(String(50), default="standard")  # good/better/best
    currency: Mapped[str] = mapped_column(String(10), default="EUR")
    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    line_items = relationship("PricingLineItem", back_populates="pricing_table", cascade="all, delete-orphan")


class PricingLineItem(Base):
    __tablename__ = "pricing_line_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pricing_table_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("pricing_tables.id", ondelete="CASCADE"))
    description: Mapped[str] = mapped_column(String(1000), nullable=False)
    quantity: Mapped[float] = mapped_column(Float, default=1)
    unit_price: Mapped[float] = mapped_column(Float, nullable=False)
    discount_pct: Mapped[float] = mapped_column(Float, default=0)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    pricing_table = relationship("PricingTable", back_populates="line_items")

    @property
    def total(self) -> float:
        return self.quantity * self.unit_price * (1 - self.discount_pct / 100)


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    doc_type: Mapped[DocType] = mapped_column(SAEnum(DocType), nullable=False)
    status: Mapped[DocStatus] = mapped_column(SAEnum(DocStatus), default=DocStatus.DRAFT)
    deal_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("deals.id"), nullable=True)
    template_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("templates.id"), nullable=True)
    pricing_table_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("pricing_tables.id"), nullable=True)
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id"), nullable=True)
    red_flags: Mapped[Optional[dict]] = mapped_column(JSONB)
    metadata_: Mapped[Optional[dict]] = mapped_column("metadata", JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    # FTS
    search_vector: Mapped[Optional[str]] = mapped_column(TSVECTOR)

    created_by_user = relationship("User", back_populates="documents", foreign_keys=[created_by])
    versions = relationship("DocumentVersion", back_populates="document", cascade="all, delete-orphan")
    approvals = relationship("Approval", back_populates="document", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_documents_search", "search_vector", postgresql_using="gin"),
    )


class DocumentVersion(Base):
    __tablename__ = "document_versions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"))
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    file_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    generated_content: Mapped[Optional[dict]] = mapped_column(JSONB)  # sections, AI outputs
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    document = relationship("Document", back_populates="versions")


class Approval(Base):
    __tablename__ = "approvals"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"))
    version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("document_versions.id"))
    approver_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    status: Mapped[ApprovalStatus] = mapped_column(SAEnum(ApprovalStatus), default=ApprovalStatus.PENDING)
    comment: Mapped[Optional[str]] = mapped_column(Text)
    decided_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    document = relationship("Document", back_populates="approvals")
    approver = relationship("User")


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    recipient_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    type: Mapped[NotificationType] = mapped_column(SAEnum(NotificationType))
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    body: Mapped[Optional[str]] = mapped_column(Text)
    link: Mapped[Optional[str]] = mapped_column(String(1000))
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    recipient_user = relationship("User", back_populates="notifications")


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(255), nullable=False)
    entity_type: Mapped[Optional[str]] = mapped_column(String(100))
    entity_id: Mapped[Optional[str]] = mapped_column(String(255))
    details: Mapped[Optional[dict]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
