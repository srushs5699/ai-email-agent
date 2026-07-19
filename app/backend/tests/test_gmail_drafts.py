import asyncio
import base64
from datetime import datetime, timezone
from email import policy
from email.parser import BytesParser
from typing import Any

import pytest
from fastapi.testclient import TestClient

from auth import get_current_user
from drafts import get_gmail_draft_service
from gmail_drafts import (
    GMAIL_DRAFTS_URL,
    GmailDraftClientError,
    GmailDraftError,
    GmailDraftService,
    build_gmail_mime,
)
from gmail_oauth import GmailCredential, GmailOAuthError
from main import app

USER_A = "user-a"
USER_B = "user-b"
DRAFT_ID = "00000000-0000-0000-0000-000000000001"
RESUME_ID = "00000000-0000-0000-0000-000000000002"
PDF = b"%PDF-1.7\nresume"


class FakeStorage:
    def __init__(self) -> None:
        self.draft: dict[str, Any] | None = draft_record()
        self.resume: dict[str, Any] | None = resume_record()
        self.downloads: list[str] = []
        self.updates: list[dict[str, Any]] = []

    def get_draft_for_gmail(self, draft_id: str, user_id: str) -> dict[str, Any] | None:
        if self.draft is None or draft_id != DRAFT_ID or user_id != USER_A:
            return None
        return self.draft

    def get_resume(self, resume_id: str, user_id: str) -> dict[str, Any] | None:
        if self.resume is None or resume_id != RESUME_ID or user_id != USER_A:
            return None
        return self.resume

    def download_resume(self, storage_path: str) -> bytes:
        self.downloads.append(storage_path)
        return PDF

    def update_gmail_draft_sync(
        self, draft_id: str, user_id: str, update: dict[str, Any]
    ) -> dict[str, Any] | None:
        if draft_id != DRAFT_ID or user_id != USER_A or self.draft is None:
            return None
        self.updates.append(update)
        self.draft.update(update)
        return self.draft


class FakeOAuth:
    async def refresh_access_token(self, user_id: str) -> GmailCredential:
        if user_id != USER_A:
            raise GmailOAuthError("gmail_authorization_required", 401)
        return GmailCredential("access-token", datetime.now(timezone.utc))


class FakeGmailClient:
    def __init__(self) -> None:
        self.calls: list[tuple[GmailCredential, str]] = []
        self.response: dict[str, object] = {
            "id": "gmail-draft",
            "message": {"id": "gmail-message"},
        }
        self.error: GmailDraftClientError | None = None

    async def create_draft(
        self, credential: GmailCredential, raw: str
    ) -> dict[str, object]:
        self.calls.append((credential, raw))
        if self.error:
            raise self.error
        return self.response

    async def update_draft(
        self, credential: GmailCredential, gmail_draft_id: str, raw: str
    ) -> dict[str, object]:
        del credential, gmail_draft_id, raw
        raise AssertionError("creation tests must not update Gmail drafts")


def draft_record(**changes: object) -> dict[str, Any]:
    return {
        "id": DRAFT_ID,
        "user_id": USER_A,
        "subject": "Subject exactly",
        "body": "Body exactly\nsecond line",
        "gmail_draft_id": None,
        "gmail_message_id": None,
        "gmail_sync_status": "not_created",
        "outreach_items": {
            "id": "outreach-a",
            "user_id": USER_A,
            "recipient_to": " to@example.com ",
            "recipient_cc": " cc@example.com ",
            "selected_resume_id": RESUME_ID,
        },
        **changes,
    }


def resume_record(**changes: object) -> dict[str, Any]:
    return {
        "id": RESUME_ID,
        "user_id": USER_A,
        "name": "../resume report.pdf",
        "storage_path": "user-a/resume-id/resume.pdf",
        "mime_type": "application/pdf",
        "file_size_bytes": len(PDF),
        **changes,
    }


def decode(raw: str) -> Any:
    return BytesParser(policy=policy.default).parsebytes(
        base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4))
    )


def test_mime_includes_recipient_subject_body_and_pdf_attachment() -> None:
    raw = build_gmail_mime(
        " to@example.com ",
        " cc@example.com ",
        "Subject exactly",
        "Body exactly",
        "../unsafe resume.pdf",
        PDF,
    )
    message = decode(raw)
    attachments = list(message.iter_attachments())

    assert message["To"] == "to@example.com"
    assert message["Cc"] == "cc@example.com"
    assert message["Subject"] == "Subject exactly"
    assert message.get_body().get_content().strip() == "Body exactly"
    assert len(attachments) == 1
    assert attachments[0].get_content_type() == "application/pdf"
    assert attachments[0].get_filename() == "unsafe resume.pdf"
    assert "+" not in raw and "/" not in raw


def test_mime_omits_empty_cc_and_rejects_invalid_recipients() -> None:
    assert (
        decode(build_gmail_mime("to@example.com", " ", "s", "b", "r", PDF))["Cc"]
        is None
    )
    for invalid in ("", "invalid", "bad@example.com,other@example.com"):
        with pytest.raises(GmailDraftError, match="gmail_invalid_recipient"):
            build_gmail_mime(invalid, None, "s", "b", "r", PDF)
    with pytest.raises(GmailDraftError, match="gmail_invalid_recipient"):
        build_gmail_mime("to@example.com", "invalid", "s", "b", "r", PDF)


