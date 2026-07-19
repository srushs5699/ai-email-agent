from datetime import datetime, timedelta, timezone
from hashlib import sha256

import httpx
import pytest

from gmail_connections import GmailConnectionRecord, GmailConnectionUpsert
from supabase_admin import GmailPersistenceError, SupabaseAdmin

USER_A = "00000000-0000-0000-0000-000000000001"
USER_B = "00000000-0000-0000-0000-000000000002"
RAW_REFRESH_TOKEN = "google-refresh-token"
ENCRYPTED_REFRESH_TOKEN = "encrypted-refresh-token"
RAW_STATE = "browser-state-value"
NOW = datetime(2026, 7, 19, tzinfo=timezone.utc)


def connection_row(**changes: object) -> dict[str, object]:
    return {
        "id": "00000000-0000-0000-0000-000000000003",
        "user_id": USER_A,
        "google_email": "person@example.com",
        "encrypted_refresh_token": ENCRYPTED_REFRESH_TOKEN,
        "access_token": "short-lived-access-token",
        "access_token_expires_at": "2026-07-19T01:00:00+00:00",
        "granted_scopes": ["https://www.googleapis.com/auth/gmail.compose"],
        "revoked_at": None,
        "created_at": "2026-07-19T00:00:00+00:00",
        "updated_at": "2026-07-19T00:00:00+00:00",
        **changes,
    }


def oauth_state_row(**changes: object) -> dict[str, object]:
    return {
        "state_hash": sha256(RAW_STATE.encode()).hexdigest(),
        "user_id": USER_A,
        "expires_at": "2026-07-20T00:00:00+00:00",
        "created_at": "2026-07-19T00:00:00+00:00",
        **changes,
    }


@pytest.fixture
def admin() -> SupabaseAdmin:
    return SupabaseAdmin("https://project.supabase.co", "service-role-key")


def response(request: httpx.Request, rows: list[dict[str, object]]) -> httpx.Response:
    return httpx.Response(200, request=request, json=rows)


