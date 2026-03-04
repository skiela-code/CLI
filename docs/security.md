# Security

## Authentication

### OIDC SSO
- Supports any OpenID Connect provider (Azure AD, Google, Okta)
- Configured via environment variables: `OIDC_PROVIDER_URL`, `OIDC_CLIENT_ID`, `OIDC_CLIENT_SECRET`
- Uses `authlib` for OIDC flow
- User is created on first login if not found

### Dev Login Fallback
- Enabled only when `DEV_LOGIN_ENABLED=true`
- **Must be disabled in production**
- Allows login with any email; creates user as admin if not found

## Authorization (RBAC)

| Role | Permissions |
|------|-------------|
| Admin | Full access to all features |
| Manager | Create/edit documents, approve, manage templates |
| User | Create documents, view own documents |

Role enforcement via `require_role()` dependency (currently applied at route level where needed).

## Session Management

- Server-side sessions via `starlette.middleware.sessions.SessionMiddleware`
- Session signed with `APP_SECRET_KEY` (change in production!)
- Session stores only `user_id`

## Audit Log

All significant actions are recorded in the `audit_log` table:
- Login/logout
- Document creation/generation
- Approval requests/decisions
- Deal syncs
- Template uploads
- Pipedrive attachments

## API Keys

External API keys are stored in environment variables, never in code:
- `ANTHROPIC_API_KEY`
- `PIPEDRIVE_API_TOKEN`
- `OIDC_CLIENT_SECRET`

## Input Validation

- Form inputs validated via FastAPI's `Form()` with required fields
- File uploads restricted to `.docx` via frontend validation
- SQL injection prevented by SQLAlchemy ORM (parameterized queries)
- XSS mitigated by Jinja2 auto-escaping

## Recommendations for Production

1. Set `DEV_LOGIN_ENABLED=false`
2. Use a strong random `APP_SECRET_KEY`
3. Enable HTTPS (TLS termination at load balancer)
4. Set `APP_ENV=production`
5. Restrict database access to app container only
6. Rotate API keys regularly
7. Enable SMTP for approval notifications
8. Add rate limiting (e.g., via reverse proxy)
