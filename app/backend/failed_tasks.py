"""Step 8 failed processing work: list, retry one, or hide one safely."""

import logging
from typing import Annotated, Any, Literal
from uuid import UUID

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel, field_validator

from auth import AuthenticatedUser, get_current_user
from email_generation import (
    EMAIL_PATTERN,
    EmailGenerationRequest,
    EmailGenerator,
    get_email_generator,
)
from processing_queues import normalize_queue_input_payload, process_queue_item
from supabase_admin import SupabaseAdmin, get_supabase_admin

router = APIRouter(prefix="/api/v1/failed-tasks", tags=["failed tasks"])
CurrentUser = Annotated[AuthenticatedUser, Depends(get_current_user)]
Storage = Annotated[SupabaseAdmin, Depends(get_supabase_admin)]
Generator = Annotated[EmailGenerator, Depends(get_email_generator)]
logger = logging.getLogger(__name__)


class FailedTaskResponse(BaseModel):
    id: UUID
    processing_queue_item_id: UUID
    queue_id: UUID
    outreach_item_id: UUID | None = None
    generated_draft_id: UUID | None = None
    resume_id: UUID | None = None
    linkedin_post_url: str | None = None
    job_description_url: str | None = None
    author_name: str | None = None
    author_profile_url: str | None = None
    linkedin_post_text: str | None = None
    job_description_text: str | None = None
    recipient_to: str | None = None
    recipient_cc: str | None = None
    no_job_description: bool | None = None
    job_description_source: Literal["visible_page", "manual", "unavailable"] | None = (
        None
    )
    captured_at: str | None = None
    failure_stage: str | None = None
    status: str
    failure_reason: str
    retry_count: int
    retrying: bool
    failed_at: str | None = None
    created_at: str
    updated_at: str


class FailedTaskListResponse(BaseModel):
    tasks: list[FailedTaskResponse]


