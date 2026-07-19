import asyncio
from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from urllib.parse import parse_qs, urlparse

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from auth import get_current_user
from gmail import get_gmail_oauth_service
from gmail_connections import (
    GmailConnectionRecord,
    GmailConnectionUpsert,
    OAuthStateRecord,
)
from gmail_oauth import (
    GOOGLE_TOKEN_URL,
    GmailOAuthError,
    GmailOAuthService,
    GoogleOAuthClientError,
)
from gmail_tokens import decrypt_token
from main import app

USER_ID = "00000000-0000-0000-0000-000000000001"
COMPOSE_SCOPE = "https://www.googleapis.com/auth/gmail.compose"
RAW_CODE = "authorization-code-secret"
RAW_STATE = "browser-state-secret"
RAW_REFRESH_TOKEN = "google-refresh-secret"
RAW_ACCESS_TOKEN = "google-access-secret"


class FakeStorage:
    def __init__(self) -> None:
        self.connection: GmailConnectionRecord | None = None
        self.state_records: dict[str, OAuthStateRecord] = {}
        self.invalidations: list[tuple[str, str]] = []
        self.upserts: list[GmailConnectionUpsert] = []
        self.metadata_updates: list[tuple[str, str | None, datetime | None]] = []

    def get_gmail_connection(self, user_id: str) -> GmailConnectionRecord | None:
        if self.connection and self.connection.user_id == user_id:
            return self.connection
        return None

    def create_gmail_oauth_state(
        self, user_id: str, state: str, expires_at: datetime
    ) -> OAuthStateRecord:
        record = OAuthStateRecord(
            state_hash=sha256(state.encode()).hexdigest(),
            user_id=user_id,
            expires_at=expires_at,
            created_at=datetime.now(timezone.utc),
        )
        self.state_records[record.state_hash] = record
        return record

    def consume_gmail_oauth_state(
        self, state: str, expected_user_id: str | None = None
    ) -> OAuthStateRecord | None:
        record = self.state_records.pop(sha256(state.encode()).hexdigest(), None)
        if record is None or record.expires_at <= datetime.now(timezone.utc):
            return None
        if expected_user_id is not None and record.user_id != expected_user_id:
            return None
        return record

    def upsert_gmail_connection(
        self, user_id: str, connection: GmailConnectionUpsert
    ) -> GmailConnectionRecord:
        self.upserts.append(connection)
        old = self.connection
        encrypted = connection.encrypted_refresh_token or (
            old.encrypted_refresh_token if old else None
        )
        assert encrypted is not None
        now = datetime.now(timezone.utc)
        self.connection = GmailConnectionRecord(
            id="connection-id",
            user_id=user_id,
            google_email=None,
            encrypted_refresh_token=encrypted,
            access_token=connection.access_token,
            access_token_expires_at=connection.access_token_expires_at,
            granted_scopes=connection.granted_scopes or (),
            revoked_at=None,
            created_at=old.created_at if old else now,
            updated_at=now,
        )
        return self.connection

    def update_gmail_access_token_metadata(
        self, user_id: str, access_token: str | None, expires_at: datetime | None
    ) -> GmailConnectionRecord | None:
        self.metadata_updates.append((user_id, access_token, expires_at))
        assert self.connection is not None
        self.connection = GmailConnectionRecord(
            **{
                **self.connection.__dict__,
                "access_token": access_token,
                "access_token_expires_at": expires_at,
            }
        )
        return self.connection

    def mark_gmail_connection_invalid(self, user_id: str, reason_code: str) -> None:
        self.invalidations.append((user_id, reason_code))


class FakeGoogleClient:
    def __init__(self, payload: dict[str, object] | None = None) -> None:
        self.payload = payload or token_payload()
        self.forms: list[dict[str, str]] = []
        self.error: GoogleOAuthClientError | None = None

    async def post_form(self, url: str, form: Mapping[str, str]) -> dict[str, object]:
        assert url == GOOGLE_TOKEN_URL
        self.forms.append(dict(form))
        if self.error:
            raise self.error
        return self.payload


def token_payload(**changes: object) -> dict[str, object]:
    return {
        "access_token": RAW_ACCESS_TOKEN,
        "refresh_token": RAW_REFRESH_TOKEN,
        "expires_in": 3600,
        "scope": COMPOSE_SCOPE,
        **changes,
    }


