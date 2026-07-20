from collections.abc import Generator

from fastapi.testclient import TestClient

from auth import get_current_user
from main import app
from supabase_admin import get_supabase_admin


class DeleteStorage:
    def __init__(self) -> None:
        self.deleted: list[tuple[str, str]] = []

    def delete_outreach_item_permanently(self, user_id: str, item_id: str) -> bool:
        self.deleted.append((user_id, item_id))
        return item_id.endswith("001")


def test_outreach_delete_is_owned_and_returns_success() -> None:
    storage = DeleteStorage()
    app.dependency_overrides[get_current_user] = lambda: {"user_id": "user-a", "email": None}
    app.dependency_overrides[get_supabase_admin] = lambda: storage
    try:
        client = TestClient(app)
        response = client.delete("/api/v1/outreach-items/00000000-0000-0000-0000-000000000001")
        assert response.status_code == 200
        assert response.json() == {"deleted": True, "outreach_item_id": "00000000-0000-0000-0000-000000000001"}
        assert storage.deleted == [("user-a", "00000000-0000-0000-0000-000000000001")]
    finally:
        app.dependency_overrides.clear()


def test_outreach_delete_hides_missing_or_other_users_item() -> None:
    storage = DeleteStorage()
    app.dependency_overrides[get_current_user] = lambda: {"user_id": "user-a", "email": None}
    app.dependency_overrides[get_supabase_admin] = lambda: storage
    try:
        response = TestClient(app).delete("/api/v1/outreach-items/00000000-0000-0000-0000-000000000002")
        assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()
