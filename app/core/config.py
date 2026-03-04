"""Application configuration via environment variables."""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # App
    app_env: str = "development"
    app_secret_key: str = "change-me"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    dev_login_enabled: bool = True

    # Database
    database_url: str = "postgresql+asyncpg://clm:clm_secret@db:5432/clm_db"
    database_url_sync: str = "postgresql://clm:clm_secret@db:5432/clm_db"

    # OIDC
    oidc_provider_url: str = "https://accounts.google.com"
    oidc_client_id: str = ""
    oidc_client_secret: str = ""
    oidc_redirect_uri: str = "http://localhost:8000/auth/callback"

    # Pipedrive
    pipedrive_api_token: str = ""
    pipedrive_base_url: str = "https://api.pipedrive.com/v1"
    pipedrive_mock_mode: bool = True

    # Anthropic
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-20250514"
    anthropic_mock_mode: bool = True

    # SMTP
    smtp_enabled: bool = False
    smtp_host: str = "smtp.example.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "clm@example.com"

    # Storage
    generated_docs_path: str = "/app/generated_docs"
    upload_path: str = "/app/uploads"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
