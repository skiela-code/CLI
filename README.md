# CLM-lite + Proposal Generator

A lightweight Contract Lifecycle Management platform with AI-powered document generation, integrated with Pipedrive CRM.

## Features

- **Template Management** — Upload DOCX templates with `{{PLACEHOLDER}}` tokens, map to deal fields / content blocks / AI
- **Document Generation** — Async document generation with AI narrative sections (Claude / OpenRouter / Mock)
- **LLM Router** — Primary/fallback provider routing with circuit breaker and metrics
- **Setup Wizard** — Browser-based onboarding for first-time setup (admin account, AI provider, integrations)
- **Pricing Engine** — Structured pricing tables with Good/Better/Best tiers
- **Pipedrive Integration** — Sync deals, attach generated documents
- **Approval Workflow** — Single-approver per document version with notifications
- **Red Flags Checker** — Missing placeholders, forbidden terms, pricing mismatches
- **Global Search** — Postgres Full-Text Search across all entities
- **SSO / RBAC** — OIDC authentication with role-based access control

## Quick Start

### Prerequisites

- Docker & Docker Compose
- (Optional) Pipedrive API token
- (Optional) Anthropic API key

### 1. Clone and configure

```bash
git clone <repo-url>
cd CLI
cp .env.example .env
```

Edit `.env` if you have API keys. **The app works fully in mock mode** without any external API keys.

### 2. Start the platform

```bash
docker compose up --build
```

This will:
- Start PostgreSQL 16
- Run database migrations
- Seed sample data (admin user, templates, blocks, pricing)
- Start the FastAPI app on port 8000

### 3. Complete the Setup Wizard

Open **http://localhost:8000** — you'll be redirected to the setup wizard:
1. Create an admin account
2. Configure AI provider (or use mock mode)
3. Configure integrations (Pipedrive mock/real)
4. Launch the app

### 4. Login

- **Setup wizard admin**: Use the account you created during setup
- **Dev login** (default): Use `admin@clm.local` — pre-seeded admin account
- **OIDC**: Configure `OIDC_*` env vars for Azure AD / Google

### 5. Test the full flow

1. **Deals** → Search → Sync a Pipedrive deal (mock data available)
2. **Templates** → View pre-seeded templates → Open Builder → Map placeholders
3. **Pricing** → View sample pricing table → Add line items
4. **Generate** → Select deal + template + pricing → Generate document
5. **Documents** → View result → Check red flags → Download DOCX
6. **Approvals** → Send for approval → Approve/Reject
7. **Search** → Search "Acme" or "SLA"

### 6. Run tests

```bash
docker compose exec app pytest -v
```

## Architecture

- **Backend**: Python 3.12 + FastAPI (fully async)
- **Database**: PostgreSQL 16 + SQLAlchemy async + asyncpg
- **UI**: Jinja2 + HTMX + Bootstrap 5 (server-rendered, zero build step)
- **AI**: LLM Router with Claude / OpenRouter / Mock providers, circuit breaker, fallback
- **CRM**: Pipedrive REST API via httpx (with mock mode)
- **Auth**: OIDC (authlib) + dev login fallback
- **Jobs**: asyncio.create_task (in-process, no Redis needed)

See `/docs` for detailed documentation:
- [Overview](docs/overview.md)
- [Architecture](docs/architecture.md)
- [Data Model](docs/data-model.md)
- [API Reference](docs/api.md)
- [Security](docs/security.md)
- [Runbook](docs/runbook.md)
- [Onboarding Guide](docs/ONBOARDING.md)
- [Configuration Reference](docs/CONFIGURATION.md)
- ADRs: [Background Jobs](docs/adr/001-background-job-approach.md) | [Auth](docs/adr/002-auth-approach.md) | [UI](docs/adr/003-ui-approach.md)

## Project Structure

```
CLI/
├── app/
│   ├── api/                    # Route handlers
│   │   ├── auth_routes.py      # OIDC + dev login
│   │   ├── deals_routes.py     # Pipedrive deals
│   │   ├── templates_routes.py # Template CRUD + builder
│   │   ├── blocks_routes.py    # Content blocks CRUD
│   │   ├── pricing_routes.py   # Pricing tables + line items
│   │   ├── documents_routes.py # Document generation + download
│   │   ├── approvals_routes.py # Approval inbox + decisions
│   │   ├── search_routes.py    # Global FTS search
│   │   └── notifications_routes.py
│   ├── core/
│   │   ├── config.py           # Pydantic settings
│   │   ├── database.py         # Async SQLAlchemy engine
│   │   ├── auth.py             # Auth dependencies + RBAC
│   │   └── logging.py          # Structured logging
│   ├── integrations/
│   │   ├── pipedrive.py        # Async Pipedrive client + mock
│   │   ├── base_provider.py    # Abstract AI provider interface
│   │   ├── claude_ai.py        # Anthropic Claude provider
│   │   ├── openrouter_provider.py  # OpenRouter provider
│   │   ├── mock_provider.py    # Mock AI provider
│   │   └── llm_router.py       # LLM routing + fallback + circuit breaker
│   ├── models/
│   │   └── models.py           # SQLAlchemy async models
│   ├── services/
│   │   ├── doc_generator.py    # Async document generation
│   │   ├── template_engine.py  # DOCX placeholder engine
│   │   ├── red_flags.py        # Pre-send validation
│   │   ├── search.py           # Postgres FTS
│   │   └── notifications.py    # Multi-channel notifications
│   ├── templates/              # Jinja2 HTML templates
│   │   ├── layouts/base.html
│   │   ├── pages/              # All page templates
│   │   └── components/         # Reusable components
│   ├── static/                 # CSS + JS
│   ├── main.py                 # FastAPI app entry
│   └── seed_data.py            # Database seeding
├── migrations/                 # Alembic migrations
├── docs/                       # Documentation
│   ├── adr/                    # Architecture Decision Records
│   └── *.md
├── tests/                      # Pytest tests
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── .env.example
└── README.md
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DEV_LOGIN_ENABLED` | `true` | Enable dev login (disable in prod!) |
| `PIPEDRIVE_MOCK_MODE` | `true` | Use mock Pipedrive data |
| `ANTHROPIC_MOCK_MODE` | `true` | Use mock AI responses |
| `DATABASE_URL` | (see .env.example) | PostgreSQL async connection string |
| `APP_SECRET_KEY` | `change-me` | Session signing key |

See `.env.example` for all configuration options.
