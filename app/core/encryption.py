"""Fernet encryption for app settings using HKDF key derivation."""

import base64

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from app.core.config import get_settings

_fernet_instance = None


def get_fernet() -> Fernet:
    global _fernet_instance
    if _fernet_instance is None:
        settings = get_settings()
        hkdf = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b"clm-lite-settings-v2",
            info=b"settings-encryption",
        )
        derived = hkdf.derive(settings.app_secret_key.encode())
        key = base64.urlsafe_b64encode(derived)
        _fernet_instance = Fernet(key)
    return _fernet_instance


def encrypt_value(plaintext: str) -> str:
    return get_fernet().encrypt(plaintext.encode()).decode()


def decrypt_value(ciphertext: str) -> str:
    return get_fernet().decrypt(ciphertext.encode()).decode()
