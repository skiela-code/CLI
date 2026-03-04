# CLM-lite + Proposal Generator — Overview

## What Is This?

CLM-lite is a lightweight Contract Lifecycle Management platform combined with an AI-powered Proposal Generator. It integrates with **Pipedrive CRM** and uses **Claude AI** (Anthropic) to generate professional business documents.

## Core Capabilities

1. **Template Management** — Upload DOCX templates with `{{PLACEHOLDER}}` tokens; map them to deal fields, content blocks, or AI-generated sections.

2. **Document Generation** — Select a deal, template, and pricing table; the system resolves all placeholders (including AI-generated narrative sections) and produces a downloadable DOCX.

3. **Pricing Engine** — Build structured pricing tables with line items, quantities, discounts, and Good/Better/Best tiers.

4. **Pipedrive Integration** — Search and sync deals from Pipedrive CRM. Attach generated documents back to deals.

5. **Approval Workflow** — Single-approver flow per document version, with in-app notifications and optional email.

6. **Red Flags Checker** — Pre-send validation: missing placeholders, forbidden terms, pricing mismatches, empty sections, stale dates.

7. **Global Search** — Postgres Full-Text Search across documents, templates, content blocks, and deals with filters.

8. **SSO / RBAC** — OIDC authentication (Azure AD / Google compatible) with role-based access control (Admin, Manager, User).

## Document Types

| Type | Generation | Placeholders |
|------|-----------|-------------|
| Contract | Template-driven | Deal/client fields + content blocks |
| NDA | Template-driven | Deal/client fields |
| Purchase Annex | Template-driven | Pricing table + delivery/payment terms |
| Commercial Offer | Content blocks + structured pricing + AI narrative | AI sections + pricing table |

## Tech Stack

- **Backend**: Python 3.12 + FastAPI (fully async)
- **Database**: PostgreSQL 16 + SQLAlchemy async + asyncpg
- **UI**: Jinja2 + HTMX + Bootstrap 5
- **AI**: Claude API (Anthropic) via httpx
- **CRM**: Pipedrive REST API via httpx
- **Auth**: OIDC (authlib) + dev login fallback
- **Container**: Docker Compose
