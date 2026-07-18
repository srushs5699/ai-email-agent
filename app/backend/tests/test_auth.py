from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Protocol

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey
from fastapi.testclient import TestClient

import auth
from main import app

client = TestClient(app)


class TokenFactory(Protocol):
    def __call__(
        self,
        claims: dict[str, object] | None = None,
        *,
        signing_key: RSAPrivateKey | None = None,
    ) -> str: ...


@pytest.fixture
def token_factory(monkeypatch: pytest.MonkeyPatch) -> TokenFactory:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    supabase_url = "https://example.supabase.co"
    monkeypatch.setenv("SUPABASE_URL", supabase_url)
    monkeypatch.setenv("SUPABASE_JWT_AUDIENCE", "authenticated")
    auth._get_jwks_client.cache_clear()
    monkeypatch.setattr(
        auth,
        "_get_jwks_client",
        lambda _url: SimpleNamespace(
            get_signing_key_from_jwt=lambda _token: SimpleNamespace(
                key=private_key.public_key()
            )
        ),
    )

    def create_token(
        claims: dict[str, object] | None = None,
        *,
        signing_key: RSAPrivateKey | None = None,
    ) -> str:
        token_claims: dict[str, object] = {
            "sub": "user-123",
            "email": "person@example.com",
            "aud": "authenticated",
            "iss": f"{supabase_url}/auth/v1",
            "exp": datetime.now(UTC) + timedelta(minutes=5),
        }
        if claims:
            token_claims.update(claims)

        return jwt.encode(
            token_claims,
            signing_key or private_key,
            algorithm="RS256",
            headers={"kid": "test-key"},
        )

    return create_token


def test_protected_endpoint_rejects_missing_access_token() -> None:
    response = client.get("/api/v1/auth/me")

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid or expired access token"}


@pytest.mark.parametrize(
    "authorization_header",
    ["Basic credentials", "Bearer", "Bearer ", "Token token"],
)
def test_protected_endpoint_rejects_malformed_authorization_header(
    authorization_header: str,
) -> None:
    response = client.get(
        "/api/v1/auth/me", headers={"Authorization": authorization_header}
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid or expired access token"}


def test_protected_endpoint_returns_verified_user(token_factory: TokenFactory) -> None:
    valid_access_token = token_factory()
    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {valid_access_token}"},
    )

    assert response.status_code == 200
    assert response.json() == {"user_id": "user-123", "email": "person@example.com"}
    assert valid_access_token not in response.text


def test_protected_endpoint_rejects_invalid_access_token(
    token_factory: TokenFactory,
) -> None:
    valid_access_token = token_factory()
    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {valid_access_token}invalid"},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid or expired access token"}


def test_protected_endpoint_rejects_token_with_invalid_signature(
    token_factory: TokenFactory,
) -> None:
    access_token = token_factory(
        signing_key=rsa.generate_private_key(public_exponent=65537, key_size=2048)
    )

    response = client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {access_token}"}
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid or expired access token"}


def test_protected_endpoint_rejects_expired_access_token(
    token_factory: TokenFactory,
) -> None:
    expired_access_token = token_factory(
        {"exp": datetime.now(UTC) - timedelta(minutes=1)}
    )

    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {expired_access_token}"},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid or expired access token"}


def test_protected_endpoint_rejects_token_with_wrong_issuer(
    token_factory: TokenFactory,
) -> None:
    access_token = token_factory({"iss": "https://wrong.supabase.co/auth/v1"})

    response = client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {access_token}"}
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid or expired access token"}


def test_protected_endpoint_rejects_token_with_wrong_audience(
    token_factory: TokenFactory,
) -> None:
    access_token = token_factory({"aud": "wrong-audience"})

    response = client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {access_token}"}
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid or expired access token"}


def test_protected_endpoint_rejects_token_without_subject(
    token_factory: TokenFactory,
) -> None:
    access_token = token_factory({"sub": None})

    response = client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {access_token}"}
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid or expired access token"}
