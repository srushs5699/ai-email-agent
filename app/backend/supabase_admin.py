import os
from typing import Any

import httpx
from fastapi import HTTPException, status


class SupabaseAdmin:
    """Small backend-only client for private Storage and application rows."""

    def __init__(self, project_url: str, service_role_key: str) -> None:
        self._project_url = project_url.rstrip("/")
        self._headers = {
            "apikey": service_role_key,
            "Authorization": f"Bearer {service_role_key}",
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
                "select": "id,user_id,name,storage_path,extracted_text,parse_status",
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


def get_supabase_admin() -> SupabaseAdmin:
    project_url = os.getenv("SUPABASE_URL")
    service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not project_url or not service_role_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Resume storage is not configured.",
        )
    return SupabaseAdmin(project_url, service_role_key)
