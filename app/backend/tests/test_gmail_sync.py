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
from gmail_drafts import GmailDraftClientError, GmailDraftError, GmailDraftService
from gmail_oauth import GmailCredential, GmailOAuthError
from main import app

USER_ID = "user-a"
DRAFT_ID = "00000000-0000-0000-0000-000000000001"
RESUME_ID = "00000000-0000-0000-0000-000000000002"
PDF = b"%PDF-1.7\nlatest resume"


class FakeStorage:
    def __init__(self) -> None:
        self.draft = record()
        self.resume = {
            "id": RESUME_ID,
            "user_id": USER_ID,
            "name": "latest resume.pdf",
            "storage_path": "user-a/latest.pdf",
        }
        self.updates: list[dict[str, Any]] = []

    def get_draft_for_gmail(self, draft_id: str, user_id: str) -> dict[str, Any] | None:
        if draft_id != DRAFT_ID or user_id != USER_ID:
            return None
        return self.draft

    def get_resume(self, resume_id: str, user_id: str) -> dict[str, Any] | None:
        return self.resume if resume_id == RESUME_ID and user_id == USER_ID else None

    def download_resume(self, storage_path: str) -> bytes:
        assert storage_path == "user-a/latest.pdf"
        return PDF

    def update_gmail_draft_sync(
        self, draft_id: str, user_id: str, update: dict[str, Any]
    ) -> dict[str, Any] | None:
        if draft_id != DRAFT_ID or user_id != USER_ID:
            return None
        self.updates.append(update)
        self.draft.update(update)
        return self.draft


class FakeOAuth:
    async def refresh_access_token(self, user_id: str) -> GmailCredential:
        assert user_id == USER_ID
        return GmailCredential("token-secret", datetime.now(timezone.utc))


class FakeClient:
    def __init__(self) -> None:
        self.updates: list[tuple[GmailCredential, str, str]] = []
        self.error: GmailDraftClientError | None = None
        self.response: dict[str, object] = {
            "id": "existing-gmail-draft",
            "message": {"id": "updated-message"},
        }

    async def create_draft(
        self, credential: GmailCredential, raw: str
    ) -> dict[str, object]:
        raise AssertionError("sync must not create Gmail drafts")

    async def update_draft(
        self, credential: GmailCredential, gmail_draft_id: str, raw: str
    ) -> dict[str, object]:
        self.updates.append((credential, gmail_draft_id, raw))
        if self.error:
            raise self.error
        return self.response


def record(**changes: object) -> dict[str, Any]:
    return {
        "id": DRAFT_ID,
        "user_id": USER_ID,
        "subject": "Latest subject",
        "body": "Latest body",
        "gmail_draft_id": "existing-gmail-draft",
        "gmail_message_id": "old-message",
        "gmail_sync_status": "sync_failed",
        "outreach_items": {
            "id": "outreach-id",
            "user_id": USER_ID,
            "recipient_to": "latest-to@example.com",
            "recipient_cc": "latest-cc@example.com",
            "selected_resume_id": RESUME_ID,
        },
        **changes,
    }


def message(raw: str) -> Any:
    return BytesParser(policy=policy.default).parsebytes(
        base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4))
    )


def test_updates_existing_gmail_draft_with_latest_persisted_mime() -> None:
    storage = FakeStorage()
    client = FakeClient()
    result = asyncio.run(
        GmailDraftService(storage, FakeOAuth(), client).update_gmail_draft(
            USER_ID, DRAFT_ID
        )
    )
    mime = message(client.updates[0][2])

    assert result.gmail_draft_id == "existing-gmail-draft"
    assert result.created is False
    assert client.updates[0][1] == "existing-gmail-draft"
    assert mime["To"] == "latest-to@example.com"
    assert mime["Cc"] == "latest-cc@example.com"
    assert mime["Subject"] == "Latest subject"
    assert mime.get_body().get_content().strip() == "Latest body"
    assert len(list(mime.iter_attachments())) == 1
    assert storage.draft["gmail_draft_id"] == "existing-gmail-draft"
    assert storage.draft["gmail_message_id"] == "updated-message"
    assert storage.draft["gmail_sync_status"] == "synced"
    assert storage.draft["gmail_sync_error_code"] is None


