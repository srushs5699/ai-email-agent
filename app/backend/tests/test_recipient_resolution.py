from typing import Any

import httpx
import pytest

from supabase_admin import SupabaseAdmin


class Response:
    status_code = 200
    headers: dict[str, str] = {"content-type": "application/json"}
    history: list[object] = []
    text = "[]"

    def raise_for_status(self) -> None:
        return None

    def json(self) -> list[object]:
        return []


def test_duplicate_lookup_uses_the_unambiguous_outreach_relationship(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    def get(url: str, **kwargs: Any) -> Response:
        captured["url"] = url
        captured["params"] = kwargs["params"]
        return Response()

    monkeypatch.setattr(httpx, "get", get)
    storage = SupabaseAdmin("https://project.supabase.co", "service-role")

    result = storage.find_active_duplicate_draft(
        "user-1", "recipient@example.com", "https://www.linkedin.com/posts/1"
    )

    assert result is None
    assert captured["url"] == "https://project.supabase.co/rest/v1/generated_drafts"
    assert (
        "generated_drafts_outreach_item_same_owner_fkey" in captured["params"]["select"]
    )


def test_duplicate_lookup_skips_the_request_without_a_linkedin_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(*_: object, **__: object) -> None:
        raise AssertionError("No duplicate lookup should be requested.")

    monkeypatch.setattr(httpx, "get", fail)
    storage = SupabaseAdmin("https://project.supabase.co", "service-role")

    assert (
        storage.find_active_duplicate_draft("user-1", "recipient@example.com", None)
        is None
    )
