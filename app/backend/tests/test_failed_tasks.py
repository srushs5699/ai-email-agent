from pydantic import ValidationError

from processing_queues import DuplicateQueueItemError, QueueInput, _failure_details


def test_failure_statuses_are_safe_and_user_facing() -> None:
    assert _failure_details(ValueError("resume"))[0] == "failed"
    assert _failure_details(ValueError("anything"))[0] == "failed"
    assert _failure_details(DuplicateQueueItemError())[0] == "duplicate"


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
                "recipient_to": "",
            }
        )
    except ValidationError as error:
        assert _failure_details(error)[0] == "no_email_available"
