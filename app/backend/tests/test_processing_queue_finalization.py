from typing import Any

import httpx

from supabase_admin import SupabaseAdmin


class Response:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows

    def raise_for_status(self) -> None:
        return None

    def json(self) -> list[dict[str, Any]]:
        return self.rows


def queue(status: str, item_statuses: list[str]) -> dict[str, Any]:
    return {
        "id": "queue-1", "status": status,
        "processing_queue_items": [{"status": value} for value in item_statuses],
    }


def test_terminal_items_finalize_a_running_queue(monkeypatch: Any) -> None:
    storage = SupabaseAdmin("https://example.test", "key")
    current = queue("running", ["completed", "failed"])
    monkeypatch.setattr(storage, "_queue", lambda *_: current)
    calls: list[dict[str, Any]] = []

    def patch(*_args: Any, **kwargs: Any) -> Response:
        calls.append(kwargs)
        return Response([{}])

    monkeypatch.setattr(httpx, "patch", patch)

    storage.finalize_processing_queue_if_done("queue-1", "user-1")

    assert calls[0]["json"]["status"] == "completed_with_failures"
    assert calls[0]["json"]["completed_items"] == 1
    assert calls[0]["json"]["failed_items"] == 1


def test_pending_or_processing_items_remain_active(monkeypatch: Any) -> None:
    storage = SupabaseAdmin("https://example.test", "key")
    active = queue("running", ["completed", "processing"])
    monkeypatch.setattr(storage, "_queue", lambda *_: active)

    def patch(*_args: Any, **_kwargs: Any) -> Response:
        raise AssertionError("An active queue must not be finalized.")

    monkeypatch.setattr(httpx, "patch", patch)

    result = storage.finalize_processing_queue_if_done("queue-1", "user-1")

    assert result is not None
    assert result["status"] == "running"