def test_service_downloads_owned_resume_privately_and_persists_gmail_ids() -> None:
    storage = FakeStorage()
    client = FakeGmailClient()
    result = asyncio.run(
        GmailDraftService(storage, FakeOAuth(), client).create_gmail_draft(
            USER_A, DRAFT_ID
        )
    )

    assert result.created is True
    assert result.gmail_draft_id == "gmail-draft"
    assert storage.downloads == ["user-a/resume-id/resume.pdf"]
    assert storage.updates[-1]["gmail_draft_id"] == "gmail-draft"
    assert storage.updates[-1]["gmail_message_id"] == "gmail-message"
    assert storage.updates[-1]["gmail_sync_error_code"] is None
    assert client.calls and client.calls[0][0].access_token == "access-token"


@pytest.mark.parametrize(
    "change",
    [
        {
            "outreach_items": {
                **draft_record()["outreach_items"],
                "selected_resume_id": None,
            }
        },
        {"user_id": USER_B},
        {"outreach_items": {**draft_record()["outreach_items"], "user_id": USER_B}},
    ],
)
def test_missing_or_cross_user_draft_relationships_are_rejected(
    change: dict[str, object],
) -> None:
    storage = FakeStorage()
    storage.draft = draft_record(**change)
    with pytest.raises(GmailDraftError):
        asyncio.run(
            GmailDraftService(storage, FakeOAuth()).create_gmail_draft(USER_A, DRAFT_ID)
        )
    assert not storage.downloads


def test_cross_user_resume_is_rejected() -> None:
    storage = FakeStorage()
    storage.resume = resume_record(user_id=USER_B)
    with pytest.raises(GmailDraftError, match="gmail_resume_unavailable"):
        asyncio.run(
            GmailDraftService(storage, FakeOAuth()).create_gmail_draft(USER_A, DRAFT_ID)
        )
    assert not storage.downloads


def test_existing_gmail_id_prevents_duplicate_creation() -> None:
    storage = FakeStorage()
    storage.draft = draft_record(
        gmail_draft_id="existing-id", gmail_message_id="message-id"
    )
    client = FakeGmailClient()
    result = asyncio.run(
        GmailDraftService(storage, FakeOAuth(), client).create_gmail_draft(
            USER_A, DRAFT_ID
        )
    )

    assert result.created is False
    assert not client.calls
    assert not storage.downloads


def test_in_progress_gmail_draft_prevents_a_second_request() -> None:
    storage = FakeStorage()
    storage.draft = draft_record(gmail_sync_status="creating")
    client = FakeGmailClient()

    with pytest.raises(GmailDraftError, match="gmail_draft_creation_in_progress"):
        asyncio.run(
            GmailDraftService(storage, FakeOAuth(), client).create_gmail_draft(
                USER_A, DRAFT_ID
            )
        )

    assert not client.calls


@pytest.mark.parametrize(
    "error_code",
    ["gmail_draft_rate_limited", "gmail_draft_timeout", "gmail_draft_creation_failed"],
)
def test_gmail_failures_preserve_website_draft(error_code: str) -> None:
    storage = FakeStorage()
    client = FakeGmailClient()
    client.error = GmailDraftClientError(error_code)
    assert storage.draft is not None
    original = {"subject": storage.draft["subject"], "body": storage.draft["body"]}

    with pytest.raises(GmailDraftError, match=error_code):
        asyncio.run(
            GmailDraftService(storage, FakeOAuth(), client).create_gmail_draft(
                USER_A, DRAFT_ID
            )
        )

    assert storage.draft is not None
    assert storage.draft["gmail_draft_id"] is None
    assert {
        "subject": storage.draft["subject"],
        "body": storage.draft["body"],
    } == original
    assert storage.updates[-1]["gmail_sync_status"] == "sync_failed"


def test_malformed_gmail_response_is_safe_and_not_persisted() -> None:
    storage = FakeStorage()
    client = FakeGmailClient()
    client.response = {"unexpected": "raw-upstream-response"}

    with pytest.raises(GmailDraftError, match="gmail_draft_creation_failed"):
        asyncio.run(
            GmailDraftService(storage, FakeOAuth(), client).create_gmail_draft(
                USER_A, DRAFT_ID
            )
        )

    assert all(
        "raw-upstream-response" not in update.values() for update in storage.updates
    )
    assert storage.draft is not None and storage.draft["gmail_draft_id"] is None


def test_authorization_required_is_safe_and_no_mime_or_token_is_logged(
    caplog: pytest.LogCaptureFixture,
) -> None:
    storage = FakeStorage()

    class DeniedOAuth:
        async def refresh_access_token(self, user_id: str) -> GmailCredential:
            raise GmailOAuthError("gmail_authorization_required", 401)

    with pytest.raises(GmailDraftError, match="gmail_authorization_required"):
        asyncio.run(
            GmailDraftService(storage, DeniedOAuth()).create_gmail_draft(
                USER_A, DRAFT_ID
            )
        )

    assert storage.updates[-1]["gmail_sync_status"] == "authorization_required"
    assert "Body exactly" not in caplog.text
    assert "to@example.com" not in caplog.text
    assert "access-token" not in caplog.text


def test_route_returns_sanitized_result_and_never_calls_send_endpoint() -> None:
    storage = FakeStorage()
    client = FakeGmailClient()
    service = GmailDraftService(storage, FakeOAuth(), client)
    app.dependency_overrides[get_current_user] = lambda: {
        "user_id": USER_A,
        "email": None,
    }
    app.dependency_overrides[get_gmail_draft_service] = lambda: service
    try:
        response = TestClient(app).post(f"/api/v1/drafts/{DRAFT_ID}/gmail")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["gmail_draft_id"] == "gmail-draft"
    assert "access-token" not in response.text
    assert "Body exactly" not in response.text
    assert GMAIL_DRAFTS_URL.endswith("/drafts")
