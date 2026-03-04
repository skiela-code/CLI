# ADR-002: Authentication Approach

## Status
Accepted

## Context
The platform requires SSO (OIDC) for production use, but must also be testable locally without configuring an identity provider.

Options considered:
1. **OIDC only** — Requires IDP setup even for local dev
2. **OIDC + API key fallback** — Non-standard, confusing
3. **OIDC + dev login behind env flag** — Simple, secure, standard pattern

## Decision
**OIDC + dev login fallback (behind `DEV_LOGIN_ENABLED` env flag)**.

## Implementation

### OIDC Flow
- Uses `authlib` library for OpenID Connect
- Configured via `OIDC_PROVIDER_URL`, `OIDC_CLIENT_ID`, `OIDC_CLIENT_SECRET`
- Compatible with Azure AD, Google, Okta, Keycloak
- On first login, user record is created automatically
- User's `oidc_sub` claim stored for identity linking

### Dev Login
- Available only when `DEV_LOGIN_ENABLED=true`
- Simple email form — creates admin user if email not found
- **Must be disabled in production** (documented in security.md)

### RBAC
- Three roles: `admin`, `manager`, `user`
- Enforced via `require_role()` FastAPI dependency
- Roles assigned at user creation; admin can modify
- OIDC-to-role mapping can be extended via claims

### Session
- `SessionMiddleware` with signed cookies
- Stores only `user_id` in session
- All user lookups go through database

## Consequences
- Local testing works out of the box without IDP configuration
- Production deployments must set `DEV_LOGIN_ENABLED=false`
- Role mapping from OIDC claims is a V2 enhancement
