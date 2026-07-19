"""Backend-only Gmail OAuth and token-refresh service."""

import os
import secrets
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Protocol
from urllib.parse import urlencode

import httpx

from gmail_config import GMAIL_COMPOSE_SCOPE, required_gmail_config
from gmail_connections import (
    GmailConnectionRecord,
    GmailConnectionUpsert,
    OAuthStateRecord,
)
from gmail_tokens import decrypt_token, encrypt_token
from supabase_admin import GmailPersistenceError

GOOGLE_AUTHORIZATION_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
OAUTH_STATE_TTL = timedelta(minutes=10)


class GmailOAuthError(Exception):
    def __init__(self, code: str, status_code: int) -> None:
        super().__init__(code)
        self.code = code
        self.status_code = status_code


class GoogleOAuthClientError(Exception):
    def __init__(self, error_code: str | None = None) -> None:
        super().__init__("Google OAuth request failed.")
        self.error_code = error_code


class GoogleOAuthClient(Protocol):
    async def post_form(
        self, url: str, form: Mapping[str, str]
    ) -> dict[str, object]: ...


class GmailOAuthStorage(Protocol):
    def get_gmail_connection(self, user_id: str) -> GmailConnectionRecord | None: ...

    def create_gmail_oauth_state(
        self, user_id: str, state: str, expires_at: datetime
    ) -> OAuthStateRecord: ...

    def consume_gmail_oauth_state(self, state: str) -> OAuthStateRecord | None: ...

    def upsert_gmail_connection(
        self, user_id: str, connection: GmailConnectionUpsert
    ) -> GmailConnectionRecord: ...

    def update_gmail_access_token_metadata(
        self, user_id: str, access_token: str | None, expires_at: datetime | None
    ) -> GmailConnectionRecord | None: ...

    def mark_gmail_connection_invalid(self, user_id: str, reason_code: str) -> None: ...


class HttpxGoogleOAuthClient:
    async def post_form(self, url: str, form: Mapping[str, str]) -> dict[str, object]:
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(url, data=form)
            response.raise_for_status()
            payload = response.json()
        except httpx.HTTPStatusError as error:
            error_code: str | None = None
            try:
                body = error.response.json()
            except ValueError:
                body = None
            if isinstance(body, dict) and body.get("error") == "invalid_grant":
                error_code = "invalid_grant"
            raise GoogleOAuthClientError(error_code) from None
        except (httpx.HTTPError, ValueError):
            raise GoogleOAuthClientError() from None
        if not isinstance(payload, dict):
            raise GoogleOAuthClientError()
        return payload


@dataclass(frozen=True)
class GmailConnectionStatus:
    configured: bool
    connected: bool
    authorization_required: bool
    google_email: str | None
    granted_scopes: tuple[str, ...]


@dataclass(frozen=True)
class GmailCredential:
    access_token: str
    expires_at: datetime | None


