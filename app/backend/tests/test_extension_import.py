import pytest

from extension_import import ImportRequest, JobPageError, _failed, classify_job_description_unavailable, extract_job_description, import_capture, normalize_public_url
from supabase_admin import ExtensionQueueAppendError


def test_html_is_sanitized_to_readable_job_text() -> None:
    text = extract_job_description("<nav>Home Cookie settings</nav><h1>Senior Engineer</h1><p>Build reliable systems.</p><ul><li>Python</li><li>Distributed systems</li></ul><script>alert(1)</script><footer>Privacy</footer>")
    assert "Senior Engineer" in text
    assert "Build reliable systems" in text
    assert "Python" in text
    assert "alert" not in text
    assert "Home Cookie" not in text


@pytest.mark.parametrize("url", ["javascript:alert(1)", "file:///etc/passwd", "not a url"])
def test_non_public_or_malformed_urls_are_rejected(url: str) -> None:
    with pytest.raises(JobPageError):
        normalize_public_url(url)


def test_request_uses_explicit_extension_field_names() -> None:
    request = ImportRequest.model_validate({"version": 1, "linkedin_post_url": "https://www.linkedin.com/feed/update/1", "author_name": "Ada", "author_profile_url": "https://www.linkedin.com/in/ada", "linkedin_post_text": "Hiring engineers", "job_description_url": "https://jobs.example.com/1", "captured_at": "2026-07-19T00:00:00Z"})
    assert request.linkedin_post_url.endswith("/1")
    assert request.linkedin_post_text == "Hiring engineers"


def test_success_persists_all_capture_fields_and_queue_relationship(monkeypatch: pytest.MonkeyPatch) -> None:
    saved: dict[str, object] = {}
    class Storage:
        def find_extension_duplicate(self, *_: object) -> None: return None
        def append_extension_processing_queue_item(self, user_id: str, metadata: dict[str, object]) -> dict[str, object]:
            saved.update(metadata)
            return {"queue_id": "00000000-0000-0000-0000-000000000001", "queue_item_id": "00000000-0000-0000-0000-000000000002", "outreach_item_id": "00000000-0000-0000-0000-000000000003", "queue_item_count": 1, "created_new_queue": True, "queue_status": "draft"}
    monkeypatch.setattr("extension_import.normalize_public_url", lambda url: url)
    result = import_capture(ImportRequest.model_validate({"version": 1, "linkedin_post_url": "https://www.linkedin.com/feed/1", "author_name": "Ada", "author_profile_url": "https://www.linkedin.com/in/ada", "linkedin_post_text": "A post", "job_description_url": "https://jobs.example.com/1", "job_description_text": "Visible job description captured in the browser.", "job_description_source": "visible_page", "captured_at": "2026-07-19T00:00:00Z"}), {"user_id": "user-1"}, Storage())
    assert result.status == "queued" and result.outreach_item_id
    assert saved["linkedin_post_url"] and saved["author_name"] and saved["author_profile_url"]
    assert saved["linkedin_post_text"] and saved["job_description_url"] and saved["job_description_text"]


@pytest.mark.parametrize(("match", "reason", "path"), [
    ({"id": "00000000-0000-0000-0000-000000000010", "queue_id": "00000000-0000-0000-0000-000000000011", "outreach_item_id": "00000000-0000-0000-0000-000000000012", "record_type": "processing_queue_item", "location": "Already in Processing Queue", "open_path": "/processing-queue?queueId=x"}, "Already in Processing Queue", "/processing-queue?queueId=x"),
    ({"id": "00000000-0000-0000-0000-000000000010", "queue_id": "00000000-0000-0000-0000-000000000011", "outreach_item_id": "00000000-0000-0000-0000-000000000012", "record_type": "failed_task", "location": "Failed Tasks", "open_path": "/failed-tasks"}, "Failed Tasks", "/failed-tasks"),
    ({"id": "00000000-0000-0000-0000-000000000010", "outreach_item_id": "00000000-0000-0000-0000-000000000012", "record_type": "review_item", "location": "Already in Review Queue", "open_path": "/review-queue"}, "Already in Review Queue", "/review-queue"),
    ({"id": "00000000-0000-0000-0000-000000000010", "queue_id": "00000000-0000-0000-0000-000000000011", "outreach_item_id": "00000000-0000-0000-0000-000000000012", "record_type": "processing_queue_item", "location": "Already completed", "open_path": "/processing-queue?queueId=x"}, "Already completed", "/processing-queue?queueId=x"),
])
def test_existing_visible_records_return_location_and_open_path(monkeypatch: pytest.MonkeyPatch, match: dict[str, str], reason: str, path: str) -> None:
    class Storage:
        def find_extension_duplicate(self, *_: object) -> dict[str, str]: return match
    monkeypatch.setattr("extension_import.normalize_public_url", lambda url: url)
    request = ImportRequest.model_validate({"version": 1, "linkedin_post_url": "https://www.linkedin.com/feed/1", "author_name": "Ada", "linkedin_post_text": "A post", "job_description_url": "https://jobs.example.com/1", "captured_at": "2026-07-19T00:00:00Z"})
    result = import_capture(request, {"user_id": "user-1"}, Storage())
    assert result.status == "duplicate" and result.reason == reason and result.existing_item_path == path


