import pytest
from pydantic import ValidationError

from processing_queues import QueueCreateRequest


def item() -> dict[str, object]:
    return {
        "resume_id": "00000000-0000-0000-0000-000000000001",
        "linkedin_post_text": "A role",
        "job_description_text": "Build things",
        "no_job_description": False,
        "recipient_to": "person@example.com",
    }


def test_queue_creation_requires_an_item() -> None:
    with pytest.raises(ValidationError):
        QueueCreateRequest(items=[])


def test_queue_creation_accepts_exactly_ten_ordered_items() -> None:
    request = QueueCreateRequest.model_validate({"items": [item() for _ in range(10)]})

    assert len(request.items) == 10
    assert request.items[0].recipient_to == "person@example.com"


def test_queue_creation_rejects_more_than_ten_items() -> None:
    with pytest.raises(ValidationError):
        QueueCreateRequest.model_validate({"items": [item() for _ in range(11)]})
