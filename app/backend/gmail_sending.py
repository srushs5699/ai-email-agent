"""Explicit, approval-gated Gmail send-existing-draft service."""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol

import httpx

from gmail_drafts import GmailDraftError
from gmail_oauth import GmailCredential, GmailOAuthError

GMAIL_DRAFT_SEND_URL = "https://gmail.googleapis.com/gmail/v1/users/me/drafts/send"


class GmailSendClientError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class GmailSendClient(Protocol):
    async def send_draft(
        self, credential: GmailCredential, gmail_draft_id: str
    ) -> dict[str, object]: ...


class HttpxGmailSendClient:
    async def send_draft(
        self, credential: GmailCredential, gmail_draft_id: str
    ) -> dict[str, object]:
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    GMAIL_DRAFT_SEND_URL,
                    json={"id": gmail_draft_id},
                    headers={"Authorization": f"Bearer {credential.access_token}"},
                )
            response.raise_for_status()
            payload = response.json()
        except httpx.TimeoutException:
            raise GmailSendClientError("gmail_send_timeout") from None
        except httpx.HTTPStatusError as error:
            if error.response.status_code == 429:
                raise GmailSendClientError("gmail_send_rate_limited") from None
            if error.response.status_code in {401, 403}:
                raise GmailSendClientError("gmail_authorization_required") from None
            raise GmailSendClientError("gmail_send_failed") from None
        except (httpx.HTTPError, ValueError):
            raise GmailSendClientError("gmail_send_failed") from None
        if not isinstance(payload, dict) or not isinstance(payload.get("id"), str):
            raise GmailSendClientError("gmail_send_failed")
        return payload


class GmailSendStorage(Protocol):
    def claim_gmail_send(
        self, draft_id: str, user_id: str, content_hash: str
    ) -> dict[str, Any] | None: ...
    def finish_gmail_send(
        self, draft_id: str, user_id: str, gmail_message_id: str
    ) -> dict[str, Any] | None: ...
    def fail_gmail_send(self, draft_id: str, user_id: str, error_code: str) -> None: ...


class GmailCredentialProvider(Protocol):
    async def refresh_access_token(self, user_id: str) -> GmailCredential: ...


@dataclass(frozen=True)
class GmailSendResult:
    gmail_sent_message_id: str
    sent_at: str


class GmailSendService:
    def __init__(
        self,
        storage: GmailSendStorage,
        oauth: GmailCredentialProvider,
        client: GmailSendClient | None = None,
    ) -> None:
        self._storage = storage
        self._oauth = oauth
        self._client = client or HttpxGmailSendClient()

    async def send(
        self, user_id: str, draft_id: str, content_hash: str
    ) -> GmailSendResult:
        claimed = self._storage.claim_gmail_send(draft_id, user_id, content_hash)
        if claimed is None:
            raise GmailDraftError("gmail_send_not_ready", 409)
        gmail_draft_id = claimed.get("gmail_draft_id")
        if not isinstance(gmail_draft_id, str) or not gmail_draft_id:
            raise GmailDraftError("gmail_draft_not_created", 409)
        try:
            credential = await self._oauth.refresh_access_token(user_id)
            response = await self._client.send_draft(credential, gmail_draft_id)
        except GmailOAuthError as error:
            self._safe_fail(user_id, draft_id, error.code)
            raise GmailDraftError(error.code, error.status_code) from None
        except GmailSendClientError as error:
            self._safe_fail(user_id, draft_id, error.code)
            raise GmailDraftError(error.code, 502) from None
        message_id = response["id"]
        assert isinstance(message_id, str)
        finished = self._storage.finish_gmail_send(draft_id, user_id, message_id)
        if finished is None:
            raise GmailDraftError("gmail_send_persistence_failed", 502)
        sent_at = finished.get("sent_at")
        return GmailSendResult(
            message_id,
            sent_at
            if isinstance(sent_at, str)
            else datetime.now(timezone.utc).isoformat(),
        )

    def _safe_fail(self, user_id: str, draft_id: str, code: str) -> None:
        try:
            self._storage.fail_gmail_send(draft_id, user_id, code)
        except httpx.HTTPError:
            pass