class FailedTaskUpdateRequest(BaseModel):
    resume_id: UUID | None = None
    recipient_to: str | None = None
    recipient_cc: str | None = None
    no_job_description: bool | None = None
    job_description_source: Literal["visible_page", "manual", "unavailable"] | None = (
        None
    )
    linkedin_post_url: str | None = None
    linkedin_post_text: str | None = None
    job_description_url: str | None = None
    job_description_text: str | None = None
    author_name: str | None = None
    author_profile_url: str | None = None

    @field_validator("linkedin_post_url", "job_description_url", "author_profile_url")
    @classmethod
    def public_urls(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        if not value.startswith(("http://", "https://")):
            raise ValueError("URL must use http or https")
        return value.strip()

    @field_validator("recipient_to", "recipient_cc")
    @classmethod
    def email_addresses(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized_value = value.strip()
        if normalized_value and not EMAIL_PATTERN.fullmatch(normalized_value):
            raise ValueError("Enter a valid email address.")
        return normalized_value or None

    @field_validator(
        "linkedin_post_text",
        "job_description_text",
        "author_name",
    )
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None


def _response(record: dict[str, Any]) -> FailedTaskResponse:
    payload = record.get("input_payload") or {}
    item_status = record.get("status")
    response_status = (
        record.get("failure_status")
        if item_status == "failed" and record.get("failure_status")
        else item_status
    )
    return FailedTaskResponse(
        id=record["id"],
        processing_queue_item_id=record["id"],
        queue_id=record["queue_id"],
        outreach_item_id=record.get("outreach_item_id"),
        generated_draft_id=record.get("generated_draft_id"),
        resume_id=payload.get("resume_id"),
        linkedin_post_url=payload.get("linkedin_post_url")
        or record.get("source_linkedin_post_url"),
        job_description_url=payload.get("job_description_url")
        or record.get("source_job_description_url"),
        author_name=payload.get("author_name") or record.get("source_author_name"),
        author_profile_url=payload.get("author_profile_url")
        or record.get("source_author_profile_url"),
        linkedin_post_text=payload.get("linkedin_post_text")
        or record.get("source_linkedin_post_text"),
        job_description_text=payload.get("job_description_text")
        or record.get("source_job_description_text"),
        recipient_to=payload.get("recipient_to"),
        recipient_cc=payload.get("recipient_cc"),
        no_job_description=payload.get("no_job_description"),
        job_description_source=payload.get("job_description_source"),
        captured_at=payload.get("captured_at") or record.get("captured_at"),
        failure_stage=record.get("failure_stage"),
        status=response_status if isinstance(response_status, str) else "failed",
        failure_reason=(
            record.get("failure_reason") or "This task could not be processed."
        ),
        retry_count=record.get("retry_count") or 0,
        retrying=record.get("status") == "processing",
        failed_at=record.get("completed_at"),
        created_at=record["created_at"],
        updated_at=record["updated_at"],
    )


def retry_one_item(
    item: dict[str, Any],
    user_id: str,
    storage: SupabaseAdmin,
    generator: EmailGenerator,
) -> None:
    process_queue_item(item, user_id, storage, generator)
    storage.reconcile_processing_queue(item["queue_id"], user_id)


def _ensure_retry_resume(
    item: dict[str, Any], user_id: str, storage: SupabaseAdmin
) -> dict[str, Any]:
    """Repair legacy queue payloads only when there is one unambiguous resume."""
    payload = normalize_queue_input_payload(item.get("input_payload") or {})
    if payload.get("resume_id"):
        repaired = storage.update_failed_processing_queue_item(
            item["id"], user_id, payload
        )
        return repaired or item
    resumes = [
        resume
        for resume in storage.list_resumes(user_id)
        if resume.get("parse_status") == "completed"
        and isinstance(resume.get("id"), str)
    ]
    if len(resumes) != 1:
        raise HTTPException(
            422,
            "Select a completed resume before retrying this task.",
        )
    repaired_payload = {**payload, "resume_id": resumes[0]["id"]}
    repaired = storage.update_failed_processing_queue_item(
        item["id"], user_id, repaired_payload
    )
    if repaired is None:
        raise HTTPException(409, "This failed task is no longer retryable.")
    return repaired


@router.get("", response_model=FailedTaskListResponse)
def list_failed_tasks(user: CurrentUser, storage: Storage) -> FailedTaskListResponse:
    rows = storage.list_failed_tasks(user["user_id"])
    return FailedTaskListResponse(tasks=[_response(row) for row in rows])


@router.patch("/{task_id}", response_model=FailedTaskResponse)
def update_failed_task(
    task_id: UUID, request: FailedTaskUpdateRequest, user: CurrentUser, storage: Storage
) -> FailedTaskResponse:
    existing = storage.get_failed_task(str(task_id), user["user_id"])
    if existing is None or existing.get("status") != "failed":
        raise HTTPException(404, "Failed task not found.")
    payload = {
        **(existing.get("input_payload") or {}),
        **request.model_dump(exclude_none=True, mode="json"),
    }
    payload = normalize_queue_input_payload(payload)
    # Validate the complete saved item, rather than only the patch, so edits
    # cannot leave a retryable task without its required recipient or source URL.
    try:
        EmailGenerationRequest.model_validate(payload)
    except Exception as error:
        raise HTTPException(422, str(error)) from error
    saved = storage.update_failed_processing_queue_item(
        str(task_id), user["user_id"], payload
    )
    if saved is None:
        raise HTTPException(409, "This failed task is no longer editable.")
    return _response(saved)


@router.post("/{task_id}/retry", response_model=FailedTaskResponse)
def retry_failed_task(
    task_id: UUID,
    background: BackgroundTasks,
    user: CurrentUser,
    storage: Storage,
    generator: Generator,
) -> FailedTaskResponse:
    logger.info(
        "failed_task_retry_requested user_id=%s item_id=%s", user["user_id"], task_id
    )
    existing = storage.get_failed_task(str(task_id), user["user_id"])
    if existing is None or existing.get("status") != "failed":
        raise HTTPException(404, "Failed task not found.")
    _ensure_retry_resume(existing, user["user_id"], storage)
    item = storage.claim_failed_task_retry(str(task_id), user["user_id"])
    if item is None:
        raise HTTPException(409, "This failed task is no longer retryable.")
    logger.info(
        "failed_task_retry_processing user_id=%s item_id=%s", user["user_id"], task_id
    )
    background.add_task(retry_one_item, item, user["user_id"], storage, generator)
    return _response(item)


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_failed_task(task_id: UUID, user: CurrentUser, storage: Storage) -> None:
    logger.info(
        "failed_task_delete_requested user_id=%s item_id=%s", user["user_id"], task_id
    )
    try:
        deleted = storage.delete_processing_queue_task_permanently(
            user["user_id"], str(task_id)
        )
    except httpx.HTTPError as error:
        logger.exception(
            "failed_task_delete_failed user_id=%s item_id=%s", user["user_id"], task_id
        )
        raise HTTPException(
            502, "The task could not be deleted. No records were removed."
        ) from error
    if deleted is None:
        raise HTTPException(404, "Failed task not found.")
    logger.info(
        "failed_task_delete_succeeded user_id=%s item_id=%s queue_id=%s "
        "status_before=%s outreach_item_id=%s",
        user["user_id"],
        task_id,
        deleted.get("queue_id"),
        deleted.get("task_status"),
        deleted.get("outreach_item_id"),
    )
