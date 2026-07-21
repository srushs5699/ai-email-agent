from typing import Any, Generator

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from auth import get_current_user
from email_generation import GeneratedEmail, get_email_generator
from main import app
from processing_queues import DuplicateQueueItemError, QueueInput, _failure_details
from supabase_admin import get_supabase_admin

ITEM_ID = "00000000-0000-0000-0000-000000000001"
QUEUE_ID = "00000000-0000-0000-0000-000000000002"
RESUME_ID = "00000000-0000-0000-0000-000000000003"


class FailedTaskStorage:
    def __init__(self) -> None:
        self.item: dict[str, Any] = {
            "id": ITEM_ID,
            "queue_id": QUEUE_ID,
            "user_id": "user-123",
            "status": "failed",
            "failure_status": "no_email_available",
            "failure_reason": "No usable recipient email is available.",
            "retry_count": 0,
            "created_at": "2026-07-23T00:00:00Z",
            "updated_at": "2026-07-23T00:00:00Z",
            "input_payload": {
                "resume_id": RESUME_ID,
                "linkedin_post_url": "https://jobs.example.com/role",
                "linkedin_post_text": "A role is open.",
                "job_description_text": "Build useful products.",
                "recipient_to": "",
            },
        }
        self.created: list[dict[str, Any]] = []

    def get_failed_task(self, item_id: str, user_id: str) -> dict[str, Any] | None:
        return self.item if item_id == ITEM_ID and user_id == "user-123" else None

    def update_failed_processing_queue_item(
        self, item_id: str, user_id: str, payload: dict[str, object]
    ) -> dict[str, Any] | None:
        if (
            item_id != ITEM_ID
            or user_id != "user-123"
            or self.item["status"] != "failed"
        ):
            return None
        self.item["input_payload"] = payload
        return self.item

    def claim_failed_task_retry(
        self, item_id: str, user_id: str
    ) -> dict[str, Any] | None:
        if (
            item_id != ITEM_ID
            or user_id != "user-123"
            or self.item["status"] != "failed"
        ):
            return None
        self.item.update(
            {
                "status": "processing",
                "retry_count": self.item["retry_count"] + 1,
                "failure_status": None,
                "failure_reason": None,
            }
        )
        return self.item

    def get_resume(self, resume_id: str, user_id: str) -> dict[str, str] | None:
        return (
            {"parse_status": "completed", "extracted_text": "Resume text"}
            if resume_id == RESUME_ID and user_id == "user-123"
            else None
        )

    def list_resumes(self, user_id: str) -> list[dict[str, str]]:
        return (
            [{"id": RESUME_ID, "parse_status": "completed"}]
            if user_id == "user-123"
            else []
        )

    def find_active_duplicate_draft(
        self, user_id: str, recipient_to: str, linkedin_post_url: str | None
    ) -> None:
        return None

    def create_draft(
        self, outreach: dict[str, Any], draft: dict[str, Any]
    ) -> dict[str, str]:
        self.created.append({**outreach, **draft})
        return {"id": "00000000-0000-0000-0000-000000000004"}

    def complete_processing_queue_item(
        self, item_id: str, user_id: str, draft_id: str
    ) -> None:
        self.item["status"] = "completed"

    def fail_processing_queue_item(
        self,
        item_id: str,
        user_id: str,
        error_code: str,
        failure_status: str,
        reason: str,
        failure_stage: str | None = None,
    ) -> None:
        self.item.update(
            {
                "status": "failed",
                "failure_status": failure_status,
                "failure_reason": reason,
                "failure_stage": failure_stage,
            }
        )

    def reconcile_processing_queue(self, queue_id: str, user_id: str) -> None:
        return None


class FailedTaskGenerator:
    def generate(self, prompt: str) -> GeneratedEmail:
        return GeneratedEmail(subject="Subject", body="Body")


