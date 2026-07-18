from collections.abc import Generator
from io import BytesIO
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfWriter

from auth import get_current_user
from email_generation import (
    GeneratedEmail,
    ProviderUnavailableError,
    get_email_generator,
)
from main import app
from supabase_admin import get_supabase_admin


class FakeStorage:
    def __init__(self) -> None:
        self.uploaded: list[tuple[str, bytes]] = []
        self.removed: list[str] = []
        self.records: dict[str, dict[str, Any]] = {}

    def upload_resume(self, storage_path: str, content: bytes) -> None:
        self.uploaded.append((storage_path, content))

    def remove_resume(self, storage_path: str) -> None:
        self.removed.append(storage_path)

    def insert_resume(self, record: dict[str, Any]) -> dict[str, Any]:
        stored_record = {**record, "created_at": "2026-07-17T00:00:00+00:00"}
        self.records[record["id"]] = stored_record
        return stored_record

    def list_resumes(self, user_id: str) -> list[dict[str, Any]]:
        return [
            record for record in self.records.values() if record["user_id"] == user_id
        ]

    def get_resume(self, resume_id: str, user_id: str) -> dict[str, Any] | None:
        record = self.records.get(resume_id)
        if record is None or record["user_id"] != user_id:
            return None
        return record

    def delete_resume(self, resume_id: str, user_id: str) -> dict[str, Any] | None:
        record = self.get_resume(resume_id, user_id)
        if record is not None:
            del self.records[resume_id]
        return record


class FakeGenerator:
    def __init__(self, response: GeneratedEmail | Exception) -> None:
        self.response = response
        self.calls: list[str] = []

    def generate(self, prompt: str) -> GeneratedEmail:
        self.calls.append(prompt)
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


@pytest.fixture
def fake_storage() -> FakeStorage:
    return FakeStorage()


@pytest.fixture
def client(fake_storage: FakeStorage) -> Generator[TestClient]:
    app.dependency_overrides[get_current_user] = lambda: {
        "user_id": "user-a",
        "email": "person@example.com",
    }
    app.dependency_overrides[get_supabase_admin] = lambda: fake_storage
    app.dependency_overrides[get_email_generator] = lambda: FakeGenerator(
        GeneratedEmail(subject="Default subject", body="Default body")
    )
    yield TestClient(app)
    app.dependency_overrides.clear()


def textless_pdf() -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def upload_pdf(client: TestClient, content: bytes = b"not-a-real-pdf") -> Any:
    return client.post(
        "/api/v1/resumes",
        files={"file": ("my resume.pdf", content, "application/pdf")},
    )


