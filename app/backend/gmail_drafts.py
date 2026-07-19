"""Gmail draft construction and backend-only creation service."""

import base64
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path
from typing import Any, Protocol

import httpx

from email_validation import RecipientValidationError, normalize_recipients
from gmail_oauth import GmailCredential, GmailOAuthError

GMAIL_DRAFTS_URL = "https://gmail.googleapis.com/gmail/v1/users/me/drafts"
MAX_RESUME_BYTES = 10 * 1024 * 1024


class GmailDraftError(Exception):
    def __init__(self, code: str, status_code: int = 502) -> None:
        super().__init__(code)
        self.code = code
        self.status_code = status_code


class GmailDraftClientError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__("Gmail draft request failed.")
        self.code = code


class GmailDraftStorage(Protocol):
    def get_draft_for_gmail(
        self, draft_id: str, user_id: str
    ) -> dict[str, Any] | None: ...

    def get_resume(self, resume_id: str, user_id: str) -> dict[str, Any] | None: ...

    def download_resume(self, storage_path: str) -> bytes: ...

    def update_gmail_draft_sync(
        self, draft_id: str, user_id: str, update: dict[str, Any]
    ) -> dict[str, Any] | None: ...


class GmailDraftClient(Protocol):
    async def create_draft(
        self, credential: GmailCredential, raw: str
    ) -> dict[str, object]: ...

    async def update_draft(
        self, credential: GmailCredential, gmail_draft_id: str, raw: str
    ) -> dict[str, object]: ...


class GmailCredentialProvider(Protocol):
    async def refresh_access_token(self, user_id: str) -> GmailCredential: ...


class HttpxGmailDraftClient:
    async def create_draft(
        self, credential: GmailCredential, raw: str
    ) -> dict[str, object]:
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    GMAIL_DRAFTS_URL,
                    json={"message": {"raw": raw}},
                    headers={"Authorization": f"Bearer {credential.access_token}"},
                )
            response.raise_for_status()
            payload = response.json()
        except httpx.TimeoutException:
            raise GmailDraftClientError("gmail_draft_timeout") from None
        except httpx.HTTPStatusError as error:
            if error.response.status_code == 429:
                raise GmailDraftClientError("gmail_draft_rate_limited") from None
            if error.response.status_code in {401, 403}:
                raise GmailDraftClientError("gmail_authorization_required") from None
            raise GmailDraftClientError("gmail_draft_creation_failed") from None
        except (httpx.HTTPError, ValueError):
            raise GmailDraftClientError("gmail_draft_creation_failed") from None
        if not isinstance(payload, dict):
            raise GmailDraftClientError("gmail_draft_creation_failed")
        return payload

    async def update_draft(
        self, credential: GmailCredential, gmail_draft_id: str, raw: str
    ) -> dict[str, object]:
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.put(
                    f"{GMAIL_DRAFTS_URL}/{gmail_draft_id}",
                    json={"id": gmail_draft_id, "message": {"raw": raw}},
                    headers={"Authorization": f"Bearer {credential.access_token}"},
                )
            response.raise_for_status()
            payload = response.json()
        except httpx.TimeoutException:
            raise GmailDraftClientError("gmail_sync_timeout") from None
        except httpx.HTTPStatusError as error:
            if error.response.status_code == 404:
                raise GmailDraftClientError("gmail_draft_not_found") from None
            if error.response.status_code == 429:
                raise GmailDraftClientError("gmail_rate_limited") from None
            if error.response.status_code in {401, 403}:
                raise GmailDraftClientError("gmail_authorization_required") from None
            raise GmailDraftClientError("gmail_sync_failed") from None
        except (httpx.HTTPError, ValueError):
            raise GmailDraftClientError("gmail_sync_failed") from None
        if not isinstance(payload, dict):
            raise GmailDraftClientError("gmail_sync_failed")
        return payload


@dataclass(frozen=True)
class GmailDraftResult:
    gmail_draft_id: str | None
    gmail_message_id: str | None
    sync_status: str
    created: bool