def test_sync_rejects_missing_or_cross_user_draft() -> None:
    storage = FakeStorage()
    storage.draft["gmail_draft_id"] = None
    with pytest.raises(GmailDraftError, match="gmail_draft_not_created"):
        asyncio.run(
            GmailDraftService(storage, FakeOAuth()).update_gmail_draft(
                USER_ID, DRAFT_ID
            )
        )
    with pytest.raises(GmailDraftError, match="gmail_draft_not_found"):
        asyncio.run(
            GmailDraftService(storage, FakeOAuth()).update_gmail_draft(
                "user-b", DRAFT_ID
            )
        )


@pytest.mark.parametrize(
    "code", ["gmail_rate_limited", "gmail_sync_timeout", "gmail_draft_not_found"]
)
def test_sync_failures_retain_website_and_gmail_draft_id(code: str) -> None:
    storage = FakeStorage()
    client = FakeClient()
    client.error = GmailDraftClientError(code)
    original = {"subject": storage.draft["subject"], "body": storage.draft["body"]}

    with pytest.raises(GmailDraftError, match=code):
        asyncio.run(
            GmailDraftService(storage, FakeOAuth(), client).update_gmail_draft(
                USER_ID, DRAFT_ID
            )
        )

    assert storage.draft["gmail_draft_id"] == "existing-gmail-draft"
    assert {
        "subject": storage.draft["subject"],
        "body": storage.draft["body"],
    } == original
    assert storage.draft["gmail_sync_status"] == "sync_failed"
    assert storage.draft["gmail_sync_error_code"] == code


def test_revoked_authorization_records_safe_state() -> None:
    storage = FakeStorage()

    class RevokedOAuth:
        async def refresh_access_token(self, user_id: str) -> GmailCredential:
            raise GmailOAuthError("gmail_authorization_revoked", 401)

    with pytest.raises(GmailDraftError, match="gmail_authorization_revoked"):
        asyncio.run(
            GmailDraftService(storage, RevokedOAuth()).update_gmail_draft(
                USER_ID, DRAFT_ID
            )
        )

    assert storage.draft["gmail_sync_status"] == "authorization_required"


def test_retry_uses_same_id_latest_content_and_clears_failure() -> None:
    storage = FakeStorage()
    client = FakeClient()
    client.error = GmailDraftClientError("gmail_rate_limited")
    service = GmailDraftService(storage, FakeOAuth(), client)
    with pytest.raises(GmailDraftError):
        asyncio.run(service.update_gmail_draft(USER_ID, DRAFT_ID))

    storage.draft["subject"] = "Newer subject"
    storage.draft["body"] = "Newer body"
    client.error = None
    asyncio.run(service.update_gmail_draft(USER_ID, DRAFT_ID))
    mime = message(client.updates[-1][2])

    assert client.updates[-1][1] == "existing-gmail-draft"
    assert mime["Subject"] == "Newer subject"
    assert mime.get_body().get_content().strip() == "Newer body"
    assert storage.draft["gmail_sync_status"] == "synced"
    assert storage.draft["gmail_sync_error_code"] is None


def test_sync_route_is_sanitized_and_never_logs_credentials_or_mime(
    caplog: pytest.LogCaptureFixture,
) -> None:
    storage = FakeStorage()
    client = FakeClient()
    service = GmailDraftService(storage, FakeOAuth(), client)
    app.dependency_overrides[get_current_user] = lambda: {
        "user_id": USER_ID,
        "email": None,
    }
    app.dependency_overrides[get_gmail_draft_service] = lambda: service
    try:
        response = TestClient(app).post(f"/api/v1/drafts/{DRAFT_ID}/gmail/sync")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["gmail_draft_id"] == "existing-gmail-draft"
    assert "token-secret" not in response.text
    assert "Latest body" not in response.text
    assert "token-secret" not in caplog.text
    assert "Latest body" not in caplog.text
