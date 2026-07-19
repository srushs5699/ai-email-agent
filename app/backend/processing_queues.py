"""Step 6 queue coordinator. Background tasks are disposable; Supabase state is not."""

# ruff: noqa: E501, E701, E702, F401, I001
import asyncio
import logging
from datetime import datetime, timezone
from typing import Annotated, Any
from uuid import UUID

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel, Field

from auth import AuthenticatedUser, get_current_user
from drafts import DraftCreateRequest
from email_generation import (
    EmailGenerationRequest,
    EmailGenerator,
    ProviderUnavailableError,
    build_generation_prompt,
    get_email_generator,
)
from supabase_admin import SupabaseAdmin, get_supabase_admin

router = APIRouter(prefix="/api/v1/processing-queues", tags=["processing queues"])
logger = logging.getLogger(__name__)
CurrentUser = Annotated[AuthenticatedUser, Depends(get_current_user)]
Storage = Annotated[SupabaseAdmin, Depends(get_supabase_admin)]
Generator = Annotated[EmailGenerator, Depends(get_email_generator)]


class QueueInput(EmailGenerationRequest):
    pass


class QueueCreateRequest(BaseModel):
    items: list[QueueInput] = Field(min_length=1, max_length=10)


class QueueItemResponse(BaseModel):
    id: UUID
    position: int
    status: str
    generated_draft_id: UUID | None = None
    error_code: str | None = None
    created_at: str
    updated_at: str


class QueueResponse(BaseModel):
    id: UUID
    status: str
    total_items: int
    completed_items: int
    failed_items: int
    created_at: str
    updated_at: str
    items: list[QueueItemResponse]


def _queue_response(record: dict[str, Any]) -> QueueResponse:
    return QueueResponse.model_validate(
        {**record, "items": record.get("processing_queue_items", [])}
    )


def _not_found() -> HTTPException:
    return HTTPException(404, "Processing queue not found.")


def _safe_error(error: Exception) -> str:
    # Never persist provider/upstream text; this small taxonomy is safe for UI/logs.
    return (
        "generation_unavailable"
        if isinstance(error, ProviderUnavailableError)
        else "generation_failed"
    )


@router.post("", response_model=QueueResponse, status_code=status.HTTP_201_CREATED)
def create_queue(
    request: QueueCreateRequest, user: CurrentUser, storage: Storage
) -> QueueResponse:
    for item in request.items:
        if storage.get_resume(str(item.resume_id), user["user_id"]) is None:
            raise HTTPException(404, "Resume not found.")
    try:
        record = storage.create_processing_queue(
            user["user_id"], [item.model_dump(mode="json") for item in request.items]
        )
        return _queue_response(record)
    except httpx.HTTPError as error:
        raise HTTPException(502, "The processing queue could not be saved.") from error


@router.get("/active", response_model=QueueResponse)
def active_queue(user: CurrentUser, storage: Storage) -> QueueResponse:
    record = storage.get_active_processing_queue(user["user_id"])
    if record is None:
        raise _not_found()
    return _queue_response(record)


@router.get("/{queue_id}", response_model=QueueResponse)
def get_queue(queue_id: UUID, user: CurrentUser, storage: Storage) -> QueueResponse:
    record = storage.get_processing_queue(str(queue_id), user["user_id"])
    if record is None:
        raise _not_found()
    return _queue_response(record)


@router.delete("/{queue_id}/items/{item_id}", status_code=204)
def remove_item(
    queue_id: UUID, item_id: UUID, user: CurrentUser, storage: Storage
) -> None:
    if not storage.remove_processing_queue_item(
        str(queue_id), str(item_id), user["user_id"]
    ):
        raise HTTPException(409, "Items can only be removed from a draft queue.")


def _launch(
    background: BackgroundTasks,
    queue_id: str,
    user_id: str,
    storage: SupabaseAdmin,
    generator: EmailGenerator,
) -> None:
    background.add_task(process_queue, queue_id, user_id, storage, generator)


@router.post("/{queue_id}/start", response_model=QueueResponse)
def start_queue(
    queue_id: UUID,
    background: BackgroundTasks,
    user: CurrentUser,
    storage: Storage,
    generator: Generator,
) -> QueueResponse:
    record = storage.start_processing_queue(
        str(queue_id), user["user_id"], allowed=("draft",)
    )
    if record is None:
        raise HTTPException(409, "Queue cannot be started.")
    _launch(background, str(queue_id), user["user_id"], storage, generator)
    return _queue_response(record)


@router.post("/{queue_id}/pause", response_model=QueueResponse)
def pause_queue(queue_id: UUID, user: CurrentUser, storage: Storage) -> QueueResponse:
    record = storage.pause_processing_queue(str(queue_id), user["user_id"])
    if record is None:
        raise _not_found()
    return _queue_response(record)


@router.post("/{queue_id}/resume", response_model=QueueResponse)
def resume_queue(
    queue_id: UUID,
    background: BackgroundTasks,
    user: CurrentUser,
    storage: Storage,
    generator: Generator,
) -> QueueResponse:
    record = storage.start_processing_queue(
        str(queue_id), user["user_id"], allowed=("paused",)
    )
    if record is None:
        raise HTTPException(409, "Queue cannot be resumed.")
    _launch(background, str(queue_id), user["user_id"], storage, generator)
    return _queue_response(record)


def process_queue(
    queue_id: str, user_id: str, storage: SupabaseAdmin, generator: EmailGenerator
) -> None:
    """Claim, generate and persist exactly one row at a time until paused/done."""
    storage.recover_stale_processing_queue_items(queue_id, user_id)
    while True:
        item = storage.claim_next_processing_queue_item(queue_id, user_id)
        if item is None:
            break
        try:
            payload = QueueInput.model_validate(item["input_payload"])
            resume = storage.get_resume(str(payload.resume_id), user_id)
            if (
                resume is None
                or resume.get("parse_status") != "completed"
                or not isinstance(resume.get("extracted_text"), str)
            ):
                raise ValueError("resume")
            generated = generator.generate(
                build_generation_prompt(resume["extracted_text"], payload)
            )
            draft_request = DraftCreateRequest(
                **payload.model_dump(), subject=generated.subject, body=generated.body
            )
            outreach = {
                "user_id": user_id,
                "linkedin_post_text": draft_request.linkedin_post_text,
                "job_description_text": draft_request.job_description_text or None,
                "no_job_description": draft_request.no_job_description,
                "recipient_to": draft_request.recipient_to,
                "recipient_cc": draft_request.recipient_cc,
                "recipient_name": draft_request.recipient_name,
                "company_name": draft_request.company_name,
                "selected_resume_id": str(draft_request.resume_id),
                "status": "ready",
            }
            draft = {
                "user_id": user_id,
                "subject": generated.subject,
                "body": generated.body,
                "generation_status": "completed",
                "draft_status": "ready_for_review",
            }
            saved = storage.create_draft(outreach, draft)
            storage.complete_processing_queue_item(item["id"], user_id, saved["id"])
        except Exception as error:
            logger.warning(
                "processing queue item failed queue_id=%s item_id=%s code=%s",
                queue_id,
                item.get("id"),
                _safe_error(error),
            )
            storage.fail_processing_queue_item(item["id"], user_id, _safe_error(error))
        storage.finish_processing_queue_if_done(queue_id, user_id)