class GmailOAuthService:
    def __init__(
        self, storage: GmailOAuthStorage, google_client: GoogleOAuthClient | None = None
    ) -> None:
        self._storage = storage
        self._google_client = google_client or HttpxGoogleOAuthClient()

    def get_connection_status(self, user_id: str) -> GmailConnectionStatus:
        if not _configured():
            return GmailConnectionStatus(False, False, False, None, ())
        try:
            connection = self._storage.get_gmail_connection(user_id)
        except GmailPersistenceError:
            raise GmailOAuthError("gmail_token_exchange_failed", 502) from None
        if connection is None:
            return GmailConnectionStatus(True, False, False, None, ())
        authorization_required = connection.revoked_at is not None
        return GmailConnectionStatus(
            configured=True,
            connected=not authorization_required,
            authorization_required=authorization_required,
            google_email=connection.google_email,
            granted_scopes=connection.granted_scopes,
        )

    def build_authorization_url(self, user_id: str) -> str:
        config = _require_config()
        state = secrets.token_urlsafe(32)
        try:
            self._storage.create_gmail_oauth_state(
                user_id, state, datetime.now(timezone.utc) + OAUTH_STATE_TTL
            )
        except GmailPersistenceError:
            raise GmailOAuthError("gmail_invalid_oauth_state", 502) from None
        parameters = {
            "client_id": config["GMAIL_OAUTH_CLIENT_ID"],
            "redirect_uri": config["GMAIL_OAUTH_REDIRECT_URI"],
            "response_type": "code",
            "scope": GMAIL_COMPOSE_SCOPE,
            "access_type": "offline",
            "include_granted_scopes": "true",
            "prompt": "consent",
            "state": state,
        }
        return f"{GOOGLE_AUTHORIZATION_URL}?{urlencode(parameters)}"

    async def handle_oauth_callback(self, code: str | None, state: str | None) -> None:
        state_record = self._consume_state(state)
        if not code:
            raise GmailOAuthError("gmail_token_exchange_failed", 400)
        config = _require_config()
        payload = await self._token_request(
            {
                "code": code,
                "client_id": config["GMAIL_OAUTH_CLIENT_ID"],
                "client_secret": config["GMAIL_OAUTH_CLIENT_SECRET"],
                "redirect_uri": config["GMAIL_OAUTH_REDIRECT_URI"],
                "grant_type": "authorization_code",
            },
            error_code="gmail_token_exchange_failed",
            user_id=state_record.user_id,
        )
        scopes = _scopes_from_payload(payload)
        if GMAIL_COMPOSE_SCOPE not in scopes:
            raise GmailOAuthError("gmail_scope_missing", 400)
        refresh_token = payload.get("refresh_token")
        encrypted_refresh_token = (
            encrypt_token(refresh_token) if isinstance(refresh_token, str) else None
        )
        access_token = _required_token(payload, "gmail_token_exchange_failed")
        try:
            self._storage.upsert_gmail_connection(
                state_record.user_id,
                GmailConnectionUpsert(
                    encrypted_refresh_token=encrypted_refresh_token,
                    access_token=access_token,
                    access_token_expires_at=_expiry_from_payload(payload),
                    granted_scopes=scopes,
                ),
            )
        except (GmailPersistenceError, ValueError):
            raise GmailOAuthError("gmail_token_exchange_failed", 502) from None

    async def handle_oauth_denial(self, state: str | None) -> None:
        self._consume_state(state)
        raise GmailOAuthError("gmail_oauth_denied", 400)

    async def refresh_access_token(self, user_id: str) -> GmailCredential:
        config = _require_config()
        try:
            connection = self._storage.get_gmail_connection(user_id)
        except GmailPersistenceError:
            raise GmailOAuthError("gmail_token_refresh_failed", 502) from None
        if connection is None or connection.revoked_at is not None:
            raise GmailOAuthError("gmail_authorization_required", 401)
        try:
            refresh_token = decrypt_token(connection.encrypted_refresh_token)
        except ValueError:
            self.mark_authorization_invalid(user_id, "authorization_required")
            raise GmailOAuthError("gmail_authorization_required", 401) from None
        payload = await self._token_request(
            {
                "refresh_token": refresh_token,
                "client_id": config["GMAIL_OAUTH_CLIENT_ID"],
                "client_secret": config["GMAIL_OAUTH_CLIENT_SECRET"],
                "grant_type": "refresh_token",
            },
            error_code="gmail_token_refresh_failed",
            user_id=user_id,
        )
        access_token = _required_token(payload, "gmail_token_refresh_failed")
        replacement_refresh_token = payload.get("refresh_token")
        try:
            if isinstance(replacement_refresh_token, str):
                self._storage.upsert_gmail_connection(
                    user_id,
                    GmailConnectionUpsert(
                        encrypted_refresh_token=encrypt_token(
                            replacement_refresh_token
                        ),
                        access_token=access_token,
                        access_token_expires_at=_expiry_from_payload(payload),
                        granted_scopes=connection.granted_scopes,
                    ),
                )
            else:
                self._storage.update_gmail_access_token_metadata(
                    user_id, access_token, _expiry_from_payload(payload)
                )
        except GmailPersistenceError:
            raise GmailOAuthError("gmail_token_refresh_failed", 502) from None
        return GmailCredential(access_token, _expiry_from_payload(payload))

    def mark_authorization_invalid(self, user_id: str, error_code: str) -> None:
        safe_code = "invalid_grant"
        if error_code != "invalid_grant":
            safe_code = "authorization_required"
        try:
            self._storage.mark_gmail_connection_invalid(user_id, safe_code)
        except GmailPersistenceError:
            raise GmailOAuthError("gmail_token_refresh_failed", 502) from None

    def _consume_state(self, state: str | None) -> OAuthStateRecord:
        if not state:
            raise GmailOAuthError("gmail_invalid_oauth_state", 400)
        try:
            record = self._storage.consume_gmail_oauth_state(state)
        except GmailPersistenceError:
            raise GmailOAuthError("gmail_invalid_oauth_state", 502) from None
        if record is None:
            raise GmailOAuthError("gmail_oauth_state_expired", 400)
        return record

    async def _token_request(
        self, form: Mapping[str, str], error_code: str, user_id: str
    ) -> dict[str, object]:
        try:
            return await self._google_client.post_form(GOOGLE_TOKEN_URL, form)
        except GoogleOAuthClientError as error:
            if error.error_code == "invalid_grant":
                self.mark_authorization_invalid(user_id, "invalid_grant")
                raise GmailOAuthError("gmail_authorization_revoked", 401) from None
            raise GmailOAuthError(error_code, 502) from None


def _configured() -> bool:
    try:
        required_gmail_config()
    except Exception:
        return False
    return True


def _require_config() -> dict[str, str]:
    try:
        return required_gmail_config()
    except Exception:
        raise GmailOAuthError("gmail_not_configured", 503) from None


def _required_token(payload: Mapping[str, object], error_code: str) -> str:
    access_token = payload.get("access_token")
    if not isinstance(access_token, str) or not access_token:
        raise GmailOAuthError(error_code, 502)
    return access_token


def _scopes_from_payload(payload: Mapping[str, object]) -> tuple[str, ...]:
    scope = payload.get("scope")
    if not isinstance(scope, str):
        return ()
    return tuple(item for item in scope.split() if item)


def _expiry_from_payload(payload: Mapping[str, object]) -> datetime | None:
    expires_in = payload.get("expires_in")
    if not isinstance(expires_in, int) or expires_in <= 0:
        return None
    return datetime.now(timezone.utc) + timedelta(seconds=expires_in)


def configured_callback_url(name: str) -> str | None:
    value = os.getenv(name, "").strip()
    return value or None
