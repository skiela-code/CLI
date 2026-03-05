"""Tests for encryption service."""

import os
import pytest


@pytest.fixture(autouse=True)
def reset_fernet():
    """Reset the cached fernet instance between tests."""
    import app.core.encryption
    app.core.encryption._fernet_instance = None
    yield
    app.core.encryption._fernet_instance = None


def test_encrypt_decrypt_roundtrip(monkeypatch):
    monkeypatch.setenv("APP_SECRET_KEY", "test-secret-key-for-encryption")
    # Clear the settings cache
    from app.core.config import get_settings
    get_settings.cache_clear()

    from app.core.encryption import encrypt_value, decrypt_value

    plaintext = "my-secret-api-key-12345"
    ciphertext = encrypt_value(plaintext)
    assert ciphertext != plaintext
    assert decrypt_value(ciphertext) == plaintext


def test_different_plaintexts_produce_different_ciphertexts(monkeypatch):
    monkeypatch.setenv("APP_SECRET_KEY", "test-secret-key-for-encryption")
    from app.core.config import get_settings
    get_settings.cache_clear()

    from app.core.encryption import encrypt_value

    ct1 = encrypt_value("value-a")
    ct2 = encrypt_value("value-b")
    assert ct1 != ct2


def test_encrypt_empty_string(monkeypatch):
    monkeypatch.setenv("APP_SECRET_KEY", "test-secret-key-for-encryption")
    from app.core.config import get_settings
    get_settings.cache_clear()

    from app.core.encryption import encrypt_value, decrypt_value

    ciphertext = encrypt_value("")
    assert decrypt_value(ciphertext) == ""
