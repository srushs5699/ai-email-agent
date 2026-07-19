import os
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any

import httpx
from fastapi import HTTPException, status

from gmail_connections import (
    GmailConnectionRecord,
    GmailConnectionUpsert,
    OAuthStateRecord,
)


class GmailPersistenceError(Exception):
    """A safe, token-free error returned by Gmail persistence operations."""


_SAFE_GMAIL_INVALIDATION_CODES = frozenset(
    {"access_denied", "authorization_required", "invalid_grant", "token_expired"}
)


class SupabaseAdmin:
    """Small backend-only client for private Storage and application rows."""

    def __init__(self, project_url: str, service_role_key: str) -> None:
        self._project_url = project_url.rstrip("/")
        self._headers = {
            "apikey": service_role_key,
            "Authorization": f"Bearer {service_role_key}",
        }

    @property
    def _private_headers(self) -> dict[str, str]:
        """Select the private PostgREST schema for Gmail credential records."""
        return {
            **self._headers,
            "Accept-Profile": "private",
            "Content-Profile": "private",
        }

    def upload_resume(self, storage_path: str, content: bytes) -> None:
        response = httpx.post(
            f"{self._project_url}/storage/v1/object/resumes/{storage_path}",
            content=content,
            headers={
                **self._headers,
                "Content-Type": "application/pdf",
                "x-upsert": "false",
            },
            timeout=30.0,
        )
        response.raise_for_status()

    def remove_resume(self, storage_path: str) -> None:
        response = httpx.request(
            "DELETE",
            f"{self._project_url}/storage/v1/object/resumes",
            json={"prefixes": [storage_path]},
            headers=self._headers,
            timeout=30.0,
        )
        response.raise_for_status()

    def insert_resume(self, record: dict[str, Any]) -> dict[str, Any]:
        response = httpx.post(
            f"{self._project_url}/rest/v1/resumes",
            json=record,
            headers={**self._headers, "Prefer": "return=representation"},
            timeout=30.0,
        )
        response.raise_for_status()
        rows = response.json()
        if not isinstance(rows, list) or not rows or not isinstance(rows[0], dict):
            raise ValueError("Supabase did not return the inserted resume.")
        return rows[0]

    def list_resumes(self, user_id: str) -> list[dict[str, Any]]:
        response = httpx.get(
            f"{self._project_url}/rest/v1/resumes",
            params={
                "select": "id,name,mime_type,file_size_bytes,parse_status,created_at",
                "user_id": f"eq.{user_id}",
                "order": "created_at.desc",
            },
            headers=self._headers,
            timeout=30.0,
        )
        response.raise_for_status()
        rows = response.json()
        if not isinstance(rows, list):
            raise ValueError("Supabase returned an invalid resume list.")
        return [row for row in rows if isinstance(row, dict)]

    def get_resume(self, resume_id: str, user_id: str) -> dict[str, Any] | None:
        response = httpx.get(
            f"{self._project_url}/rest/v1/resumes",
            params={
                "select": "id,user_id,name,storage_path,mime_type,file_size_bytes,"
                "extracted_text,parse_status",
                "id": f"eq.{resume_id}",
                "user_id": f"eq.{user_id}",
                "limit": "1",
            },
            headers=self._headers,
            timeout=30.0,
        )
        response.raise_for_status()
        rows = response.json()
        if not isinstance(rows, list) or not rows:
            return None
        return rows[0] if isinstance(rows[0], dict) else None

    def download_resume(self, storage_path: str) -> bytes:
        response = httpx.get(
            f"{self._project_url}/storage/v1/object/resumes/{storage_path}",
            headers=self._headers,
            timeout=30.0,
        )
        response.raise_for_status()
        return response.content

    def delete_resume(self, resume_id: str, user_id: str) -> dict[str, Any] | None:
        response = httpx.delete(
            f"{self._project_url}/rest/v1/resumes",
            params={"id": f"eq.{resume_id}", "user_id": f"eq.{user_id}"},
            headers={**self._headers, "Prefer": "return=representation"},
            timeout=30.0,
        )
        response.raise_for_status()
        rows = response.json()
        if not isinstance(rows, list) or not rows:
            return None
        return rows[0] if isinstance(rows[0], dict) else None

    def create_draft(
        self, outreach_item: dict[str, Any], draft: dict[str, Any]
    ) -> dict[str, Any]:
        outreach_response = httpx.post(
            f"{self._project_url}/rest/v1/outreach_items",
            json=outreach_item,
            headers={**self._headers, "Prefer": "return=representation"},
            timeout=30.0,
        )
        outreach_response.raise_for_status()
        outreach_rows = outreach_response.json()
        if (
            not isinstance(outreach_rows, list)
            or not outreach_rows
            or not isinstance(outreach_rows[0], dict)
        ):
            raise ValueError("Supabase did not return the outreach item.")
        draft["outreach_item_id"] = outreach_rows[0]["id"]
        draft_response = httpx.post(
            f"{self._project_url}/rest/v1/generated_drafts",
            json=draft,
            headers={**self._headers, "Prefer": "return=representation"},
            timeout=30.0,
        )
        draft_response.raise_for_status()
        rows = draft_response.json()
        if not isinstance(rows, list) or not rows or not isinstance(rows[0], dict):
            raise ValueError("Supabase did not return the draft.")
        return {**rows[0], "outreach_item": outreach_rows[0]}

    def get_draft(self, draft_id: str, user_id: str) -> dict[str, Any] | None:
        return self._get_drafts({"id": f"eq.{draft_id}", "user_id": f"eq.{user_id}"})

    def get_latest_draft(self, user_id: str) -> dict[str, Any] | None:
        return self._get_drafts(
            {
                "user_id": f"eq.{user_id}",
                "draft_status": "in.(draft,ready_for_review)",
                "order": "updated_at.desc",
            }
        )

    def _get_drafts(self, params: dict[str, str]) -> dict[str, Any] | None:
        response = httpx.get(
            f"{self._project_url}/rest/v1/generated_drafts",
            params={
                "select": "id,subject,body,draft_status,created_at,updated_at,"
                "gmail_draft_id,gmail_message_id,gmail_sync_status,"
                "gmail_sync_error_code,approval_status,approved_at,approved_content_hash,"
                "send_status,sent_at,gmail_sent_message_id,send_error_code,"
                "outreach_items!generated_drafts_outreach_item_same_owner_fkey(*)",
                "limit": "1",
                **params,
            },
            headers=self._headers,
            timeout=30.0,
        )
        response.raise_for_status()
        rows = response.json()
        if not isinstance(rows, list) or not rows or not isinstance(rows[0], dict):
            return None
        return rows[0]

    def update_draft(
        self, draft_id: str, user_id: str, update: dict[str, Any]
    ) -> dict[str, Any] | None:
        response = httpx.patch(
            f"{self._project_url}/rest/v1/generated_drafts",
            params={"id": f"eq.{draft_id}", "user_id": f"eq.{user_id}"},
            json=update,
            headers={**self._headers, "Prefer": "return=representation"},
            timeout=30.0,
        )
        response.raise_for_status()
        rows = response.json()
        if not isinstance(rows, list) or not rows or not isinstance(rows[0], dict):
            return None
        return rows[0]

    def update_draft_recipients(
        self, outreach_item_id: str, user_id: str, update: dict[str, Any]
    ) -> dict[str, Any] | None:
        response = httpx.patch(
            f"{self._project_url}/rest/v1/outreach_items",
            params={"id": f"eq.{outreach_item_id}", "user_id": f"eq.{user_id}"},
            json=update,
            headers={**self._headers, "Prefer": "return=representation"},
            timeout=30.0,
        )
        response.raise_for_status()
        rows = response.json()
        if not isinstance(rows, list) or not rows or not isinstance(rows[0], dict):
            return None
        return rows[0]

    def get_draft_for_gmail(self, draft_id: str, user_id: str) -> dict[str, Any] | None:
        response = httpx.get(
            f"{self._project_url}/rest/v1/generated_drafts",
            params={
                "select": "id,user_id,subject,body,gmail_draft_id,gmail_message_id,"
                "gmail_sync_status,approval_status,approved_at,approved_content_hash,send_status,sent_at,gmail_sent_message_id,send_error_code,outreach_items!"
                "generated_drafts_outreach_item_same_owner_fkey("
                "id,user_id,recipient_to,recipient_cc,selected_resume_id)",
                "id": f"eq.{draft_id}",
                "user_id": f"eq.{user_id}",
                "limit": "1",
            },
            headers=self._headers,
            timeout=30.0,
        )
        response.raise_for_status()
        rows = response.json()
        if not isinstance(rows, list) or not rows or not isinstance(rows[0], dict):
            return None
        return rows[0]

    def update_gmail_draft_sync(
        self, draft_id: str, user_id: str, update: dict[str, Any]
    ) -> dict[str, Any] | None:
        response = httpx.patch(
            f"{self._project_url}/rest/v1/generated_drafts",
            params={"id": f"eq.{draft_id}", "user_id": f"eq.{user_id}"},
            json=update,
            headers={**self._headers, "Prefer": "return=representation"},
            timeout=30.0,
        )
        response.raise_for_status()
        rows = response.json()
        if not isinstance(rows, list) or not rows or not isinstance(rows[0], dict):
            return None
        return rows[0]

    def claim_gmail_send(
        self, draft_id: str, user_id: str, content_hash: str
    ) -> dict[str, Any] | None:
        response = httpx.post(
            f"{self._project_url}/rest/v1/rpc/claim_approved_gmail_send",
            json={
                "p_draft_id": draft_id,
                "p_user_id": user_id,
                "p_content_hash": content_hash,
            },
            headers=self._headers,
            timeout=30.0,
        )
        response.raise_for_status()
        rows = response.json()
        if not isinstance(rows, list) or not rows or not isinstance(rows[0], dict):
            return None
        return rows[0]

    def finish_gmail_send(
        self, draft_id: str, user_id: str, gmail_message_id: str
    ) -> dict[str, Any] | None:
        return self.update_draft(
            draft_id,
            user_id,
            {
                "send_status": "sent",
                "sent_at": datetime.now(timezone.utc).isoformat(),
                "gmail_sent_message_id": gmail_message_id,
                "send_error_code": None,
                "draft_status": "sent",
            },
        )

    def fail_gmail_send(self, draft_id: str, user_id: str, error_code: str) -> None:
        self.update_draft(
            draft_id,
            user_id,
            {"send_status": "failed", "send_error_code": error_code},
        )

    def get_gmail_connection(self, user_id: str) -> GmailConnectionRecord | None:
        try:
            response = httpx.get(
                f"{self._project_url}/rest/v1/gmail_connections",
                params={
                    "select": "id,user_id,google_email,encrypted_refresh_token,"
                    "access_token,access_token_expires_at,granted_scopes,revoked_at,"
                    "created_at,updated_at",
                    "user_id": f"eq.{user_id}",
                    "limit": "1",
                },
                headers=self._private_headers,
                timeout=30.0,
            )
            response.raise_for_status()
            rows = response.json()
            if not isinstance(rows, list) or not rows:
                return None
            return _gmail_connection_record(rows[0])
        except (httpx.HTTPError, TypeError, ValueError, KeyError) as error:
            raise GmailPersistenceError("Gmail connection storage failed.") from error

    def upsert_gmail_connection(
        self, user_id: str, connection: GmailConnectionUpsert
    ) -> GmailConnectionRecord:
        try:
            existing = self.get_gmail_connection(user_id)
            encrypted_refresh_token = connection.encrypted_refresh_token
            if encrypted_refresh_token is None and existing is not None:
                encrypted_refresh_token = existing.encrypted_refresh_token
            if encrypted_refresh_token is None:
                raise ValueError("A refresh token is required for a new connection.")
            record = {
                "user_id": user_id,
                "google_email": (
                    connection.google_email
                    if connection.google_email is not None
                    else (existing.google_email if existing is not None else None)
                ),
                "encrypted_refresh_token": encrypted_refresh_token,
                "access_token": (
                    connection.access_token
                    if connection.access_token is not None
                    else (existing.access_token if existing is not None else None)
                ),
                "access_token_expires_at": _timestamp_value(
                    connection.access_token_expires_at
                    if connection.access_token_expires_at is not None
                    else (
                        existing.access_token_expires_at
                        if existing is not None
                        else None
                    )
                ),
                "granted_scopes": list(
                    connection.granted_scopes
                    if connection.granted_scopes is not None
                    else (existing.granted_scopes if existing is not None else ())
                ),
                "revoked_at": None,
            }
            response = httpx.post(
                f"{self._project_url}/rest/v1/gmail_connections",
                params={"on_conflict": "user_id"},
                json=record,
                headers={
                    **self._private_headers,
                    "Prefer": "resolution=merge-duplicates,return=representation",
                },
                timeout=30.0,
            )
            response.raise_for_status()
            rows = response.json()
            if not isinstance(rows, list) or not rows:
                raise ValueError("Supabase did not return a Gmail connection.")
            return _gmail_connection_record(rows[0])
        except GmailPersistenceError:
            raise
        except (httpx.HTTPError, TypeError, ValueError, KeyError) as error:
            raise GmailPersistenceError("Gmail connection storage failed.") from error

    def mark_gmail_connection_invalid(self, user_id: str, reason_code: str) -> None:
        if reason_code not in _SAFE_GMAIL_INVALIDATION_CODES:
            raise GmailPersistenceError("Gmail connection storage failed.")
        try:
            response = httpx.patch(
                f"{self._project_url}/rest/v1/gmail_connections",
                params={"user_id": f"eq.{user_id}"},
                json={"revoked_at": _timestamp_value(datetime.now(timezone.utc))},
                headers=self._private_headers,
                timeout=30.0,
            )
            response.raise_for_status()
        except httpx.HTTPError as error:
            raise GmailPersistenceError("Gmail connection storage failed.") from error

    def update_gmail_access_token_metadata(
        self, user_id: str, access_token: str | None, expires_at: datetime | None
    ) -> GmailConnectionRecord | None:
        try:
            response = httpx.patch(
                f"{self._project_url}/rest/v1/gmail_connections",
                params={"user_id": f"eq.{user_id}"},
                json={
                    "access_token": access_token,
                    "access_token_expires_at": _timestamp_value(expires_at),
                },
                headers={
                    **self._private_headers,
                    "Prefer": "return=representation",
                },
                timeout=30.0,
            )
            response.raise_for_status()
            rows = response.json()
            if not isinstance(rows, list) or not rows:
                return None
            return _gmail_connection_record(rows[0])
        except (httpx.HTTPError, TypeError, ValueError, KeyError) as error:
            raise GmailPersistenceError("Gmail connection storage failed.") from error

    def create_gmail_oauth_state(
        self, user_id: str, state: str, expires_at: datetime
    ) -> OAuthStateRecord:
        try:
            response = httpx.post(
                f"{self._project_url}/rest/v1/gmail_oauth_states",
                json={
                    "state_hash": _oauth_state_hash(state),
                    "user_id": user_id,
                    "expires_at": _timestamp_value(expires_at),
                },
                headers={
                    **self._private_headers,
                    "Prefer": "return=representation",
                },
                timeout=30.0,
            )
            response.raise_for_status()
            rows = response.json()
            if not isinstance(rows, list) or not rows:
                raise ValueError("Supabase did not return an OAuth state.")
            return _oauth_state_record(rows[0])
        except (httpx.HTTPError, TypeError, ValueError, KeyError) as error:
            raise GmailPersistenceError("Gmail OAuth state storage failed.") from error

    def consume_gmail_oauth_state(
        self, state: str, expected_user_id: str | None = None
    ) -> OAuthStateRecord | None:
        """Atomically delete a matching, unexpired state and return it once."""
        try:
            response = httpx.delete(
                f"{self._project_url}/rest/v1/gmail_oauth_states",
                params={
                    "state_hash": f"eq.{_oauth_state_hash(state)}",
                    "expires_at": f"gt.{_timestamp_value(datetime.now(timezone.utc))}",
                    **(
                        {"user_id": f"eq.{expected_user_id}"}
                        if expected_user_id is not None
                        else {}
                    ),
                },
                headers={
                    **self._private_headers,
                    "Prefer": "return=representation",
                },
                timeout=30.0,
            )
            response.raise_for_status()
            rows = response.json()
            if not isinstance(rows, list) or not rows:
                return None
            return _oauth_state_record(rows[0])
        except (httpx.HTTPError, TypeError, ValueError, KeyError) as error:
            raise GmailPersistenceError("Gmail OAuth state storage failed.") from error

    def delete_expired_gmail_oauth_states(self, now: datetime) -> int:
        try:
            response = httpx.delete(
                f"{self._project_url}/rest/v1/gmail_oauth_states",
                params={"expires_at": f"lt.{_timestamp_value(now)}"},
                headers={
                    **self._private_headers,
                    "Prefer": "return=representation",
                },
                timeout=30.0,
            )
            response.raise_for_status()
            rows = response.json()
            if not isinstance(rows, list):
                raise ValueError("Supabase returned invalid OAuth state rows.")
            return len(rows)
        except (httpx.HTTPError, ValueError) as error:
            raise GmailPersistenceError("Gmail OAuth state storage failed.") from error