def test_uploads_text_pdf_and_returns_safe_metadata(
    client: TestClient, fake_storage: FakeStorage, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("resumes._extract_pdf_text", lambda _content: "Python engineer")

    response = upload_pdf(client, b"pdf-content")

    assert response.status_code == 201
    payload = response.json()
    assert payload["name"] == "my resume"
    assert payload["parse_status"] == "completed"
    assert "extracted_text" not in payload
    assert fake_storage.uploaded[0][0].startswith("user-a/")
    assert fake_storage.uploaded[0][0].endswith("/my-resume.pdf")


def test_rejects_invalid_pdf(client: TestClient) -> None:
    response = upload_pdf(client)

    assert response.status_code == 422
    assert (
        response.json()["detail"]
        == "The PDF could not be read. Upload a text-based PDF."
    )


def test_rejects_textless_pdf(client: TestClient) -> None:
    response = upload_pdf(client, textless_pdf())

    assert response.status_code == 422
    assert (
        response.json()["detail"]
        == "The PDF has no extractable text. OCR is not supported."
    )


def test_rejects_non_pdf_upload(client: TestClient) -> None:
    response = client.post(
        "/api/v1/resumes",
        files={"file": ("resume.txt", b"text", "text/plain")},
    )

    assert response.status_code == 415


def test_unauthenticated_upload_is_rejected() -> None:
    unauthenticated_client = TestClient(app)
    response = unauthenticated_client.post(
        "/api/v1/resumes",
        files={"file": ("resume.pdf", b"content", "application/pdf")},
    )

    assert response.status_code == 401


def test_resume_delete_does_not_allow_another_users_record(
    client: TestClient, fake_storage: FakeStorage
) -> None:
    fake_storage.records["00000000-0000-0000-0000-000000000001"] = {
        "id": "00000000-0000-0000-0000-000000000001",
        "user_id": "user-b",
        "storage_path": "user-b/00000000-0000-0000-0000-000000000001/resume.pdf",
    }

    response = client.delete("/api/v1/resumes/00000000-0000-0000-0000-000000000001")

    assert response.status_code == 404
    assert not fake_storage.removed


def generation_payload(resume_id: str) -> dict[str, object]:
    return {
        "resume_id": resume_id,
        "linkedin_post_text": "We are growing our engineering team.",
        "job_description_text": "Build reliable web applications.",
        "no_job_description": False,
        "recipient_to": "recipient@example.com",
    }


def test_generates_email_for_owned_resume(
    client: TestClient, fake_storage: FakeStorage
) -> None:
    resume_id = "00000000-0000-0000-0000-000000000010"
    fake_storage.records[resume_id] = {
        "id": resume_id,
        "user_id": "user-a",
        "extracted_text": "Python and FastAPI experience",
        "parse_status": "completed",
    }
    generator = FakeGenerator(GeneratedEmail(subject="Hello", body="Email body"))
    app.dependency_overrides[get_email_generator] = lambda: generator

    response = client.post(
        "/api/v1/email-generation", json=generation_payload(resume_id)
    )

    assert response.status_code == 200
    assert response.json() == {"subject": "Hello", "body": "Email body"}
    assert "Python and FastAPI experience" in generator.calls[0]


def test_rejects_generation_for_another_users_resume(
    client: TestClient, fake_storage: FakeStorage
) -> None:
    resume_id = "00000000-0000-0000-0000-000000000011"
    fake_storage.records[resume_id] = {
        "id": resume_id,
        "user_id": "user-b",
        "extracted_text": "Private text",
        "parse_status": "completed",
    }

    response = client.post(
        "/api/v1/email-generation", json=generation_payload(resume_id)
    )

    assert response.status_code == 404


def test_rejects_missing_generation_input(
    client: TestClient, fake_storage: FakeStorage
) -> None:
    resume_id = "00000000-0000-0000-0000-000000000012"
    fake_storage.records[resume_id] = {
        "id": resume_id,
        "user_id": "user-a",
        "extracted_text": "Resume text",
        "parse_status": "completed",
    }
    payload = generation_payload(resume_id)
    payload["linkedin_post_text"] = ""
    payload["job_description_text"] = ""

    response = client.post("/api/v1/email-generation", json=payload)

    assert response.status_code == 422


def test_rejects_blank_generation_recipient(
    client: TestClient, fake_storage: FakeStorage
) -> None:
    resume_id = "00000000-0000-0000-0000-000000000015"
    fake_storage.records[resume_id] = {
        "id": resume_id,
        "user_id": "user-a",
        "extracted_text": "Resume text",
        "parse_status": "completed",
    }
    payload = generation_payload(resume_id)
    payload["recipient_to"] = "   "

    response = client.post("/api/v1/email-generation", json=payload)

    assert response.status_code == 422


def test_generation_returns_safe_error_for_invalid_provider_response(
    client: TestClient, fake_storage: FakeStorage
) -> None:
    resume_id = "00000000-0000-0000-0000-000000000013"
    fake_storage.records[resume_id] = {
        "id": resume_id,
        "user_id": "user-a",
        "extracted_text": "Resume text",
        "parse_status": "completed",
    }
    app.dependency_overrides[get_email_generator] = lambda: FakeGenerator(
        ValueError("untrusted provider detail")
    )

    response = client.post(
        "/api/v1/email-generation", json=generation_payload(resume_id)
    )

    assert response.status_code == 502
    assert response.json()["detail"] == (
        "Email generation returned an invalid response. Please try again."
    )
    assert "untrusted provider detail" not in response.text


def test_generation_returns_safe_error_for_provider_failure(
    client: TestClient, fake_storage: FakeStorage
) -> None:
    resume_id = "00000000-0000-0000-0000-000000000014"
    fake_storage.records[resume_id] = {
        "id": resume_id,
        "user_id": "user-a",
        "extracted_text": "Resume text",
        "parse_status": "completed",
    }
    app.dependency_overrides[get_email_generator] = lambda: FakeGenerator(
        ProviderUnavailableError("provider connection detail")
    )

    response = client.post(
        "/api/v1/email-generation", json=generation_payload(resume_id)
    )

    assert response.status_code == 502
    assert response.json()["detail"] == (
        "Email generation is temporarily unavailable. Please try again."
    )
    assert "provider connection detail" not in response.text