def test_orphaned_outreach_is_repaired_instead_of_reported_as_duplicate(monkeypatch: pytest.MonkeyPatch) -> None:
    class Storage:
        def find_extension_duplicate(self, *_: object) -> dict[str, str]: return {"record_type": "orphaned_outreach", "outreach_item_id": "00000000-0000-0000-0000-000000000012"}
        def repair_extension_orphan(self, *_: object) -> dict[str, object]: return {"queue_id": "00000000-0000-0000-0000-000000000001", "queue_item_id": "00000000-0000-0000-0000-000000000002", "outreach_item_id": "00000000-0000-0000-0000-000000000012", "queue_item_count": 1, "created_new_queue": False, "queue_status": "draft"}
    monkeypatch.setattr("extension_import.normalize_public_url", lambda url: url)
    request = ImportRequest.model_validate({"version": 1, "linkedin_post_url": "https://www.linkedin.com/feed/1", "author_name": "Ada", "linkedin_post_text": "A post", "job_description_url": "https://jobs.example.com/1", "captured_at": "2026-07-19T00:00:00Z"})
    assert import_capture(request, {"user_id": "user-1"}, Storage()).status == "repaired"


def test_empty_orphan_repair_response_falls_back_to_a_new_import(monkeypatch: pytest.MonkeyPatch) -> None:
    class Storage:
        def find_extension_duplicate(self, *_: object) -> dict[str, str]: return {"record_type": "orphaned_outreach", "outreach_item_id": "00000000-0000-0000-0000-000000000012", "id": "00000000-0000-0000-0000-000000000012", "location": "orphaned outreach"}
        def repair_extension_orphan(self, *_: object) -> None: return None
        def append_extension_processing_queue_item(self, *_: object) -> dict[str, object]: return {"queue_id": "00000000-0000-0000-0000-000000000001", "queue_item_id": "00000000-0000-0000-0000-000000000002", "outreach_item_id": "00000000-0000-0000-0000-000000000003", "queue_item_count": 1, "created_new_queue": True, "queue_status": "draft"}
    monkeypatch.setattr("extension_import.normalize_public_url", lambda url: url)
    request = ImportRequest.model_validate({"version": 1, "linkedin_post_url": "https://www.linkedin.com/feed/1", "author_name": "Ada", "linkedin_post_text": "A post", "idempotency_key": "capture-empty-repair", "captured_at": "2026-07-19T00:00:00Z"})
    assert import_capture(request, {"user_id": "user-1"}, Storage()).outcome == "queued"


def test_duplicate_url_is_normalized_before_lookup(monkeypatch: pytest.MonkeyPatch) -> None:
    looked_up: list[str] = []
    class Storage:
        def find_extension_duplicate(self, _user: str, url: str) -> None: looked_up.append(url); return None
        def append_extension_processing_queue_item(self, *_: object) -> dict[str, object]: return {"queue_id": "00000000-0000-0000-0000-000000000001", "queue_item_id": "00000000-0000-0000-0000-000000000002", "outreach_item_id": "00000000-0000-0000-0000-000000000003", "queue_item_count": 1, "created_new_queue": True, "queue_status": "draft"}
    monkeypatch.setattr("extension_import.normalize_public_url", lambda _url: "https://www.linkedin.com/feed/1")
    request = ImportRequest.model_validate({"version": 1, "linkedin_post_url": "https://www.linkedin.com/feed/1?tracking=x#fragment", "author_name": "Ada", "linkedin_post_text": "A post", "job_description_url": "https://jobs.example.com/1", "captured_at": "2026-07-19T00:00:00Z"})
    import_capture(request, {"user_id": "user-1"}, Storage())
    assert looked_up == ["https://www.linkedin.com/feed/1"]