def _timestamp_value(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _parse_timestamp(value: object) -> datetime:
    if not isinstance(value, str):
        raise ValueError("Expected timestamp.")
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _gmail_connection_record(value: object) -> GmailConnectionRecord:
    if not isinstance(value, dict):
        raise ValueError("Expected Gmail connection record.")
    scopes = value["granted_scopes"]
    if not isinstance(scopes, list) or not all(
        isinstance(scope, str) for scope in scopes
    ):
        raise ValueError("Expected Gmail scopes.")
    return GmailConnectionRecord(
        id=str(value["id"]),
        user_id=str(value["user_id"]),
        google_email=(
            value["google_email"] if isinstance(value["google_email"], str) else None
        ),
        encrypted_refresh_token=str(value["encrypted_refresh_token"]),
        access_token=(
            value["access_token"] if isinstance(value["access_token"], str) else None
        ),
        access_token_expires_at=(
            _parse_timestamp(value["access_token_expires_at"])
            if value["access_token_expires_at"] is not None
            else None
        ),
        granted_scopes=tuple(scopes),
        revoked_at=(
            _parse_timestamp(value["revoked_at"]) if value["revoked_at"] else None
        ),
        created_at=_parse_timestamp(value["created_at"]),
        updated_at=_parse_timestamp(value["updated_at"]),
    )


def _oauth_state_hash(state: str) -> str:
    return sha256(state.encode()).hexdigest()


def _oauth_state_record(value: object) -> OAuthStateRecord:
    if not isinstance(value, dict):
        raise ValueError("Expected OAuth state record.")
    return OAuthStateRecord(
        state_hash=str(value["state_hash"]),
        user_id=str(value["user_id"]),
        expires_at=_parse_timestamp(value["expires_at"]),
        created_at=_parse_timestamp(value["created_at"]),
    )


def get_supabase_admin() -> SupabaseAdmin:
    project_url = os.getenv("SUPABASE_URL")
    service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not project_url or not service_role_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Resume storage is not configured.",
        )
    return SupabaseAdmin(project_url, service_role_key)