def connection(
    *,
    encrypted_refresh_token: str = "ciphertext",
    access_token: str | None = "old-access",
    access_token_expires_at: datetime | None = None,
    granted_scopes: tuple[str, ...] = (COMPOSE_SCOPE,),
    revoked_at: datetime | None = None,
) -> GmailConnectionRecord:
    now = datetime.now(timezone.utc)
    return GmailConnectionRecord(
        id="connection-id",
        user_id=USER_ID,
        google_email="person@example.com",
        encrypted_refresh_token=encrypted_refresh_token,
        access_token=access_token,
        access_token_expires_at=access_token_expires_at or now,
        granted_scopes=granted_scopes,
        revoked_at=revoked_at,
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def gmail_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GMAIL_OAUTH_CLIENT_ID", "client-id")
    monkeypatch.setenv("GMAIL_OAUTH_CLIENT_SECRET", "client-secret")
    monkeypatch.setenv("GMAIL_OAUTH_REDIRECT_URI", "https://app.example/callback")
    monkeypatch.setenv("GMAIL_TOKEN_ENCRYPTION_KEY", Fernet.generate_key().decode())


def test_status_when_gmail_is_not_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GMAIL_OAUTH_CLIENT_ID", raising=False)
    status = GmailOAuthService(FakeStorage()).get_connection_status(USER_ID)

    assert status.configured is False
    assert status.connected is False


def test_status_when_disconnected_and_connected(gmail_env: None) -> None:
    storage = FakeStorage()
    service = GmailOAuthService(storage, FakeGoogleClient())
    assert service.get_connection_status(USER_ID).connected is False

    storage.connection = connection()
    status = service.get_connection_status(USER_ID)
    assert status.connected is True
    assert status.google_email == "person@example.com"


def test_authorization_url_uses_required_google_parameters(gmail_env: None) -> None:
    storage = FakeStorage()
    url = GmailOAuthService(storage).build_authorization_url(USER_ID)
    query = parse_qs(urlparse(url).query)

    assert url.startswith("https://accounts.google.com/o/oauth2/v2/auth?")
    assert query["scope"] == [COMPOSE_SCOPE]
    assert query["access_type"] == ["offline"]
    assert query["prompt"] == ["consent"]
    assert query["include_granted_scopes"] == ["true"]
    raw_state = query["state"][0]
    assert len(raw_state) >= 43
    assert raw_state not in storage.state_records
    assert sha256(raw_state.encode()).hexdigest() in storage.state_records


def test_callback_consumes_state_exchanges_code_and_encrypts_refresh_token(
    gmail_env: None,
) -> None:
    storage = FakeStorage()
    google = FakeGoogleClient()
    service = GmailOAuthService(storage, google)
    url = service.build_authorization_url(USER_ID)
    state = parse_qs(urlparse(url).query)["state"][0]

    asyncio.run(service.handle_oauth_callback(RAW_CODE, state))

    assert google.forms[0]["code"] == RAW_CODE
    assert google.forms[0]["grant_type"] == "authorization_code"
    assert (
        decrypt_token(storage.upserts[0].encrypted_refresh_token or "")
        == RAW_REFRESH_TOKEN
    )
    assert not storage.state_records


@pytest.mark.parametrize("state", [None, "unknown-state"])
def test_callback_rejects_missing_or_invalid_state(
    gmail_env: None, state: str | None
) -> None:
    with pytest.raises(GmailOAuthError) as raised:
        asyncio.run(
            GmailOAuthService(FakeStorage()).handle_oauth_callback(RAW_CODE, state)
        )

    assert raised.value.code in {
        "gmail_invalid_oauth_state",
        "gmail_oauth_state_expired",
    }


def test_callback_rejects_expired_or_reused_state(gmail_env: None) -> None:
    storage = FakeStorage()
    storage.create_gmail_oauth_state(
        USER_ID, RAW_STATE, datetime.now(timezone.utc) - timedelta(seconds=1)
    )
    service = GmailOAuthService(storage, FakeGoogleClient())
    with pytest.raises(GmailOAuthError, match="gmail_oauth_state_expired"):
        asyncio.run(service.handle_oauth_callback(RAW_CODE, RAW_STATE))

    storage.create_gmail_oauth_state(
        USER_ID, RAW_STATE, datetime.now(timezone.utc) + timedelta(minutes=1)
    )
    asyncio.run(service.handle_oauth_callback(RAW_CODE, RAW_STATE))
    with pytest.raises(GmailOAuthError, match="gmail_oauth_state_expired"):
        asyncio.run(service.handle_oauth_callback(RAW_CODE, RAW_STATE))


def test_callback_rejects_missing_compose_scope(gmail_env: None) -> None:
    storage = FakeStorage()
    storage.create_gmail_oauth_state(
        USER_ID, RAW_STATE, datetime.now(timezone.utc) + timedelta(minutes=1)
    )
    service = GmailOAuthService(
        storage, FakeGoogleClient(token_payload(scope="openid"))
    )

    with pytest.raises(GmailOAuthError, match="gmail_scope_missing"):
        asyncio.run(service.handle_oauth_callback(RAW_CODE, RAW_STATE))


def test_callback_preserves_existing_refresh_token_when_google_omits_one(
    gmail_env: None,
) -> None:
    storage = FakeStorage()
    storage.connection = connection(encrypted_refresh_token="existing-encrypted")
    storage.create_gmail_oauth_state(
        USER_ID, RAW_STATE, datetime.now(timezone.utc) + timedelta(minutes=1)
    )
    service = GmailOAuthService(
        storage, FakeGoogleClient(token_payload(refresh_token=None))
    )

    asyncio.run(service.handle_oauth_callback(RAW_CODE, RAW_STATE))

    assert storage.connection.encrypted_refresh_token == "existing-encrypted"


def test_successful_refresh_preserves_old_refresh_token(gmail_env: None) -> None:
    storage = FakeStorage()
    storage.connection = connection(encrypted_refresh_token=encrypt_refresh(gmail_env))
    google = FakeGoogleClient(token_payload(refresh_token=None))

    credential = asyncio.run(
        GmailOAuthService(storage, google).refresh_access_token(USER_ID)
    )

    assert credential.access_token == RAW_ACCESS_TOKEN
    assert storage.metadata_updates[0][1] == RAW_ACCESS_TOKEN
    assert google.forms[0]["grant_type"] == "refresh_token"


def test_refresh_replacement_token_is_encrypted(gmail_env: None) -> None:
    storage = FakeStorage()
    storage.connection = connection(encrypted_refresh_token=encrypt_refresh(gmail_env))
    replacement = "replacement-refresh-secret"
    asyncio.run(
        GmailOAuthService(
            storage, FakeGoogleClient(token_payload(refresh_token=replacement))
        ).refresh_access_token(USER_ID)
    )

    assert (
        decrypt_token(storage.upserts[0].encrypted_refresh_token or "") == replacement
    )


def test_invalid_grant_marks_connection_invalid(gmail_env: None) -> None:
    storage = FakeStorage()
    storage.connection = connection(encrypted_refresh_token=encrypt_refresh(gmail_env))
    google = FakeGoogleClient()
    google.error = GoogleOAuthClientError("invalid_grant")

    with pytest.raises(GmailOAuthError, match="gmail_authorization_revoked"):
        asyncio.run(GmailOAuthService(storage, google).refresh_access_token(USER_ID))

    assert storage.invalidations == [(USER_ID, "invalid_grant")]


def test_denial_and_exchange_failure_are_safe(gmail_env: None) -> None:
    storage = FakeStorage()
    storage.create_gmail_oauth_state(
        USER_ID, RAW_STATE, datetime.now(timezone.utc) + timedelta(minutes=1)
    )
    with pytest.raises(GmailOAuthError, match="gmail_oauth_denied"):
        asyncio.run(GmailOAuthService(storage).handle_oauth_denial(RAW_STATE))

    storage.create_gmail_oauth_state(
        USER_ID, RAW_STATE, datetime.now(timezone.utc) + timedelta(minutes=1)
    )
    google = FakeGoogleClient()
    google.error = GoogleOAuthClientError()
    with pytest.raises(GmailOAuthError) as raised:
        asyncio.run(
            GmailOAuthService(storage, google).handle_oauth_callback(
                RAW_CODE, RAW_STATE
            )
        )
    assert raised.value.code == "gmail_token_exchange_failed"
    assert RAW_CODE not in str(raised.value)


def test_routes_exclude_credentials_and_ignore_callback_user_id(
    gmail_env: None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    storage = FakeStorage()
    storage.connection = connection(encrypted_refresh_token="encrypted-token")
    google = FakeGoogleClient()
    service = GmailOAuthService(storage, google)
    app.dependency_overrides[get_current_user] = lambda: {
        "user_id": USER_ID,
        "email": None,
    }
    app.dependency_overrides[get_gmail_oauth_service] = lambda: service
    client = TestClient(app)
    try:
        status = client.get("/api/v1/gmail/status")
        authorized = client.get("/api/v1/gmail/authorize")
        state = parse_qs(urlparse(authorized.json()["authorization_url"]).query)[
            "state"
        ][0]
        callback = client.get(
            f"/api/v1/gmail/callback?code={RAW_CODE}&state={state}&user_id=attacker"
        )
    finally:
        app.dependency_overrides.clear()

    assert status.status_code == 200
    assert {"access_token", "refresh_token", "encrypted_refresh_token"}.isdisjoint(
        status.json()
    )
    assert callback.status_code == 200
    assert storage.connection is not None and storage.connection.user_id == USER_ID
    assert RAW_CODE not in callback.text
    assert RAW_ACCESS_TOKEN not in callback.text
    assert RAW_REFRESH_TOKEN not in callback.text
    assert state not in callback.text
    assert RAW_CODE not in caplog.text
    assert RAW_ACCESS_TOKEN not in caplog.text
    assert RAW_REFRESH_TOKEN not in caplog.text
    assert state not in caplog.text
    assert len(google.forms) == 1
    assert all(
        form["grant_type"] in {"authorization_code", "refresh_token"}
        for form in google.forms
    )


def encrypt_refresh(gmail_env: None) -> str:
    del gmail_env
    from gmail_tokens import encrypt_token

    return encrypt_token(RAW_REFRESH_TOKEN)
