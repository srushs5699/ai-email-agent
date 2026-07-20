"""Step 8 failed processing work: list, retry one, or hide one safely."""

import logging
from typing import Annotated, Any
from uuid import UUID

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel

from auth import AuthenticatedUser, get_current_user
from email_generation import EmailGenerator, get_email_generator
from processing_queues import process_queue_item
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
    captured_at: str | None = None
    failure_stage: str | None = None
    status: str
    failure_reason: str
    retry_count: int
    retrying: bool
    created_at: str
    updated_at: str


class FailedTaskListResponse(BaseModel):
    tasks: list[FailedTaskResponse]


def _response(record: dict[str, Any]) -> FailedTaskResponse:
    payload = record.get("input_payload") or {}
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
        captured_at=payload.get("captured_at") or record.get("captured_at"),
        failure_stage=record.get("failure_stage"),
        status=record.get("failure_status") or "failed",
        failure_reason=(
            record.get("failure_reason") or "This task could not be processed."
        ),
        retry_count=record.get("retry_count") or 0,
        retrying=record.get("status") == "processing",
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


@router.get("", response_model=FailedTaskListResponse)
def list_failed_tasks(user: CurrentUser, storage: Storage) -> FailedTaskListResponse:
    rows = storage.list_failed_tasks(user["user_id"])
    return FailedTaskListResponse(tasks=[_response(row) for row in rows])


@router.post("/{task_id}/retry", response_model=FailedTaskResponse)
def retry_failed_task(
    task_id: UUID,
    background: BackgroundTasks,
    user: CurrentUser,
    storage: Storage,
    generator: Generator,
) -> FailedTaskResponse:
    item = storage.claim_failed_task_retry(str(task_id), user["user_id"])
    if item is None:
        existing = storage.get_failed_task(str(task_id), user["user_id"])
        if existing is None:
            raise HTTPException(404, "Failed task not found.")
        raise HTTPException(409, "This failed task is no longer retryable.")
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