@pytest.fixture
def failed_task_client() -> Generator[tuple[TestClient, FailedTaskStorage]]:
    storage = FailedTaskStorage()
    app.dependency_overrides[get_current_user] = lambda: {
        "user_id": "user-123",
        "email": "user@example.com",
    }
    app.dependency_overrides[get_supabase_admin] = lambda: storage
    app.dependency_overrides[get_email_generator] = lambda: FailedTaskGenerator()
    yield TestClient(app), storage
    app.dependency_overrides.clear()


def test_failure_statuses_are_safe_and_user_facing() -> None:
    assert _failure_details(ValueError("resume"))[0] == "failed"
    assert _failure_details(ValueError("anything"))[0] == "failed"
    assert _failure_details(DuplicateQueueItemError())[0] == "duplicate"


def test_failure_details_preserve_stage_and_timeout_reason() -> None:
    status, code, reason = _failure_details(
        httpx.ReadTimeout("timed out"), "ai_generation"
    )

    assert status == "failed"
    assert code == "external_service_timeout"
    assert reason == "The external service timed out during ai generation."


def test_failure_details_preserve_missing_resume_reason() -> None:
    _, code, reason = _failure_details(ValueError("resume"), "resume_loading")

    assert code == "resume_unavailable"
    assert reason == "The selected resume is unavailable or not ready."


def test_failed_task_response_preserves_linkedin_url() -> None:
    # Import here so this test also protects the public failed-task shape.
    from failed_tasks import _response

    result = _response(
        {
            "id": "00000000-0000-0000-0000-000000000001",
            "queue_id": "00000000-0000-0000-0000-000000000002",
            "input_payload": {
                "resume_id": "00000000-0000-0000-0000-000000000003",
                "linkedin_post_url": "https://www.linkedin.com/posts/example",
            },
            "failure_status": "duplicate",
            "failure_reason": "An equivalent draft already exists.",
            "retry_count": 2,
            "status": "failed",
            "created_at": "2026-07-23T00:00:00Z",
            "updated_at": "2026-07-23T00:00:00Z",
        }
    )
    assert result.linkedin_post_url == "https://www.linkedin.com/posts/example"
    assert result.status == "duplicate"


def test_no_email_failure_is_classified() -> None:
    try:
        QueueInput.model_validate(
            {
                "resume_id": "00000000-0000-0000-0000-000000000001",
                "linkedin_post_url": "https://jobs.example.com/role",
                "recipient_to": "",
            }
        )
    except ValidationError as error:
        assert _failure_details(error)[0] == "no_email_available"


def test_save_then_retry_no_email_task_uses_persisted_email(
    failed_task_client: tuple[TestClient, FailedTaskStorage],
) -> None:
    client, storage = failed_task_client

    saved = client.patch(
        f"/api/v1/failed-tasks/{ITEM_ID}",
        json={"recipient_to": "corrected@example.com"},
    )

    assert saved.status_code == 200
    assert saved.json()["id"] == ITEM_ID
    assert storage.item["input_payload"]["recipient_to"] == "corrected@example.com"
    assert storage.item["status"] == "failed"
    assert storage.item["retry_count"] == 0

    retried = client.post(f"/api/v1/failed-tasks/{ITEM_ID}/retry")

    assert retried.status_code == 200
    assert storage.item["retry_count"] == 1
    assert storage.item["status"] == "completed"
    assert storage.created[0]["recipient_to"] == "corrected@example.com"


def test_save_rejects_an_invalid_recipient_email(
    failed_task_client: tuple[TestClient, FailedTaskStorage],
) -> None:
    client, _ = failed_task_client

    response = client.patch(
        f"/api/v1/failed-tasks/{ITEM_ID}",
        json={"recipient_to": "not-an-email"},
    )

    assert response.status_code == 422
    assert "valid email" in response.text


def test_retry_repairs_a_legacy_task_with_one_completed_resume(
    failed_task_client: tuple[TestClient, FailedTaskStorage],
) -> None:
    client, storage = failed_task_client
    storage.item["input_payload"].pop("resume_id")
    storage.item["input_payload"]["recipient_to"] = "corrected@example.com"

    response = client.post(f"/api/v1/failed-tasks/{ITEM_ID}/retry")

    assert response.status_code == 200
    assert storage.created[0]["selected_resume_id"] == RESUME_ID