def test_missing_jd_is_queued_and_does_not_create_failed_task(monkeypatch: pytest.MonkeyPatch) -> None:
    class Storage:
        def find_extension_duplicate(self, *_: object) -> None: return None
        def create_extension_failed_task(self, *_: object) -> object: raise AssertionError("recoverable anti-bot result must not create a failed task")
        def append_extension_processing_queue_item(self, _user: str, metadata: dict[str, object]) -> dict[str, object]:
            assert metadata["job_description_text"] is None and metadata["job_description_source"] == "unavailable"
            return {"queue_id": "00000000-0000-0000-0000-000000000001", "queue_item_id": "00000000-0000-0000-0000-000000000002", "outreach_item_id": "00000000-0000-0000-0000-000000000003", "queue_item_count": 1, "created_new_queue": True, "queue_status": "draft"}
    monkeypatch.setattr("extension_import.normalize_public_url", lambda url: url)
    request = ImportRequest.model_validate({"version": 1, "linkedin_post_url": "https://www.linkedin.com/feed/1", "author_name": "Ada", "linkedin_post_text": "A post", "job_description_url": "https://jobs.example.com/1", "captured_at": "2026-07-19T00:00:00Z"})
    result = import_capture(request, {"user_id": "user-1"}, Storage())
    assert result.outcome == "queued" and result.status == "queued" and result.outreach_item_id


def test_exact_blocked_jd_workflow_queues_without_failed_or_existing_state(monkeypatch: pytest.MonkeyPatch) -> None:
    saved: dict[str, object] = {}
    class Storage:
        def find_extension_duplicate(self, *_: object) -> None: return None
        def create_extension_failed_task(self, *_: object) -> object: raise AssertionError("JD unavailability must not create Failed Tasks")
        def append_extension_processing_queue_item(self, _user: str, metadata: dict[str, object]) -> dict[str, object]:
            saved.update(metadata)
            return {"queue_id": "00000000-0000-0000-0000-000000000001", "queue_item_id": "00000000-0000-0000-0000-000000000002", "outreach_item_id": "00000000-0000-0000-0000-000000000003", "queue_item_count": 2, "created_new_queue": False, "queue_status": "draft"}
    monkeypatch.setattr("extension_import.normalize_public_url", lambda url: url.split("?")[0].rstrip("/"))
    request = ImportRequest.model_validate({"version": 1, "linkedin_post_url": "https://www.linkedin.com/feed/update/urn:li:activity:123?trk=feed", "author_name": "Ada", "author_profile_url": "https://www.linkedin.com/in/ada", "linkedin_post_text": "Hiring platform engineers", "job_description_url": "https://jobs.example.com/blocked", "job_description_text": None, "job_description_source": "unavailable", "idempotency_key": "capture-12345678", "captured_at": "2026-07-19T00:00:00Z"})
    result = import_capture(request, {"user_id": "user-1"}, Storage())
    assert result.outcome == "queued" and result.queue_id and result.outreach_item_id
    assert saved["linkedin_post_url"] == "https://www.linkedin.com/feed/update/urn:li:activity:123"
    assert saved["job_description_url"] == "https://jobs.example.com/blocked" and saved["job_description_text"] is None


def test_old_failed_row_is_not_a_duplicate(monkeypatch: pytest.MonkeyPatch) -> None:
    class Storage:
        def find_extension_duplicate(self, *_: object) -> None: return None
        def append_extension_processing_queue_item(self, *_: object) -> dict[str, object]: return {"queue_id": "00000000-0000-0000-0000-000000000001", "queue_item_id": "00000000-0000-0000-0000-000000000002", "outreach_item_id": "00000000-0000-0000-0000-000000000003", "queue_item_count": 1, "created_new_queue": True, "queue_status": "draft"}
    monkeypatch.setattr("extension_import.normalize_public_url", lambda url: url)
    request = ImportRequest.model_validate({"version": 1, "linkedin_post_url": "https://www.linkedin.com/feed/1", "author_name": "Ada", "linkedin_post_text": "A post", "job_description_source": "unavailable", "idempotency_key": "capture-failed-123", "captured_at": "2026-07-19T00:00:00Z"})
    assert import_capture(request, {"user_id": "user-1"}, Storage()).outcome == "queued"