def build_gmail_mime(
    recipient_to: str,
    recipient_cc: str | None,
    subject: str,
    body: str,
    resume_name: str,
    resume_content: bytes,
) -> str:
    to_address = _validated_address(recipient_to, required=True)
    cc_address = _validated_address(recipient_cc, required=False)
    if not resume_content or len(resume_content) > MAX_RESUME_BYTES:
        raise GmailDraftError("gmail_resume_unavailable", 422)
    if not resume_content.startswith(b"%PDF-"):
        raise GmailDraftError("gmail_resume_unavailable", 422)
    message = EmailMessage()
    message["To"] = to_address
    if cc_address is not None:
        message["Cc"] = cc_address
    message["Subject"] = subject
    message.set_content(body, subtype="plain", charset="utf-8")
    message.add_attachment(
        resume_content,
        maintype="application",
        subtype="pdf",
        filename=_safe_pdf_filename(resume_name),
    )
    return base64.urlsafe_b64encode(message.as_bytes()).decode().rstrip("=")


class GmailDraftService:
    def __init__(
        self,
        storage: GmailDraftStorage,
        oauth: GmailCredentialProvider,
        client: GmailDraftClient | None = None,
    ) -> None:
        self._storage = storage
        self._oauth = oauth
        self._client = client or HttpxGmailDraftClient()

    async def create_gmail_draft(self, user_id: str, draft_id: str) -> GmailDraftResult:
        draft = self._load_draft(user_id, draft_id)
        existing_id = draft.get("gmail_draft_id")
        if isinstance(existing_id, str) and existing_id:
            return GmailDraftResult(
                gmail_draft_id=existing_id,
                gmail_message_id=_optional_string(draft.get("gmail_message_id")),
                sync_status=_optional_string(draft.get("gmail_sync_status"))
                or "synced",
                created=False,
            )
        if draft.get("gmail_sync_status") == "creating":
            raise GmailDraftError("gmail_draft_creation_in_progress", 409)
        self._update_sync(
            user_id,
            draft_id,
            {"gmail_sync_status": "creating", "gmail_sync_error_code": None},
        )
        try:
            raw = self._build_message(user_id, draft)
            credential = await self._oauth.refresh_access_token(user_id)
            response = await self._client.create_draft(credential, raw)
            gmail_draft_id = _required_string(response, "id")
            message = response.get("message")
            gmail_message_id = (
                _optional_string(message.get("id"))
                if isinstance(message, dict)
                else None
            )
        except GmailOAuthError as error:
            self._record_failure(user_id, draft_id, error.code)
            raise GmailDraftError(error.code, error.status_code) from None
        except GmailDraftClientError as error:
            self._record_failure(user_id, draft_id, error.code)
            raise GmailDraftError(error.code, 502) from None
        except GmailDraftError as error:
            self._record_failure(user_id, draft_id, error.code)
            raise
        self._update_sync(
            user_id,
            draft_id,
            {
                "gmail_draft_id": gmail_draft_id,
                "gmail_message_id": gmail_message_id,
                "gmail_sync_status": "synced",
                "gmail_last_synced_at": datetime.now(timezone.utc).isoformat(),
                "gmail_sync_error_code": None,
            },
        )
        return GmailDraftResult(gmail_draft_id, gmail_message_id, "synced", True)

    async def update_gmail_draft(self, user_id: str, draft_id: str) -> GmailDraftResult:
        draft = self._load_draft(user_id, draft_id)
        gmail_draft_id = _optional_string(draft.get("gmail_draft_id"))
        if gmail_draft_id is None:
            raise GmailDraftError("gmail_draft_not_created", 409)
        if draft.get("gmail_sync_status") == "syncing":
            raise GmailDraftError("gmail_sync_in_progress", 409)
        self._update_sync(
            user_id,
            draft_id,
            {"gmail_sync_status": "syncing", "gmail_sync_error_code": None},
        )
        try:
            raw = self._build_message(user_id, draft)
            credential = await self._oauth.refresh_access_token(user_id)
            response = await self._client.update_draft(credential, gmail_draft_id, raw)
            returned_id = _required_string(response, "id")
            if returned_id != gmail_draft_id:
                raise GmailDraftClientError("gmail_sync_failed")
            message = response.get("message")
            message_id = (
                _optional_string(message.get("id"))
                if isinstance(message, dict)
                else None
            )
        except GmailOAuthError as error:
            self._record_failure(user_id, draft_id, error.code)
            raise GmailDraftError(error.code, error.status_code) from None
        except GmailDraftClientError as error:
            self._record_failure(user_id, draft_id, error.code)
            raise GmailDraftError(error.code, 502) from None
        except GmailDraftError as error:
            self._record_failure(user_id, draft_id, error.code)
            raise
        success: dict[str, Any] = {
            "gmail_sync_status": "synced",
            "gmail_last_synced_at": datetime.now(timezone.utc).isoformat(),
            "gmail_sync_error_code": None,
        }
        if message_id is not None:
            success["gmail_message_id"] = message_id
        self._update_sync(user_id, draft_id, success)
        return GmailDraftResult(gmail_draft_id, message_id, "synced", False)

    def _load_draft(self, user_id: str, draft_id: str) -> dict[str, Any]:
        try:
            draft = self._storage.get_draft_for_gmail(draft_id, user_id)
        except httpx.HTTPError:
            raise GmailDraftError("gmail_draft_creation_failed") from None
        if draft is None or draft.get("user_id") != user_id:
            raise GmailDraftError("gmail_draft_not_found", 404)
        outreach = draft.get("outreach_items")
        if not isinstance(outreach, dict) or outreach.get("user_id") != user_id:
            raise GmailDraftError("gmail_draft_not_found", 404)
        if not isinstance(outreach.get("selected_resume_id"), str):
            raise GmailDraftError("gmail_resume_unavailable", 422)
        return draft

    def _build_message(self, user_id: str, draft: Mapping[str, Any]) -> str:
        outreach = draft["outreach_items"]
        if not isinstance(outreach, dict):
            raise GmailDraftError("gmail_draft_not_found", 404)
        resume_id = outreach["selected_resume_id"]
        if not isinstance(resume_id, str):
            raise GmailDraftError("gmail_resume_unavailable", 422)
        try:
            resume = self._storage.get_resume(resume_id, user_id)
        except httpx.HTTPError:
            raise GmailDraftError("gmail_resume_unavailable", 422) from None
        if resume is None or resume.get("user_id") != user_id:
            raise GmailDraftError("gmail_resume_unavailable", 422)
        storage_path = resume.get("storage_path")
        resume_name = resume.get("name")
        if not isinstance(storage_path, str) or not isinstance(resume_name, str):
            raise GmailDraftError("gmail_resume_unavailable", 422)
        try:
            content = self._storage.download_resume(storage_path)
        except httpx.HTTPError:
            raise GmailDraftError("gmail_resume_unavailable", 422) from None
        return build_gmail_mime(
            _optional_string(outreach.get("recipient_to")) or "",
            _optional_string(outreach.get("recipient_cc")),
            _optional_string(draft.get("subject")) or "",
            _optional_string(draft.get("body")) or "",
            resume_name,
            content,
        )

    def _record_failure(self, user_id: str, draft_id: str, error_code: str) -> None:
        status = (
            "authorization_required"
            if error_code
            in {"gmail_authorization_required", "gmail_authorization_revoked"}
            else "sync_failed"
        )
        try:
            self._update_sync(
                user_id,
                draft_id,
                {"gmail_sync_status": status, "gmail_sync_error_code": error_code},
            )
        except GmailDraftError:
            pass

    def _update_sync(self, user_id: str, draft_id: str, update: dict[str, Any]) -> None:
        try:
            result = self._storage.update_gmail_draft_sync(draft_id, user_id, update)
        except httpx.HTTPError:
            raise GmailDraftError("gmail_draft_creation_failed") from None
        if result is None:
            raise GmailDraftError("gmail_draft_not_found", 404)


def _validated_address(value: str | None, required: bool) -> str | None:
    try:
        return normalize_recipients(value, required=required)
    except RecipientValidationError:
        raise GmailDraftError("gmail_invalid_recipient", 422) from None


def _safe_pdf_filename(name: str) -> str:
    candidate = Path(name).name
    candidate = re.sub(r"[^A-Za-z0-9._ -]", "_", candidate).strip(" .")
    if not candidate:
        candidate = "resume"
    return candidate if candidate.lower().endswith(".pdf") else f"{candidate}.pdf"


def _optional_string(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _required_string(value: Mapping[str, object], key: str) -> str:
    result = value.get(key)
    if not isinstance(result, str) or not result:
        raise GmailDraftClientError("gmail_draft_creation_failed")
    return result
