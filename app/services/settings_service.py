"""DB-backed settings CRUD with encryption and env-var fallback."""

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.encryption import encrypt_value, decrypt_value
from app.models.models import AppSetting

SECRET_KEYS = {"anthropic_api_key", "openrouter_api_key", "pipedrive_api_token"}


async def get_setting(db: AsyncSession, key: str) -> Optional[str]:
    """Get a setting value. DB overrides env vars."""
    result = await db.execute(select(AppSetting).where(AppSetting.key == key))
    row = result.scalar_one_or_none()
    if row and row.value_encrypted:
        return decrypt_value(row.value_encrypted)
    # Fallback to env var
    env_settings = get_settings()
    return getattr(env_settings, key, None)


async def set_setting(db: AsyncSession, key: str, value: str) -> None:
    """Upsert a setting."""
    result = await db.execute(select(AppSetting).where(AppSetting.key == key))
    row = result.scalar_one_or_none()
    encrypted = encrypt_value(value)
    if row:
        row.value_encrypted = encrypted
    else:
        db.add(AppSetting(key=key, value_encrypted=encrypted))


async def get_all_settings(db: AsyncSession) -> dict[str, str]:
    """Get all DB settings as a dict (decrypted)."""
    result = await db.execute(select(AppSetting))
    settings = {}
    for row in result.scalars():
        if row.value_encrypted:
            settings[row.key] = decrypt_value(row.value_encrypted)
    return settings


async def is_setup_complete(db: AsyncSession) -> bool:
    """Check if initial setup has been completed."""
    val = await get_setting(db, "setup_complete")
    return val == "true"


def mask_key(value: str) -> str:
    """Return masked version showing only last 4 chars."""
    if not value or len(value) <= 4:
        return "****"
    return "*" * (len(value) - 4) + value[-4:]
