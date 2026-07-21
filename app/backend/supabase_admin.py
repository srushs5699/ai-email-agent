# ruff: noqa: E501, E701, E702
import logging
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

logger = logging.getLogger(__name__)


class GmailPersistenceError(Exception):
    """A safe, token-free error returned by Gmail persistence operations."""


class ExtensionQueueAppendError(Exception):
    """A safe PostgREST error for a failed extension queue append."""


class ExtensionOrphanRepairError(Exception):
    """A safe PostgREST error for an orphan-repair RPC rejection."""


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

    def find_active_duplicate_draft(
        self, user_id: str, recipient_to: str, linkedin_post_url: str | None
    ) -> dict[str, Any] | None:
        if not linkedin_post_url:
            return None
        endpoint = f"{self._project_url}/rest/v1/generated_drafts"
        logger.info(
            "recipient_resolution_started provider=supabase_postgrest method=GET url=%s",
            endpoint,
        )
        response = httpx.get(
            endpoint,
            params={
                "select": (
                    "id,outreach_items!generated_drafts_outreach_item_same_owner_fkey!inner("
                    "recipient_to,linkedin_post_url)"
                ),
                "user_id": f"eq.{user_id}",
                "draft_status": "in.(draft,ready_for_review,sent)",
                "outreach_items.recipient_to": f"eq.{recipient_to}",
                "outreach_items.linkedin_post_url": f"eq.{linkedin_post_url}",
                "limit": "1",
            },
            headers=self._headers,
            timeout=30.0,
        )
        logger.info(
            "recipient_resolution_response provider=supabase_postgrest status_code=%s "
            "location=%s content_type=%s redirect_history=%s response_preview=%s",
            response.status_code,
            response.headers.get("location"),
            response.headers.get("content-type"),
            len(response.history),
            response.text[:500] if not 200 <= response.status_code < 300 else "",
        )
        response.raise_for_status()
        rows = response.json()
        return (
            rows[0]
            if isinstance(rows, list) and rows and isinstance(rows[0], dict)
            else None
        )

    def get_latest_draft(self, user_id: str) -> dict[str, Any] | None:
        return self._get_drafts(
            {
                "user_id": f"eq.{user_id}",
                "draft_status": "in.(draft,ready_for_review)",
                "order": "updated_at.desc",
            }
        )

    def list_review_drafts(self, user_id: str) -> list[dict[str, Any]]:
        response = httpx.get(
            f"{self._project_url}/rest/v1/generated_drafts",
            params={
                "select": "id,subject,body,draft_status,created_at,updated_at,"
                "gmail_draft_id,gmail_message_id,gmail_sync_status,"
                "gmail_sync_error_code,approval_status,approved_at,send_status,"
                "sent_at,gmail_sent_message_id,send_error_code,"
                "outreach_items!generated_drafts_outreach_item_same_owner_fkey(*)",
                "user_id": f"eq.{user_id}",
                "draft_status": "in.(draft,ready_for_review)",
                "send_status": "neq.sent",
                "order": "updated_at.desc",
            },
            headers=self._headers,
            timeout=30.0,
        )
        response.raise_for_status()
        rows = response.json()
        if not isinstance(rows, list):
            raise ValueError("Supabase returned an invalid draft list.")
        return [row for row in rows if isinstance(row, dict)]

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

    def _queue(self, queue_id: str, user_id: str) -> dict[str, Any] | None:
        response = httpx.get(
            f"{self._project_url}/rest/v1/processing_queues",
            params={
                "select": "*,processing_queue_items(*)",
                "id": f"eq.{queue_id}",
                "user_id": f"eq.{user_id}",
                "order": "created_at.desc",
                "processing_queue_items.order": "position.asc",
                "limit": "1",
            },
            headers=self._headers,
            timeout=30.0,
        )
        response.raise_for_status()
        rows = response.json()
        return (
            rows[0]
            if isinstance(rows, list) and rows and isinstance(rows[0], dict)
            else None
        )

    def create_processing_queue(
        self, user_id: str, items: list[dict[str, Any]]
    ) -> dict[str, Any]:
        response = httpx.post(
            f"{self._project_url}/rest/v1/processing_queues",
            json={"user_id": user_id, "total_items": len(items)},
            headers={**self._headers, "Prefer": "return=representation"},
            timeout=30.0,
        )
        response.raise_for_status()
        queues = response.json()
        if not isinstance(queues, list) or not queues:
            raise ValueError("Supabase did not return the queue.")
        queue = queues[0]
        rows = [
            {
                "queue_id": queue["id"],
                "user_id": user_id,
                "position": position,
                "input_payload": item,
            }
            for position, item in enumerate(items)
        ]
        item_response = httpx.post(
            f"{self._project_url}/rest/v1/processing_queue_items",
            json=rows,
            headers={**self._headers, "Prefer": "return=representation"},
            timeout=30.0,
        )
        item_response.raise_for_status()
        return self._queue(queue["id"], user_id) or queue

    def find_extension_duplicate(
        self, user_id: str, linkedin_post_url: str
    ) -> dict[str, Any] | None:
        response = httpx.get(
            f"{self._project_url}/rest/v1/processing_queue_items",
            params={
                "select": "id,queue_id,outreach_item_id,status,failure_status,hidden_at",
                "user_id": f"eq.{user_id}",
                "source_linkedin_post_url": f"eq.{linkedin_post_url}",
                "status": "neq.failed",
                "failure_status": "is.null",
                "hidden_at": "is.null",
                "limit": "1",
            },
            headers=self._headers,
            timeout=30.0,
        )
        response.raise_for_status()
        rows = response.json()
        if isinstance(rows, list) and rows and isinstance(rows[0], dict):
            item = rows[0]
            queue = self.get_processing_queue(str(item["queue_id"]), user_id)
            queue_status = queue.get("status") if queue else None
            item["record_type"] = (
                "failed_task"
                if item.get("status") == "failed" or item.get("failure_status")
                else "processing_queue_item"
            )
            item["location"] = (
                "Failed Tasks"
                if item["record_type"] == "failed_task"
                else (
                    "Already completed"
                    if queue_status in {"completed", "completed_with_failures"}
                    else "Already in Processing Queue"
                )
            )
            item["queue_status"] = queue_status
            item["open_path"] = (
                "/failed-tasks"
                if item["record_type"] == "failed_task"
                else f"/processing-queue?queueId={item['queue_id']}"
            )
            return item

        # A captured outreach without a queue item is an interrupted import, not
        # a visible duplicate.  Generation history makes it a real review/sent
        # duplicate; otherwise callers repair it through the RPC below.
        outreach = httpx.get(
            f"{self._project_url}/rest/v1/outreach_items",
            params={
                "select": "id,status",
                "user_id": f"eq.{user_id}",
                "linkedin_post_url": f"eq.{linkedin_post_url}",
                "limit": "1",
            },
            headers=self._headers,
            timeout=30.0,
        )
        outreach.raise_for_status()
        outreach_rows = outreach.json()
        if (
            not isinstance(outreach_rows, list)
            or not outreach_rows
            or not isinstance(outreach_rows[0], dict)
        ):
            return None
        record = outreach_rows[0]
        drafts = httpx.get(
            f"{self._project_url}/rest/v1/generated_drafts",
            params={
                "select": "id,draft_status",
                "user_id": f"eq.{user_id}",
                "outreach_item_id": f"eq.{record['id']}",
                "limit": "1",
            },
            headers=self._headers,
            timeout=30.0,
        )
        drafts.raise_for_status()
        draft_rows = drafts.json()
        if (
            isinstance(draft_rows, list)
            and draft_rows
            and isinstance(draft_rows[0], dict)
        ):
            draft = draft_rows[0]
            location = (
                "Already completed"
                if draft.get("draft_status") == "sent"
                else "Already in Review Queue"
            )
            return {
                "id": draft["id"],
                "outreach_item_id": record["id"],
                "record_type": "review_item",
                "location": location,
                "open_path": "/review-queue",
            }
        return {
            "id": record["id"],
            "outreach_item_id": record["id"],
            "record_type": "orphaned_outreach",
            "location": "orphaned outreach",
        }

    def repair_extension_orphan(
        self, user_id: str, outreach_item_id: str, metadata: dict[str, object]
    ) -> dict[str, Any] | None:
        payload = {
            "p_user_id": user_id,
            "p_outreach_item_id": outreach_item_id,
            "p_metadata": self._extension_queue_metadata(metadata),
        }
        response = httpx.post(
            f"{self._project_url}/rest/v1/rpc/repair_extension_orphaned_outreach",
            json=payload,
            headers=self._headers,
            timeout=30.0,
        )
        if response.is_error:
            try:
                body = response.json()
            except ValueError:
                body = response.text
            detail = body.get("message", body) if isinstance(body, dict) else body
            raise ExtensionOrphanRepairError(
                f"repair extension orphan rejected ({response.status_code}): {str(detail)[:500]}"
            )
        rows = response.json()
        if isinstance(rows, dict):
            return rows if rows.get("queue_id") and rows.get("queue_item_id") else None
        if not isinstance(rows, list) or not rows or not isinstance(rows[0], dict):
            return None
        row = rows[0]
        return row if row.get("queue_id") and row.get("queue_item_id") else None

    @staticmethod
    def _extension_queue_metadata(
        metadata: dict[str, object],
    ) -> dict[str, object | None]:
        """Keep the JSONB RPC contract small and make nullable text explicit."""
        nullable = {
            "author_profile_url",
            "job_description_url",
            "job_description_text",
        }
        allowed = {
            "linkedin_post_url",
            "author_name",
            "author_profile_url",
            "linkedin_post_text",
            "job_description_url",
            "job_description_text",
            "job_description_source",
            "capture_source",
            "captured_at",
            "idempotency_key",
        }
        payload: dict[str, object | None] = {}
        for key in allowed:
            value = metadata.get(key)
            payload[key] = (
                None
                if key in nullable and isinstance(value, str) and not value.strip()
                else value
            )
        return payload

    @staticmethod
    def _extension_append_error(response: httpx.Response) -> ExtensionQueueAppendError:
        try:
            body = response.json()
        except ValueError:
            body = response.text
        if isinstance(body, dict):
            detail = (
                body.get("message")
                or body.get("details")
                or body.get("hint")
                or "Supabase rejected the queue append."
            )
        else:
            detail = str(body) or "Supabase rejected the queue append."
        return ExtensionQueueAppendError(
            f"Processing Queue append was rejected ({response.status_code}): {str(detail)[:500]}"
        )

    def append_extension_processing_queue_item(
        self, user_id: str, metadata: dict[str, object]
    ) -> dict[str, Any]:
        response = httpx.post(
            f"{self._project_url}/rest/v1/rpc/append_extension_processing_queue_item",
            json={
                "p_user_id": user_id,
                "p_metadata": self._extension_queue_metadata(metadata),
            },
            headers=self._headers,
            timeout=30.0,
        )
        if response.is_error:
            raise self._extension_append_error(response)
        rows = response.json()
        if not isinstance(rows, list) or not rows or not isinstance(rows[0], dict):
            raise ValueError("Supabase did not return the imported queue item.")
        return rows[0]

    def create_extension_failed_task(
        self, user_id: str, metadata: dict[str, object], reason: str, stage: str
    ) -> dict[str, Any]:
        response = httpx.post(
            f"{self._project_url}/rest/v1/rpc/create_extension_failed_task",
            json={
                "p_user_id": user_id,
                "p_metadata": metadata,
                "p_reason": reason,
                "p_stage": stage,
            },
            headers=self._headers,
            timeout=30.0,
        )
        response.raise_for_status()
        rows = response.json()
        if not isinstance(rows, list) or not rows or not isinstance(rows[0], dict):
            raise ValueError("Supabase did not return the failed import.")
        return rows[0]

    def get_processing_queue(
        self, queue_id: str, user_id: str
    ) -> dict[str, Any] | None:
        return self._queue(queue_id, user_id)

    def list_processing_queues(self, user_id: str) -> list[dict[str, Any]]:
        """Return every user-owned queue so active work and history stay visible."""
        response = httpx.get(
            f"{self._project_url}/rest/v1/processing_queues",
            params={
                "select": "*,processing_queue_items(*)",
                "user_id": f"eq.{user_id}",
                "order": "updated_at.desc",
                "processing_queue_items.order": "position.asc",
            },
            headers=self._headers,
            timeout=30.0,
        )
        response.raise_for_status()
        rows = response.json()
        records = (
            [row for row in rows if isinstance(row, dict)]
            if isinstance(rows, list)
            else []
        )
        return [
            self.finalize_processing_queue_if_done(str(record["id"]), user_id) or record
            for record in records
        ]

    def get_active_processing_queue(self, user_id: str) -> dict[str, Any] | None:
        response = httpx.get(
            f"{self._project_url}/rest/v1/processing_queues",
            params={
                "select": "*,processing_queue_items(*)",
                "user_id": f"eq.{user_id}",
                "status": "in.(draft,running,paused)",
                "order": "updated_at.desc",
                "limit": "1",
            },
            headers=self._headers,
            timeout=30.0,
        )
        response.raise_for_status()
        rows = response.json()
        if not isinstance(rows, list) or not rows or not isinstance(rows[0], dict):
            return None
        record = rows[0]
        record["processing_queue_items"] = sorted(
            record.get("processing_queue_items", []), key=lambda item: item["position"]
        )
        reconciled = self.finalize_processing_queue_if_done(record["id"], user_id)
        if reconciled is not None and reconciled.get("status") not in {
            "draft",
            "running",
            "paused",
        }:
            # A legacy running batch can already contain only terminal items.
            # Re-query so it is never returned as an active queue.
            return self.get_active_processing_queue(user_id)
        if reconciled is not None:
            return reconciled
        return record

    def remove_processing_queue_item(
        self, queue_id: str, item_id: str, user_id: str
    ) -> bool:
        queue = self._queue(queue_id, user_id)
        if queue is None or queue.get("status") not in {"draft", "paused"}:
            return False
        response = httpx.delete(
            f"{self._project_url}/rest/v1/processing_queue_items",
            params={
                "id": f"eq.{item_id}",
                "queue_id": f"eq.{queue_id}",
                "user_id": f"eq.{user_id}",
                "status": "in.(pending,failed)",
            },
            headers={**self._headers, "Prefer": "return=representation"},
            timeout=30.0,
        )
        response.raise_for_status()
        rows = response.json()
        if not isinstance(rows, list) or not rows:
            return False
        httpx.patch(
            f"{self._project_url}/rest/v1/processing_queues",
            params={
                "id": f"eq.{queue_id}",
                "user_id": f"eq.{user_id}",
                "status": f"eq.{queue['status']}",
            },
            json={"total_items": max(0, int(queue["total_items"]) - 1)},
            headers=self._headers,
            timeout=30.0,
        ).raise_for_status()
        return True

    def delete_outreach_item_permanently(
        self, user_id: str, outreach_item_id: str
    ) -> bool:
        response = httpx.post(
            f"{self._project_url}/rest/v1/rpc/delete_outreach_item_permanently",
            json={"p_user_id": user_id, "p_outreach_item_id": outreach_item_id},
            headers=self._headers,
            timeout=30.0,
        )
        response.raise_for_status()
        return response.json() is True

    def delete_processing_queue_task_permanently(
        self, user_id: str, item_id: str
    ) -> dict[str, Any] | None:
        response = httpx.post(
            f"{self._project_url}/rest/v1/rpc/delete_processing_queue_task_permanently",
            json={"p_user_id": user_id, "p_queue_item_id": item_id},
            headers=self._headers,
            timeout=30.0,
        )
        response.raise_for_status()
        rows = response.json()
        return (
            rows[0]
            if isinstance(rows, list) and rows and isinstance(rows[0], dict)
            else None
        )

    def delete_processing_queue(self, queue_id: str, user_id: str) -> bool | None:
        """Delete an inactive queue and its queue items, preserving outreach/drafts."""
        queue = self._queue(queue_id, user_id)
        if queue is None:
            return None
        if queue.get("status") in {"draft", "running", "paused"}:
            return False
        response = httpx.delete(
            f"{self._project_url}/rest/v1/processing_queues",
            params={"id": f"eq.{queue_id}", "user_id": f"eq.{user_id}"},
            headers={**self._headers, "Prefer": "return=representation"},
            timeout=30.0,
        )
        response.raise_for_status()
        return bool(response.json())

    def update_processing_queue_item(
        self, queue_id: str, item_id: str, user_id: str, update: dict[str, object]
    ) -> dict[str, Any] | None:
        queue = self._queue(queue_id, user_id)
        if queue is None or queue.get("status") not in {"draft", "paused"}:
            return None
        allowed = {
            "linkedin_post_url",
            "author_name",
            "author_profile_url",
            "linkedin_post_text",
            "job_description_url",
            "job_description_text",
            "recipient_to",
            "recipient_cc",
        }
        if not set(update).issubset(allowed):
            return None
        source = {
            "source_linkedin_post_url": update.get("linkedin_post_url"),
            "source_author_name": update.get("author_name"),
            "source_author_profile_url": update.get("author_profile_url"),
            "source_linkedin_post_text": update.get("linkedin_post_text"),
            "source_job_description_url": update.get("job_description_url"),
            "source_job_description_text": update.get("job_description_text"),
        }
        source = {key: value for key, value in source.items() if value is not None}
        response = httpx.patch(
            f"{self._project_url}/rest/v1/processing_queue_items",
            params={
                "id": f"eq.{item_id}",
                "queue_id": f"eq.{queue_id}",
                "user_id": f"eq.{user_id}",
                "status": "in.(pending,failed)",
            },
            json=source,
            headers={**self._headers, "Prefer": "return=representation"},
            timeout=30.0,
        )
        response.raise_for_status()
        rows = response.json()
        return (
            rows[0]
            if isinstance(rows, list) and rows and isinstance(rows[0], dict)
            else None
        )

    def start_processing_queue(
        self, queue_id: str, user_id: str, allowed: tuple[str, ...]
    ) -> dict[str, Any] | None:
        queue = self._queue(queue_id, user_id)
        if (
            queue is None
            or queue.get("status") not in allowed
            or not queue.get("processing_queue_items")
        ):
            return None
        response = httpx.patch(
            f"{self._project_url}/rest/v1/processing_queues",
            params={
                "id": f"eq.{queue_id}",
                "user_id": f"eq.{user_id}",
                "status": f"in.({','.join(allowed)})",
            },
            json={
                "status": "running",
                "started_at": datetime.now(timezone.utc).isoformat(),
            },
            headers={**self._headers, "Prefer": "return=representation"},
            timeout=30.0,
        )
        response.raise_for_status()
        rows = response.json()
        return (
            self._queue(queue_id, user_id) if isinstance(rows, list) and rows else None
        )

    def pause_processing_queue(
        self, queue_id: str, user_id: str
    ) -> dict[str, Any] | None:
        queue = self._queue(queue_id, user_id)
        if queue is None:
            return None
        if queue.get("status") == "running":
            httpx.patch(
                f"{self._project_url}/rest/v1/processing_queues",
                params={
                    "id": f"eq.{queue_id}",
                    "user_id": f"eq.{user_id}",
                    "status": "eq.running",
                },
                json={
                    "status": "paused",
                    "paused_at": datetime.now(timezone.utc).isoformat(),
                },
                headers=self._headers,
                timeout=30.0,
            ).raise_for_status()
        return self._queue(queue_id, user_id)

    def claim_next_processing_queue_item(
        self, queue_id: str, user_id: str
    ) -> dict[str, Any] | None:
        response = httpx.post(
            f"{self._project_url}/rest/v1/rpc/claim_next_processing_queue_item",
            json={"p_queue_id": queue_id, "p_user_id": user_id},
            headers=self._headers,
            timeout=30.0,
        )
        response.raise_for_status()
        rows = response.json()
        return (
            rows[0]
            if isinstance(rows, list) and rows and isinstance(rows[0], dict)
            else None
        )

    def recover_stale_processing_queue_items(self, queue_id: str, user_id: str) -> None:
        httpx.post(
            f"{self._project_url}/rest/v1/rpc/recover_stale_processing_queue_items",
            json={"p_queue_id": queue_id, "p_user_id": user_id},
            headers=self._headers,
            timeout=30.0,
        ).raise_for_status()

    def complete_processing_queue_item(
        self, item_id: str, user_id: str, draft_id: str
    ) -> None:
        response = httpx.patch(
            f"{self._project_url}/rest/v1/processing_queue_items",
            params={
                "id": f"eq.{item_id}",
                "user_id": f"eq.{user_id}",
                "status": "eq.processing",
            },
            json={
                "status": "completed",
                "generated_draft_id": draft_id,
                "error_code": None,
                "failure_status": None,
                "failure_reason": None,
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "processing_lease_expires_at": None,
            },
            headers={**self._headers, "Prefer": "return=representation"},
            timeout=30.0,
        )
        response.raise_for_status()

    def cleanup_completed_processing_queue(self, queue_id: str, user_id: str) -> bool:
        response = httpx.post(
            f"{self._project_url}/rest/v1/rpc/cleanup_completed_processing_queue",
            json={"p_queue_id": queue_id, "p_user_id": user_id},
            headers=self._headers,
            timeout=30.0,
        )
        response.raise_for_status()
        return response.json() is True

    def fail_processing_queue_item(
        self,
        item_id: str,
        user_id: str,
        error_code: str,
        failure_status: str = "failed",
        failure_reason: str | None = None,
        failure_stage: str | None = None,
    ) -> None:
        httpx.patch(
            f"{self._project_url}/rest/v1/processing_queue_items",
            params={
                "id": f"eq.{item_id}",
                "user_id": f"eq.{user_id}",
                "status": "eq.processing",
            },
            json={
                "status": "failed",
                "error_code": error_code,
                "failure_status": failure_status,
                "failure_reason": failure_reason or "This task could not be processed.",
                "failure_stage": failure_stage,
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "processing_lease_expires_at": None,
            },
            headers=self._headers,
            timeout=30.0,
        ).raise_for_status()

    def list_failed_tasks(self, user_id: str) -> list[dict[str, Any]]:
        response = httpx.get(
            f"{self._project_url}/rest/v1/processing_queue_items",
            # Extension failure records from older deployments can be `failed`
            # before `failure_status` was populated.  Never hide them solely
            # because that optional classification is absent.
            params={
                "select": "*",
                "user_id": f"eq.{user_id}",
                "status": "eq.failed",
                "hidden_at": "is.null",
                "order": "updated_at.desc",
            },
            headers=self._headers,
            timeout=30.0,
        )
        response.raise_for_status()
        rows = response.json()
        return (
            [row for row in rows if isinstance(row, dict)]
            if isinstance(rows, list)
            else []
        )

    def get_failed_task(self, item_id: str, user_id: str) -> dict[str, Any] | None:
        response = httpx.get(
            f"{self._project_url}/rest/v1/processing_queue_items",
            params={
                "select": "*",
                "id": f"eq.{item_id}",
                "user_id": f"eq.{user_id}",
                "limit": "1",
            },
            headers=self._headers,
            timeout=30.0,
        )
        response.raise_for_status()
        rows = response.json()
        return (
            rows[0]
            if isinstance(rows, list) and rows and isinstance(rows[0], dict)
            else None
        )

    def claim_failed_task_retry(
        self, item_id: str, user_id: str
    ) -> dict[str, Any] | None:
        response = httpx.post(
            f"{self._project_url}/rest/v1/rpc/claim_failed_processing_queue_item",
            json={"p_item_id": item_id, "p_user_id": user_id},
            headers=self._headers,
            timeout=30.0,
        )
        response.raise_for_status()
        rows = response.json()
        return (
            rows[0]
            if isinstance(rows, list) and rows and isinstance(rows[0], dict)
            else None
        )

    def update_failed_processing_queue_item(
        self, item_id: str, user_id: str, payload: dict[str, object]
    ) -> dict[str, Any] | None:
        """Persist corrected retry input without changing the failed lifecycle state."""
        response = httpx.patch(
            f"{self._project_url}/rest/v1/processing_queue_items",
            params={
                "id": f"eq.{item_id}",
                "user_id": f"eq.{user_id}",
                "status": "eq.failed",
            },
            json={
                "input_payload": payload,
                "source_linkedin_post_url": payload.get("linkedin_post_url"),
                "source_linkedin_post_text": payload.get("linkedin_post_text"),
                "source_job_description_url": payload.get("job_description_url"),
                "source_job_description_text": payload.get("job_description_text"),
                "source_author_name": payload.get("author_name"),
                "source_author_profile_url": payload.get("author_profile_url"),
            },
            headers={**self._headers, "Prefer": "return=representation"},
            timeout=30.0,
        )
        response.raise_for_status()
        rows = response.json()
        return (
            rows[0]
            if isinstance(rows, list) and rows and isinstance(rows[0], dict)
            else None
        )

    def hide_failed_task(self, item_id: str, user_id: str) -> bool:
        response = httpx.patch(
            f"{self._project_url}/rest/v1/processing_queue_items",
            params={
                "id": f"eq.{item_id}",
                "user_id": f"eq.{user_id}",
                "status": "eq.failed",
                "hidden_at": "is.null",
            },
            json={"hidden_at": datetime.now(timezone.utc).isoformat()},
            headers={**self._headers, "Prefer": "return=representation"},
            timeout=30.0,
        )
        response.raise_for_status()
        return bool(response.json())

    def finalize_processing_queue_if_done(
        self, queue_id: str, user_id: str
    ) -> dict[str, Any] | None:
        """Idempotently move an active batch to a terminal state when all items end."""
        queue = self._queue(queue_id, user_id)
        if queue is None:
            return None
        items = queue.get("processing_queue_items", [])
        if not items or any(
            item.get("status") in {"pending", "processing"} for item in items
        ):
            return queue
        completed = sum(
            item.get("status") == "completed"
            or item.get("failure_status") in {"duplicate", "no_email_available"}
            for item in items
        )
        failed = sum(
            item.get("status") == "failed"
            and item.get("failure_status") not in {"duplicate", "no_email_available"}
            for item in items
        )
        status_value = "completed_with_failures" if failed else "completed"
        if (
            queue.get("status") == status_value
            and queue.get("completed_items") == completed
            and queue.get("failed_items") == failed
        ):
            return queue
        response = httpx.patch(
            f"{self._project_url}/rest/v1/processing_queues",
            params={
                "id": f"eq.{queue_id}",
                "user_id": f"eq.{user_id}",
            },
            json={
                "status": status_value,
                "completed_items": completed,
                "failed_items": failed,
                "completed_at": datetime.now(timezone.utc).isoformat(),
            },
            headers={**self._headers, "Prefer": "return=representation"},
            timeout=30.0,
        )
        response.raise_for_status()
        rows = response.json()
        if isinstance(rows, list) and rows and isinstance(rows[0], dict):
            return self._queue(queue_id, user_id) or rows[0]
        # A concurrent worker finalized the batch first; its terminal state is
        # authoritative and no second transition is attempted.
        return self._queue(queue_id, user_id)

    def finish_processing_queue_if_done(self, queue_id: str, user_id: str) -> None:
        self.finalize_processing_queue_if_done(queue_id, user_id)

    def reconcile_processing_queue(self, queue_id: str, user_id: str) -> None:
        """Refresh terminal counters after a one-item retry without restarting a batch."""
        self.finalize_processing_queue_if_done(queue_id, user_id)

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