def test_queue_append_error_is_reported_without_creating_a_failed_task(monkeypatch: pytest.MonkeyPatch) -> None:
    class Storage:
        def find_extension_duplicate(self, *_: object) -> None: return None
        def append_extension_processing_queue_item(self, *_: object) -> dict[str, object]: raise ExtensionQueueAppendError("Processing Queue append was rejected (400): batch is full")
        def create_extension_failed_task(self, *_: object) -> object: raise AssertionError("queue RPC error must not create Failed Tasks")
    monkeypatch.setattr("extension_import.normalize_public_url", lambda url: url)
    request = ImportRequest.model_validate({"version": 1, "linkedin_post_url": "https://www.linkedin.com/feed/1", "author_name": "Ada", "linkedin_post_text": "A post", "idempotency_key": "capture-queue-full", "captured_at": "2026-07-19T00:00:00Z"})
    result = import_capture(request, {"user_id": "user-1"}, Storage())
    assert result.outcome == "error" and "batch is full" in (result.reason or "")


@pytest.mark.parametrize(("status_code", "body", "content_type", "timed_out"), [
    (401, "", "text/html", False), (403, "", "text/html", False), (429, "", "text/html", False),
    (200, "CAPTCHA Verify you are human", "text/html", False), (200, "Access denied", "text/html", False),
    (200, "Login required", "text/html", False), (200, "", "application/pdf", False), (None, "", None, True),
])
def test_protected_or_unavailable_jd_outcomes_are_nonfatal(status_code: int | None, body: str, content_type: str | None, timed_out: bool) -> None:
    assert classify_job_description_unavailable(status_code, body, content_type, timed_out)


def test_manual_jd_source_is_persisted(monkeypatch: pytest.MonkeyPatch) -> None:
    saved: dict[str, object] = {}
    class Storage:
        def find_extension_duplicate(self, *_: object) -> None: return None
        def append_extension_processing_queue_item(self, _user: str, metadata: dict[str, object]) -> dict[str, object]:
            saved.update(metadata); return {"queue_id": "00000000-0000-0000-0000-000000000001", "queue_item_id": "00000000-0000-0000-0000-000000000002", "outreach_item_id": "00000000-0000-0000-0000-000000000003", "queue_item_count": 1, "created_new_queue": False, "queue_status": "draft"}
    monkeypatch.setattr("extension_import.normalize_public_url", lambda url: url)
    request = ImportRequest.model_validate({"version": 1, "linkedin_post_url": "https://www.linkedin.com/feed/1", "author_name": "Ada", "linkedin_post_text": "A post", "job_description_text": "Manually pasted description", "job_description_source": "manual", "captured_at": "2026-07-19T00:00:00Z"})
    assert import_capture(request, {"user_id": "user-1"}, Storage()).status == "queued"
    assert saved["job_description_source"] == "manual"


def test_terminal_failure_is_verified_before_failed_response_is_returned() -> None:
    class Storage:
        def create_extension_failed_task(self, user_id: str, metadata: dict[str, object], reason: str, stage: str) -> dict[str, object]:
            assert user_id == "user-1" and metadata["linkedin_post_url"] == "https://www.linkedin.com/feed/1"
            return {"id": "00000000-0000-0000-0000-000000000099", "status": "failed"}
        def get_failed_task(self, item_id: str, user_id: str) -> dict[str, object]:
            assert item_id.endswith("99") and user_id == "user-1"
            return {"id": item_id, "status": "failed", "hidden_at": None, "failure_reason": "unreachable", "failure_stage": "job_description_fetch"}
    result = _failed(Storage(), "user-1", {"linkedin_post_url": "https://www.linkedin.com/feed/1", "job_description_url": "https://jobs.example/1"}, "unreachable", "job_description_fetch")
    assert str(result.failed_task_id).endswith("0099") and result.status == "failed"


def test_unverified_failed_insert_never_claims_failed_tasks() -> None:
    class Storage:
        def create_extension_failed_task(self, *_: object) -> dict[str, object]: return {"id": "00000000-0000-0000-0000-000000000099", "status": "failed"}
        def get_failed_task(self, *_: object) -> None: return None
    with pytest.raises(RuntimeError, match="could not be verified"):
        _failed(Storage(), "user-1", {}, "unreachable", "job_description_fetch")
