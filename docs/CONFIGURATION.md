# Configuration Reference

## Environment Variables

All settings can be configured via `.env` file or environment variables. Database-stored settings (configured via Setup Wizard or Admin Settings) take precedence over environment variables.

### App Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `APP_ENV` | `development` | Environment mode (`development` / `production`) |
| `APP_SECRET_KEY` | `change-me` | Secret key for session encryption and settings encryption |
| `APP_HOST` | `0.0.0.0` | Host to bind to |
| `APP_PORT` | `8000` | Port to listen on |
| `DEV_LOGIN_ENABLED` | `true` | Enable dev login bypass |

### Database

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql+asyncpg://clm:clm_secret@db:5432/clm_db` | Async database URL |
| `DATABASE_URL_SYNC` | `postgresql://clm:clm_secret@db:5432/clm_db` | Sync database URL (for Alembic) |

### AI Providers

| Variable | Default | Description |
|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | `` | Anthropic API key |
| `ANTHROPIC_MODEL` | `claude-sonnet-4-20250514` | Claude model to use |
| `ANTHROPIC_MOCK_MODE` | `true` | Use mock AI responses |
| `OPENROUTER_API_KEY` | `` | OpenRouter API key |
| `OPENROUTER_MODEL` | `` | OpenRouter model identifier |
| `OPENROUTER_BASE_URL` | `https://openrouter.ai/api/v1/chat/completions` | OpenRouter API URL |

### Pipedrive

| Variable | Default | Description |
|----------|---------|-------------|
| `PIPEDRIVE_API_TOKEN` | `` | Pipedrive API token |
| `PIPEDRIVE_MOCK_MODE` | `true` | Use mock Pipedrive data |

## Settings Precedence

1. **Database settings** (set via Setup Wizard or Admin Settings) — highest priority
2. **Environment variables** (from `.env` file) — fallback
3. **Code defaults** — lowest priority

## Secret Handling

- All database-stored settings are encrypted using Fernet symmetric encryption
- The encryption key is derived from `APP_SECRET_KEY` using HKDF (SHA-256)
- API keys are masked in the Admin Settings UI (showing only last 4 characters)
- Changing `APP_SECRET_KEY` will invalidate all stored encrypted settings

## AI Provider Routing

The LLM Router supports:
- **Primary provider**: First choice for AI generation
- **Fallback provider**: Used when primary fails with server errors (429, 500, 502, 503, 504)
- **Circuit breaker**: After 5 consecutive failures, provider is disabled for 60 seconds
- Auth errors (401, 403) do NOT trigger fallback (fail immediately)
