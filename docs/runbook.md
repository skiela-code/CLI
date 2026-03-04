# Runbook

## Starting the Platform

```bash
# 1. Clone the repository
git clone <repo-url> && cd CLI

# 2. Copy env file
cp .env.example .env
# Edit .env if you have real Pipedrive/Claude API keys

# 3. Start everything
docker compose up --build

# 4. Access the web UI
open http://localhost:8000
```

## First-Time Setup

On first start, the app will:
1. Run Alembic migrations (create all tables + FTS triggers)
2. Run seed data (admin user, sample templates, blocks, pricing)

## Dev Login

1. Go to http://localhost:8000
2. You'll be redirected to the dev login page
3. Use `admin@clm.local` (pre-seeded) or any email
4. Click "Sign In (Dev Mode)"

## Quickstart Flow (No External APIs Needed)

1. **Login** as `admin@clm.local`
2. **Deals** → Click "Search" → See mock Pipedrive deals → "Sync" one
3. **Templates** → See pre-seeded templates (Contract, NDA, Commercial Offer, Purchase Annex)
4. **Template Builder** → Click "Builder" on any template → Map placeholders → Save
5. **Content Blocks** → See pre-seeded blocks (SLA, GDPR, Implementation)
6. **Pricing** → See pre-seeded pricing table → Add/remove line items
7. **Generate Document** → Select deal + template + pricing → Click "Generate"
8. **Documents** → View generated document → See red flags → Download DOCX
9. **Approvals** → Send document for approval → Switch to reviewer and approve
10. **Search** → Search for "Acme" or "SLA"

## Database Operations

```bash
# Connect to database
docker compose exec db psql -U clm -d clm_db

# Run migrations manually
docker compose exec app alembic upgrade head

# Create a new migration
docker compose exec app alembic revision --autogenerate -m "description"

# Reset database (WARNING: destroys all data)
docker compose down -v
docker compose up --build
```

## Running Tests

```bash
# Inside container
docker compose exec app pytest -v

# Locally (requires python-docx installed)
pip install -r requirements.txt
pytest -v
```

## Logs

```bash
# All logs
docker compose logs -f

# App logs only
docker compose logs -f app

# Database logs
docker compose logs -f db
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Port 8000 in use | Change `APP_PORT` in .env and docker-compose.yml |
| Database connection refused | Wait for health check; check `docker compose logs db` |
| Migration fails | Check if database URL matches in alembic.ini and .env |
| Template upload fails | Check `UPLOAD_PATH` directory permissions |
| OIDC login fails | Verify OIDC settings; use dev login for testing |
| Claude API errors | Set `ANTHROPIC_MOCK_MODE=true` for testing without API key |
