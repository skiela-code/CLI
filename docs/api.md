# API Reference

All routes serve HTML (Jinja2 templates). This is a server-rendered application, not a JSON API.

## Authentication

| Method | Path | Description |
|--------|------|-------------|
| GET | `/auth/login` | Redirect to OIDC or dev login |
| GET | `/auth/dev-login` | Dev login form (when DEV_LOGIN_ENABLED=true) |
| POST | `/auth/dev-login` | Process dev login |
| GET | `/auth/callback` | OIDC callback |
| GET | `/auth/logout` | Clear session |

## Dashboard

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Dashboard with quick actions |

## Deals

| Method | Path | Description |
|--------|------|-------------|
| GET | `/deals?search=&source=` | List deals (Pipedrive + local) |
| POST | `/deals/sync/{pipedrive_id}` | Sync a Pipedrive deal to local DB |

## Templates

| Method | Path | Description |
|--------|------|-------------|
| GET | `/templates` | List all templates |
| GET | `/templates/upload` | Upload form |
| POST | `/templates/upload` | Upload DOCX + extract placeholders |
| GET | `/templates/{id}` | Template detail + placeholders |
| GET | `/templates/{id}/builder` | Placeholder mapping UI |
| POST | `/templates/{id}/builder` | Save placeholder mappings |

## Content Blocks

| Method | Path | Description |
|--------|------|-------------|
| GET | `/blocks?category=` | List blocks with category filter |
| GET | `/blocks/new` | New block form |
| POST | `/blocks/new` | Create block |
| GET | `/blocks/{id}/edit` | Edit block form |
| POST | `/blocks/{id}/edit` | Update block |
| POST | `/blocks/{id}/delete` | Delete block |

## Pricing

| Method | Path | Description |
|--------|------|-------------|
| GET | `/pricing` | List pricing tables |
| GET | `/pricing/new` | New table form |
| POST | `/pricing/new` | Create pricing table |
| GET | `/pricing/{id}` | Table detail + line items |
| POST | `/pricing/{id}/item` | Add line item |
| POST | `/pricing/{id}/item/{item_id}/delete` | Delete line item |

## Documents

| Method | Path | Description |
|--------|------|-------------|
| GET | `/documents` | List all documents |
| GET | `/documents/generate` | Generation form |
| POST | `/documents/generate` | Start document generation |
| GET | `/documents/{id}` | Document detail (versions, red flags, approvals) |
| GET | `/documents/{id}/download/{version_id}` | Download DOCX |
| POST | `/documents/{id}/approve/request` | Send for approval |
| POST | `/documents/{id}/attach-pipedrive` | Attach to Pipedrive deal |

## Approvals

| Method | Path | Description |
|--------|------|-------------|
| GET | `/approvals` | Approver inbox |
| POST | `/approvals/{id}/decide` | Approve or reject |

## Search

| Method | Path | Description |
|--------|------|-------------|
| GET | `/search?q=&doc_type=&status=&category=` | Global FTS search |

## Notifications

| Method | Path | Description |
|--------|------|-------------|
| GET | `/notifications` | Notification inbox |
| POST | `/notifications/{id}/read` | Mark as read |
