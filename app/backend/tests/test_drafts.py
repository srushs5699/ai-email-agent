from collections.abc import Generator
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from auth import get_current_user
from drafts import _persistence_error
from main import app
from supabase_admin import get_supabase_admin


class FakeDraftStorage:
    def __init__(self) -> None:
        self.resumes = {
            "00000000-0000-0000-0000-000000000001": {"user_id": "user-a"},
            "00000000-0000-0000-0000-000000000002": {"user_id": "user-b"},
        }
        self.drafts: dict[str, dict[str, Any]] = {}

    def get_resume(self, resume_id: str, user_id: str) -> dict[str, Any] | None:
        record = self.resumes.get(resume_id)
        return record if record and record["user_id"] == user_id else None

    def create_draft(
        self, outreach_item: dict[str, Any], draft: dict[str, Any]
    ) -> dict[str, Any]:
        draft_id = f"00000000-0000-0000-0000-00000000000{len(self.drafts) + 3}"
        outreach_id = f"00000000-0000-0000-0000-{len(self.drafts) + 100:012d}"
        outreach = {**outreach_item, "id": outreach_id}
        record = {
            **draft,
            "id": draft_id,
            "created_at": "2026-07-18T00:00:00+00:00",
            "updated_at": f"2026-07-18T00:00:0{len(self.drafts)}+00:00",
            "outreach_items": outreach,
        }
        self.drafts[draft_id] = record
        return record

    def get_draft(self, draft_id: str, user_id: str) -> dict[str, Any] | None:
        record = self.drafts.get(draft_id)
        return record if record and record["user_id"] == user_id else None

    def get_latest_draft(self, user_id: str) -> dict[str, Any] | None:
        matches = [d for d in self.drafts.values() if d["user_id"] == user_id]
        return max(matches, key=lambda draft: draft["updated_at"], default=None)

    def update_draft(
        self, draft_id: str, user_id: str, update: dict[str, Any]
    ) -> dict[str, Any] | None:
        record = self.get_draft(draft_id, user_id)
        if record is None:
            return None
        record.update(update)
        record["updated_at"] = "2026-07-18T00:01:00+00:00"
        return record


@pytest.fixture
def storage() -> FakeDraftStorage:
    return FakeDraftStorage()


@pytest.fixture
def client(storage: FakeDraftStorage) -> Generator[TestClient]:
    app.dependency_overrides[get_current_user] = lambda: {
        "user_id": "user-a",
        "email": None,
    }
    app.dependency_overrides[get_supabase_admin] = lambda: storage
    yield TestClient(app)
    app.dependency_overrides.clear()


def payload(**changes: object) -> dict[str, object]:
    return {
        "resume_id": "00000000-0000-0000-0000-000000000001",
        "linkedin_post_text": "Post",
        "job_description_text": "Role",
        "no_job_description": False,
        "recipient_to": "recipient@example.com",
        "subject": "Subject",
        "body": "Body",
        **changes,
    }


def test_creates_owned_draft_for_owned_resume(
    client: TestClient, storage: FakeDraftStorage
) -> None:
    response = client.post("/api/v1/drafts", json=payload())

    assert response.status_code == 201
    assert response.json()["subject"] == "Subject"
    assert storage.drafts[response.json()["id"]]["user_id"] == "user-a"


def test_rejects_another_users_resume(client: TestClient) -> None:
    response = client.post(
        "/api/v1/drafts",
        json=payload(resume_id="00000000-0000-0000-0000-000000000002"),
    )
    assert response.status_code == 404


@pytest.mark.parametrize("field", ["subject", "body"])
def test_rejects_blank_draft_content(client: TestClient, field: str) -> None:
    response = client.post("/api/v1/drafts", json=payload(**{field: "  "}))
    assert response.status_code == 422


def test_updates_and_gets_latest_owned_draft(client: TestClient) -> None:
    created = client.post("/api/v1/drafts", json=payload()).json()
    updated = client.patch(
        f"/api/v1/drafts/{created['id']}", json={"subject": "Updated", "body": "Body"}
    )

    assert updated.status_code == 200
    assert client.get("/api/v1/drafts/latest").json()["subject"] == "Updated"


def test_hides_other_users_draft(client: TestClient, storage: FakeDraftStorage) -> None:
    created = client.post("/api/v1/drafts", json=payload()).json()
    storage.drafts[created["id"]]["user_id"] = "user-b"

    assert client.get(f"/api/v1/drafts/{created['id']}").status_code == 404
    assert (
        client.patch(
            f"/api/v1/drafts/{created['id']}", json={"subject": "New", "body": "Body"}
        ).status_code
        == 404
    )


def test_persistence_diagnostics_log_safe_postgrest_error(
    caplog: pytest.LogCaptureFixture,
) -> None:
    request = httpx.Request(
        "POST", "https://project.supabase.co/rest/v1/generated_drafts"
    )
    response = httpx.Response(
        400,
        request=request,
        json={"code": "42703", "message": "column does not exist", "details": None},
    )

    error = _persistence_error(
        httpx.HTTPStatusError("failed", request=request, response=response)
    )

    assert error.status_code == 502
    assert "upstream_status=400" in caplog.text
    assert "supabase_code=42703" in caplog.text
    assert "column does not exist" in caplog.text
