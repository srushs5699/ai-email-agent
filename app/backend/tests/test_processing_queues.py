import pytest
from pydantic import ValidationError

from processing_queues import (
    QueueCreateRequest,
    QueueInput,
    normalize_queue_input_payload,
)


def item() -> dict[str, object]:
    return {
        "resume_id": "00000000-0000-0000-0000-000000000001",
        "linkedin_post_url": "https://jobs.example.com/role",
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


def test_unavailable_job_description_normalizes_for_queue_validation() -> None:
    payload = normalize_queue_input_payload(
        {
            **item(),
            "job_description_text": " ",
            "job_description_url": "https://jobs.example/role",
            "job_description_source": "unavailable",
        }
    )

    assert payload["job_description_text"] == ""
    assert payload["job_description_url"] is None
    assert payload["no_job_description"] is True
    assert QueueInput.model_validate(payload).no_job_description is True


def test_pasted_text_clears_unavailable_job_description_state() -> None:
    payload = normalize_queue_input_payload(
        {
            **item(),
            "job_description_text": " Pasted role ",
            "job_description_source": "unavailable",
        }
    )

    assert payload["job_description_text"] == "Pasted role"
    assert payload["job_description_source"] == "manual"
    assert payload["no_job_description"] is False


def test_job_description_url_is_a_valid_queue_input() -> None:
    payload = normalize_queue_input_payload(
        {
            **item(),
            "job_description_text": "",
            "job_description_url": "https://jobs.example/role",
        }
    )

    assert payload["no_job_description"] is False
    assert (
        QueueInput.model_validate(payload).job_description_url
        == "https://jobs.example/role"
    )


@pytest.mark.parametrize("post_text", [None, "", "   "])
def test_queue_accepts_missing_linkedin_post_text(post_text: object) -> None:
    validated = QueueInput.model_validate({**item(), "linkedin_post_text": post_text})

    assert validated.linkedin_post_text is None


@pytest.mark.parametrize(
    "url",
    ["https://www.linkedin.com/jobs/view/123", "https://jobs.lever.co/acme/role"],
)
def test_queue_accepts_http_source_urls_from_any_host(url: str) -> None:
    validated = QueueInput.model_validate({**item(), "linkedin_post_url": url})

    assert validated.linkedin_post_url == url


@pytest.mark.parametrize("url", ["javascript:alert(1)", "data:text/plain,nope", "file:///tmp/a"])
def test_queue_rejects_unsafe_source_url_protocols(url: str) -> None:
    with pytest.raises(ValidationError, match="Only HTTP and HTTPS URLs are allowed"):
        QueueInput.model_validate({**item(), "linkedin_post_url": url})
