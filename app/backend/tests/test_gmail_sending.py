import asyncio
from datetime import datetime, timezone
from typing import Any

import pytest

from gmail_drafts import GmailDraftError
from gmail_oauth import GmailCredential
from gmail_sending import GmailSendClientError, GmailSendService


class Storage:
    def __init__(self) -> None:
        self.record: dict[str, Any] = {"gmail_draft_id": "stored-draft"}
        self.claims = 0
        self.failed: list[str] = []

    def claim_gmail_send(
        self, draft_id: str, user_id: str, content_hash: str
    ) -> dict[str, Any] | None:
        del draft_id, user_id, content_hash
        self.claims += 1
        if self.claims > 1:
            return None
        return self.record

    def finish_gmail_send(
        self, draft_id: str, user_id: str, gmail_message_id: str
    ) -> dict[str, Any] | None:
        del draft_id, user_id
        self.record.update(
            {
                "sent_at": "2026-07-18T01:00:00+00:00",
                "gmail_sent_message_id": gmail_message_id,
            }
        )
        return self.record

    def fail_gmail_send(self, draft_id: str, user_id: str, error_code: str) -> None:
        del draft_id, user_id
        self.failed.append(error_code)


class OAuth:
    async def refresh_access_token(self, user_id: str) -> GmailCredential:
        assert user_id == "user-a"
        return GmailCredential("token", datetime.now(timezone.utc))


class Client:
    def __init__(self) -> None:
        self.ids: list[str] = []
        self.error: GmailSendClientError | None = None

    async def send_draft(
        self, credential: GmailCredential, gmail_draft_id: str
    ) -> dict[str, object]:
        assert credential.access_token == "token"
        self.ids.append(gmail_draft_id)
        if self.error:
            raise self.error
        return {"id": "sent-message"}


def test_send_uses_only_the_stored_gmail_draft_and_persists_audit() -> None:
    storage, client = Storage(), Client()
    result = asyncio.run(
        GmailSendService(storage, OAuth(), client).send("user-a", "draft", "hash")
    )
    assert client.ids == ["stored-draft"]
    assert result.gmail_sent_message_id == "sent-message"
    assert storage.record["gmail_sent_message_id"] == "sent-message"


def test_second_claim_prevents_another_gmail_send() -> None:
    storage, client = Storage(), Client()
    service = GmailSendService(storage, OAuth(), client)
    asyncio.run(service.send("user-a", "draft", "hash"))
    with pytest.raises(GmailDraftError, match="gmail_send_not_ready"):
        asyncio.run(service.send("user-a", "draft", "hash"))
    assert client.ids == ["stored-draft"]


def test_gmail_failure_preserves_the_claimed_draft_for_safe_retry() -> None:
    storage, client = Storage(), Client()
    client.error = GmailSendClientError("gmail_send_timeout")
    with pytest.raises(GmailDraftError, match="gmail_send_timeout"):
        asyncio.run(
            GmailSendService(storage, OAuth(), client).send("user-a", "draft", "hash")
        )
    assert storage.failed == ["gmail_send_timeout"]
    assert "gmail_sent_message_id" not in storage.record
