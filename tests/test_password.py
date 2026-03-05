"""Tests for password hashing."""

from app.core.password import hash_password, verify_password


def test_hash_verify_roundtrip():
    password = "my-secure-password"
    hashed = hash_password(password)
    assert verify_password(password, hashed)


def test_wrong_password_fails():
    hashed = hash_password("correct-password")
    assert not verify_password("wrong-password", hashed)


def test_different_passwords_produce_different_hashes():
    h1 = hash_password("password1")
    h2 = hash_password("password2")
    assert h1 != h2


def test_same_password_produces_different_hashes():
    """Salt should make each hash unique."""
    h1 = hash_password("same-password")
    h2 = hash_password("same-password")
    assert h1 != h2


def test_verify_invalid_hash():
    assert not verify_password("test", "invalid-hash-format")
    assert not verify_password("test", "")
    assert not verify_password("test", "abc:def")  # invalid hex
