# ruff: noqa: E501

import re

import httpx
import pytest

from supabase_admin import ExtensionOrphanRepairError, ExtensionQueueAppendError, SupabaseAdmin


class Response:
    def __init__(self, status_code: int, payload: object) -> None:
        self.status_code = status_code
        self._payload = payload
        self.is_error = status_code >= 400
        self.text = str(payload)

    def json(self) -> object:
        return self._payload


def test_append_uses_exact_rpc_names_and_normalizes_optional_text(monkeypatch: pytest.MonkeyPatch) -> None:
    received: dict[str, object] = {}
    def post(_url: str, **kwargs: object) -> Response:
        received.update(kwargs)
        return Response(200, [{"queue_id": "queue", "queue_item_id": "item", "outreach_item_id": "outreach", "queue_item_count": 1, "created_new_queue": False, "queue_status": "draft"}])
    monkeypatch.setattr(httpx, "post", post)
    storage = SupabaseAdmin("https://example.supabase.co", "service-role")
    result = storage.append_extension_processing_queue_item("00000000-0000-0000-0000-000000000001", {
        "linkedin_post_url": "https://www.linkedin.com/feed/update/1",
        "author_name": "Ada", "author_profile_url": " ", "linkedin_post_text": "Hiring",
        "job_description_url": "", "job_description_text": " ", "job_description_source": "unavailable",
        "capture_source": "browser_extension", "captured_at": "2026-07-19T00:00:00Z",
        "idempotency_key": "capture-12345678", "job_description_warning": "unsupported key",
    })
    assert result["queue_id"] == "queue"
    assert received["json"] == {"p_user_id": "00000000-0000-0000-0000-000000000001", "p_metadata": {
        "linkedin_post_url": "https://www.linkedin.com/feed/update/1", "author_name": "Ada", "author_profile_url": None,
        "linkedin_post_text": "Hiring", "job_description_url": None, "job_description_text": None,
        "job_description_source": "unavailable", "capture_source": "browser_extension", "captured_at": "2026-07-19T00:00:00Z", "idempotency_key": "capture-12345678",
    }}


@pytest.mark.parametrize("message", ["function public.append_extension_processing_queue_item(uuid, json) does not exist", "The active processing batch already contains 10 items"])
def test_append_surfaces_safe_supabase_400_detail(monkeypatch: pytest.MonkeyPatch, message: str) -> None:
    monkeypatch.setattr(httpx, "post", lambda *_args, **_kwargs: Response(400, {"message": message, "hint": "ignored"}))
    storage = SupabaseAdmin("https://example.supabase.co", "service-role")
    with pytest.raises(ExtensionQueueAppendError, match=re.escape(message)):
        storage.append_extension_processing_queue_item("00000000-0000-0000-0000-000000000001", {})


def test_append_rejects_malformed_success_response(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(httpx, "post", lambda *_args, **_kwargs: Response(200, []))
    with pytest.raises(ValueError, match="did not return"):
        SupabaseAdmin("https://example.supabase.co", "service-role").append_extension_processing_queue_item("00000000-0000-0000-0000-000000000001", {})


def test_orphan_repair_uses_uuid_jsonb_parameters_and_normalizes_list_response(monkeypatch: pytest.MonkeyPatch) -> None:
    received: dict[str, object] = {}
    def post(_url: str, **kwargs: object) -> Response:
        received.update(kwargs); return Response(200, [{"queue_id": "queue", "queue_item_id": "item"}])
    monkeypatch.setattr(httpx, "post", post)
    result = SupabaseAdmin("https://example.supabase.co", "service-role").repair_extension_orphan("00000000-0000-0000-0000-000000000001", "00000000-0000-0000-0000-000000000002", {"author_profile_url": ""})
    assert result == {"queue_id": "queue", "queue_item_id": "item"}
    assert received["json"] == {"p_user_id": "00000000-0000-0000-0000-000000000001", "p_outreach_item_id": "00000000-0000-0000-0000-000000000002", "p_metadata": {"linkedin_post_url": None, "author_name": None, "author_profile_url": None, "linkedin_post_text": None, "job_description_url": None, "job_description_text": None, "job_description_source": None, "capture_source": None, "captured_at": None, "idempotency_key": None}}


def test_orphan_repair_preserves_safe_400_body(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(httpx, "post", lambda *_args, **_kwargs: Response(400, {"message": "PGRST202 missing function"}))
    with pytest.raises(ExtensionOrphanRepairError, match="PGRST202 missing function"):
        SupabaseAdmin("https://example.supabase.co", "secret").repair_extension_orphan("00000000-0000-0000-0000-000000000001", "00000000-0000-0000-0000-000000000002", {})


def test_orphan_repair_empty_success_is_a_safe_fallback_signal(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(httpx, "post", lambda *_args, **_kwargs: Response(200, []))
    assert SupabaseAdmin("https://example.supabase.co", "secret").repair_extension_orphan("00000000-0000-0000-0000-000000000001", "00000000-0000-0000-0000-000000000002", {}) is None