def test_connection_lookup_is_scoped_to_user_id(
    admin: SupabaseAdmin, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fake_get(url: str, **kwargs: object) -> httpx.Response:
        assert url.endswith("/rest/v1/gmail_connections")
        params = kwargs["params"]
        assert isinstance(params, dict)
        assert params["user_id"] == f"eq.{USER_A}"
        headers = kwargs["headers"]
        assert isinstance(headers, dict)
        assert headers["Accept-Profile"] == "private"
        assert headers["Content-Profile"] == "private"
        request = httpx.Request("GET", url)
        return response(request, [connection_row()])

    monkeypatch.setattr("supabase_admin.httpx.get", fake_get)

    assert admin.get_gmail_connection(USER_A).user_id == USER_A  # type: ignore[union-attr]


def test_gmail_oauth_state_queries_target_private_schema(
    admin: SupabaseAdmin, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fake_post(url: str, **kwargs: object) -> httpx.Response:
        assert url.endswith("/rest/v1/gmail_oauth_states")
        headers = kwargs["headers"]
        assert isinstance(headers, dict)
        assert headers["Accept-Profile"] == "private"
        assert headers["Content-Profile"] == "private"
        return response(httpx.Request("POST", url), [oauth_state_row()])

    monkeypatch.setattr("supabase_admin.httpx.post", fake_post)

    admin.create_gmail_oauth_state(USER_A, RAW_STATE, NOW + timedelta(minutes=10))


def test_generated_draft_query_remains_in_the_public_schema(
    admin: SupabaseAdmin, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fake_get(url: str, **kwargs: object) -> httpx.Response:
        assert url.endswith("/rest/v1/generated_drafts")
        headers = kwargs["headers"]
        assert isinstance(headers, dict)
        assert "Accept-Profile" not in headers
        assert "Content-Profile" not in headers
        return response(httpx.Request("GET", url), [])

    monkeypatch.setattr("supabase_admin.httpx.get", fake_get)

    assert admin.get_draft("draft-id", USER_A) is None


def test_missing_connection_returns_none(
    admin: SupabaseAdmin, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "supabase_admin.httpx.get",
        lambda url, **kwargs: response(httpx.Request("GET", url), []),
    )

    assert admin.get_gmail_connection(USER_A) is None


def test_upsert_does_not_encrypt_data(
    admin: SupabaseAdmin, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(admin, "get_gmail_connection", lambda user_id: None)
    sent: dict[str, object] = {}

    def fake_post(url: str, **kwargs: object) -> httpx.Response:
        sent.update(kwargs["json"] if isinstance(kwargs["json"], dict) else {})
        return response(httpx.Request("POST", url), [connection_row()])

    monkeypatch.setattr("supabase_admin.httpx.post", fake_post)

    admin.upsert_gmail_connection(
        USER_A,
        GmailConnectionUpsert(encrypted_refresh_token=RAW_REFRESH_TOKEN),
    )

    assert sent["encrypted_refresh_token"] == RAW_REFRESH_TOKEN


def test_upsert_preserves_existing_refresh_token_when_omitted(
    admin: SupabaseAdmin, monkeypatch: pytest.MonkeyPatch
) -> None:
    existing = admin_connection()
    monkeypatch.setattr(admin, "get_gmail_connection", lambda user_id: existing)
    sent: dict[str, object] = {}
    monkeypatch.setattr(
        "supabase_admin.httpx.post",
        lambda url, **kwargs: (
            sent.update(kwargs["json"] if isinstance(kwargs["json"], dict) else {})
            or response(httpx.Request("POST", url), [connection_row()])
        ),
    )

    admin.upsert_gmail_connection(USER_A, GmailConnectionUpsert())

    assert sent["encrypted_refresh_token"] == ENCRYPTED_REFRESH_TOKEN


def test_upsert_replaces_refresh_token_when_supplied(
    admin: SupabaseAdmin, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        admin, "get_gmail_connection", lambda user_id: admin_connection()
    )
    sent: dict[str, object] = {}
    monkeypatch.setattr(
        "supabase_admin.httpx.post",
        lambda url, **kwargs: (
            sent.update(kwargs["json"] if isinstance(kwargs["json"], dict) else {})
            or response(httpx.Request("POST", url), [connection_row()])
        ),
    )

    admin.upsert_gmail_connection(
        USER_A, GmailConnectionUpsert(encrypted_refresh_token="new-encrypted-token")
    )

    assert sent["encrypted_refresh_token"] == "new-encrypted-token"


def test_marking_connection_invalid_accepts_only_safe_codes(
    admin: SupabaseAdmin, monkeypatch: pytest.MonkeyPatch
) -> None:
    sent: dict[str, object] = {}
    monkeypatch.setattr(
        "supabase_admin.httpx.patch",
        lambda url, **kwargs: (
            sent.update(kwargs["json"] if isinstance(kwargs["json"], dict) else {})
            or response(httpx.Request("PATCH", url), [])
        ),
    )

    admin.mark_gmail_connection_invalid(USER_A, "invalid_grant")

    assert set(sent) == {"revoked_at"}
    with pytest.raises(GmailPersistenceError, match="Gmail connection storage failed"):
        admin.mark_gmail_connection_invalid(USER_A, "raw Google error: token=secret")


def test_updates_access_token_expiry_metadata(
    admin: SupabaseAdmin, monkeypatch: pytest.MonkeyPatch
) -> None:
    sent: dict[str, object] = {}
    monkeypatch.setattr(
        "supabase_admin.httpx.patch",
        lambda url, **kwargs: (
            sent.update(kwargs["json"] if isinstance(kwargs["json"], dict) else {})
            or response(httpx.Request("PATCH", url), [connection_row()])
        ),
    )

    admin.update_gmail_access_token_metadata(USER_A, "updated-access", NOW)

    assert sent == {
        "access_token": "updated-access",
        "access_token_expires_at": NOW.isoformat(),
    }


def test_oauth_state_creation_hashes_browser_state(
    admin: SupabaseAdmin, monkeypatch: pytest.MonkeyPatch
) -> None:
    sent: dict[str, object] = {}
    monkeypatch.setattr(
        "supabase_admin.httpx.post",
        lambda url, **kwargs: (
            sent.update(kwargs["json"] if isinstance(kwargs["json"], dict) else {})
            or response(httpx.Request("POST", url), [oauth_state_row()])
        ),
    )

    admin.create_gmail_oauth_state(USER_A, RAW_STATE, NOW + timedelta(minutes=10))

    assert sent["state_hash"] == sha256(RAW_STATE.encode()).hexdigest()
    assert RAW_STATE not in sent.values()


def test_valid_oauth_state_is_consumed_once(
    admin: SupabaseAdmin, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = 0

    def fake_delete(url: str, **kwargs: object) -> httpx.Response:
        nonlocal calls
        calls += 1
        rows = [oauth_state_row()] if calls == 1 else []
        return response(httpx.Request("DELETE", url), rows)

    monkeypatch.setattr("supabase_admin.httpx.delete", fake_delete)

    assert admin.consume_gmail_oauth_state(RAW_STATE, USER_A) is not None
    assert admin.consume_gmail_oauth_state(RAW_STATE, USER_A) is None


def test_expired_oauth_state_is_rejected(
    admin: SupabaseAdmin, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fake_delete(url: str, **kwargs: object) -> httpx.Response:
        params = kwargs["params"]
        assert isinstance(params, dict)
        assert str(params["expires_at"]).startswith("gt.")
        return response(httpx.Request("DELETE", url), [])

    monkeypatch.setattr("supabase_admin.httpx.delete", fake_delete)

    assert admin.consume_gmail_oauth_state(RAW_STATE, USER_A) is None


def test_cross_user_oauth_state_is_rejected(
    admin: SupabaseAdmin, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fake_delete(url: str, **kwargs: object) -> httpx.Response:
        params = kwargs["params"]
        assert isinstance(params, dict)
        assert params["user_id"] == f"eq.{USER_B}"
        return response(httpx.Request("DELETE", url), [])

    monkeypatch.setattr("supabase_admin.httpx.delete", fake_delete)

    assert admin.consume_gmail_oauth_state(RAW_STATE, USER_B) is None


def test_database_errors_are_safe_and_never_include_token_values(
    admin: SupabaseAdmin,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    request = httpx.Request(
        "POST", "https://project.supabase.co/rest/v1/gmail_connections"
    )
    response_error = httpx.Response(
        500,
        request=request,
        json={"message": f"upstream failure {RAW_REFRESH_TOKEN}"},
    )

    monkeypatch.setattr(admin, "get_gmail_connection", lambda user_id: None)
    monkeypatch.setattr(
        "supabase_admin.httpx.post",
        lambda url, **kwargs: (_ for _ in ()).throw(
            httpx.HTTPStatusError("failed", request=request, response=response_error)
        ),
    )

    with pytest.raises(GmailPersistenceError) as raised:
        admin.upsert_gmail_connection(
            USER_A, GmailConnectionUpsert(encrypted_refresh_token=RAW_REFRESH_TOKEN)
        )

    assert RAW_REFRESH_TOKEN not in str(raised.value)
    assert RAW_REFRESH_TOKEN not in caplog.text


def admin_connection() -> GmailConnectionRecord:
    """Build a parsed record through the public lookup path's row format."""
    from supabase_admin import _gmail_connection_record

    return _gmail_connection_record(connection_row())
