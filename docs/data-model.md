# Data Model

## Entity Relationship Diagram

```
┌──────────┐     ┌──────────────┐     ┌────────────────┐
│   User   │     │    Deal      │     │   Template     │
├──────────┤     ├──────────────┤     ├────────────────┤
│ id (PK)  │     │ id (PK)      │     │ id (PK)        │
│ email    │     │ pipedrive_id │     │ name           │
│ name     │     │ title        │     │ doc_type       │
│ role     │     │ org_name     │     │ description    │
│ oidc_sub │     │ contact_name │     │ file_path      │
│ is_active│     │ contact_email│     │ is_active      │
│ created_at│    │ value        │     │ search_vector  │
└────┬─────┘     │ currency     │     └───────┬────────┘
     │           │ custom_fields│             │ 1:N
     │           │ search_vector│     ┌───────┴──────────────┐
     │           └──────┬───────┘     │ TemplatePlaceholder  │
     │                  │             ├──────────────────────┤
     │                  │             │ id (PK)              │
     │                  │             │ template_id (FK)     │
     │                  │             │ token                │
     │                  │             │ source               │
     │                  │             │ source_field         │
     │           ┌──────┴───────┐     │ content_block_id(FK) │
     │           │              │     │ ai_prompt            │
     │    ┌──────┴──────┐       │     │ default_value        │
     │    │ PricingTable│       │     └──────────────────────┘
     │    ├─────────────┤       │
     │    │ id (PK)     │       │     ┌────────────────┐
     │    │ name        │       │     │ ContentBlock   │
     │    │ deal_id(FK) │       │     ├────────────────┤
     │    │ tier        │       │     │ id (PK)        │
     │    │ currency    │       │     │ title          │
     │    └──────┬──────┘       │     │ body           │
     │           │ 1:N          │     │ category       │
     │    ┌──────┴──────────┐   │     │ tags (JSONB)   │
     │    │ PricingLineItem │   │     │ is_approved    │
     │    ├─────────────────┤   │     │ search_vector  │
     │    │ id (PK)         │   │     └────────────────┘
     │    │ pricing_table_id│   │
     │    │ description     │   │
     │    │ quantity        │   │
     │    │ unit_price      │   │
     │    │ discount_pct    │   │
     │    └─────────────────┘   │
     │                          │
     │    ┌─────────────────────┴──────┐
     │    │        Document            │
     │    ├────────────────────────────┤
     │    │ id (PK)                    │
     │    │ title                      │
     │    │ doc_type                   │
     │    │ status                     │
     ├────│ created_by (FK -> User)    │
     │    │ deal_id (FK)               │
     │    │ template_id (FK)           │
     │    │ pricing_table_id (FK)      │
     │    │ red_flags (JSONB)          │
     │    │ metadata (JSONB)           │
     │    │ search_vector              │
     │    └────────┬───────────────────┘
     │             │ 1:N
     │    ┌────────┴────────┐    ┌────────────────┐
     │    │ DocumentVersion │    │    Approval     │
     │    ├─────────────────┤    ├────────────────┤
     │    │ id (PK)         │    │ id (PK)        │
     │    │ document_id(FK) │    │ document_id(FK)│
     │    │ version_number  │    │ version_id(FK) │
     │    │ file_path       │◄───│ approver_id(FK)│
     │    │ generated_content│   │ status         │
     │    └─────────────────┘    │ comment        │
     │                           │ decided_at     │
     │                           └────────────────┘
     │
     │    ┌────────────────┐    ┌────────────────┐
     │    │ Notification   │    │   AuditLog     │
     │    ├────────────────┤    ├────────────────┤
     └────│ recipient_id   │    │ id (PK)        │
          │ type           │    │ user_id (FK)   │
          │ title          │    │ action         │
          │ body           │    │ entity_type    │
          │ link           │    │ entity_id      │
          │ is_read        │    │ details (JSONB)│
          └────────────────┘    └────────────────┘
```

## Enums

| Enum | Values |
|------|--------|
| UserRole | admin, manager, user |
| DocType | contract, nda, purchase_annex, commercial_offer |
| DocStatus | draft, pending_approval, approved, rejected, sent |
| ApprovalStatus | pending, approved, rejected |
| PlaceholderSource | deal_field, client_field, content_block, ai_generated, manual |
| NotificationType | approval_request, approval_decision, document_ready |

## Full-Text Search

PostgreSQL GIN indexes + triggers on:
- `deals.search_vector` (title, org_name, contact_name)
- `templates.search_vector` (name, description)
- `content_blocks.search_vector` (title, body, category)
- `documents.search_vector` (title)

Triggers auto-update search vectors on INSERT/UPDATE.
