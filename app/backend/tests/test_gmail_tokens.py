import pytest
from cryptography.fernet import Fernet
from fastapi import HTTPException

from gmail_config import GMAIL_COMPOSE_SCOPE, gmail_scopes
from gmail_tokens import decrypt_token, encrypt_token


def test_encrypts_and_decrypts_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GMAIL_TOKEN_ENCRYPTION_KEY", Fernet.generate_key().decode())

    encrypted = encrypt_token("refresh-token")

    assert encrypted != "refresh-token"
    assert decrypt_token(encrypted) == "refresh-token"


def test_rejects_missing_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GMAIL_TOKEN_ENCRYPTION_KEY", raising=False)

    with pytest.raises(HTTPException, match="not configured"):
        encrypt_token("token")


def test_rejects_invalid_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GMAIL_TOKEN_ENCRYPTION_KEY", "invalid")

    with pytest.raises(HTTPException, match="not configured"):
        encrypt_token("token")


def test_rejects_invalid_ciphertext(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GMAIL_TOKEN_ENCRYPTION_KEY", Fernet.generate_key().decode())

    with pytest.raises(ValueError, match="Stored Gmail authorization is invalid"):
        decrypt_token("invalid")


def test_defaults_to_compose_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GMAIL_OAUTH_SCOPES", raising=False)

    assert gmail_scopes() == (GMAIL_COMPOSE_SCOPE,)
