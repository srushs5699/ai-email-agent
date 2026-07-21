"""Step 6 queue coordinator. Background tasks are disposable; Supabase state is not."""

# ruff: noqa: E501, E701, E702, F401, I001
import asyncio
import logging
from datetime import datetime, timezone
from typing import Annotated, Any, Mapping
from uuid import UUID

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel, Field, ValidationError, field_validator
from urllib.parse import urlsplit

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


class DuplicateQueueItemError(Exception):
    """An exact recipient and LinkedIn-source match already has a draft."""


class QueueInput(EmailGenerationRequest):
    pass


def normalize_queue_input_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Return one canonical job-description state for queue validation."""
    normalized = dict(payload)
    for field in (
        "linkedin_post_url",
        "linkedin_post_text",
        "job_description_url",
        "job_description_text",
        "job_description_source",
    ):
        value = normalized.get(field)
        if isinstance(value, str):
            normalized[field] = value.strip() or None

    text = normalized.get("job_description_text")
    url = normalized.get("job_description_url")
    source = normalized.get("job_description_source")
    source = source.lower() if isinstance(source, str) else None

    if text:
        normalized["no_job_description"] = False
        normalized["job_description_source"] = (
            source if source in {"visible_page", "manual"} else "manual"
        )
    elif source == "unavailable" or not url:
        normalized["job_description_text"] = ""
        normalized["job_description_url"] = None
        normalized["job_description_source"] = "unavailable"
        normalized["no_job_description"] = True
    else:
        normalized["job_description_text"] = ""
        normalized["job_description_source"] = "visible_page"
        normalized["no_job_description"] = False
    return normalized


class QueueCreateRequest(BaseModel):
    items: list[QueueInput] = Field(min_length=1, max_length=10)


class QueueItemResponse(BaseModel):
    id: UUID
    position: int
    status: str
    generated_draft_id: UUID | None = None
    error_code: str | None = None
    failure_status: str | None = None
    failure_reason: str | None = None
    created_at: str
    updated_at: str
    started_at: str | None = None
    completed_at: str | None = None
    outreach_item_id: UUID | None = None
    source_linkedin_post_url: str | None = None
    source_author_name: str | None = None
    source_author_profile_url: str | None = None
    source_linkedin_post_text: str | None = None
    source_job_description_url: str | None = None
    source_job_description_text: str | None = None


class QueueItemUpdateRequest(BaseModel):
    linkedin_post_url: str | None = Field(default=None, max_length=2048)
    author_name: str | None = Field(default=None, max_length=300)
    author_profile_url: str | None = Field(default=None, max_length=2048)
    linkedin_post_text: str | None = Field(default=None, max_length=12000)
    job_description_url: str | None = Field(default=None, max_length=2048)
    job_description_text: str | None = Field(default=None, max_length=50000)
    recipient_to: str | None = Field(default=None, max_length=320)
    recipient_cc: str | None = Field(default=None, max_length=320)

    @field_validator("linkedin_post_url")
    @classmethod
    def source_url_is_safe(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("LinkedIn Post URL / JD URL is required.")
        parsed = urlsplit(normalized)
        if parsed.scheme not in {"http", "https"}:
            raise ValueError("Only HTTP and HTTPS URLs are allowed.")
        if not parsed.netloc:
            raise ValueError(
                "Enter a valid HTTP or HTTPS LinkedIn post, job, or JD URL."
            )
        return normalized

    @field_validator("linkedin_post_text", "job_description_text", "author_name")
    @classmethod
    def optional_text_is_nullable(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None


class QueueResponse(BaseModel):
    id: UUID
    queue_number: int = 0
    status: str
    total_items: int
    completed_items: int
    failed_items: int
    created_at: str
    updated_at: str
    started_at: str | None = None
    paused_at: str | None = None
    completed_at: str | None = None
    items: list[QueueItemResponse]


def _queue_response(record: dict[str, Any]) -> QueueResponse:
    return QueueResponse.model_validate(
        {**record, "items": record.get("processing_queue_items", [])}
    )


def _not_found() -> HTTPException:
    return HTTPException(404, "Processing queue not found.")


def _failure_details(
    error: Exception, stage: str = "processing"
) -> tuple[str, str, str]:
    """Return a user-safe status, code, and reason without provider internals."""
    if isinstance(error, DuplicateQueueItemError):
        return (
            "duplicate",
            "duplicate",
            "A draft already exists for this recipient and LinkedIn source.",
        )
    if isinstance(error, ValidationError) and "recipient_to" in str(error):
        return (
            "no_email_available",
            "no_email_available",
            "No usable recipient email is available.",
        )
    if isinstance(error, ProviderUnavailableError):
        return (
            "failed",
            "generation_unavailable",
            "The AI provider was unavailable during email generation.",
        )
    if isinstance(error, ValueError) and str(error) == "resume":
        return (
            "failed",
            "resume_unavailable",
            "The selected resume is unavailable or not ready.",
        )
    if isinstance(error, httpx.TimeoutException):
        return (
            "failed",
            "external_service_timeout",
            f"The external service timed out during {stage.replace('_', ' ')}.",
        )
    if isinstance(error, httpx.HTTPStatusError) and error.response is not None:
        return (
            "failed",
            "external_service_http_error",
            f"The external service returned HTTP {error.response.status_code} during "
            f"{stage.replace('_', ' ')}.",
        )
    if isinstance(error, ValidationError):
        return (
            "failed",
            "invalid_processing_input",
            "The saved processing details are incomplete or invalid.",
        )
    return (
        "failed",
        "processing_error",
        f"{stage.replace('_', ' ').capitalize()} failed. Please review the task and retry.",
    )


def _safe_exception_message(error: Exception) -> str:
    if isinstance(error, httpx.HTTPStatusError) and error.response is not None:
        return f"HTTP {error.response.status_code}"
    if isinstance(error, httpx.TimeoutException):
        return "request timed out"
    if isinstance(error, ProviderUnavailableError):
        return "AI provider unavailable"
    if isinstance(error, ValidationError):
        return "processing input validation failed"
    if isinstance(error, ValueError) and str(error) == "resume":
        return "selected resume unavailable"
    return "unexpected processing error"


@router.post("", response_model=QueueResponse, status_code=status.HTTP_201_CREATED)
def create_queue(
    request: QueueCreateRequest, user: CurrentUser, storage: Storage
) -> QueueResponse:
    normalized_items = [
        QueueInput.model_validate(normalize_queue_input_payload(item.model_dump()))
        for item in request.items
    ]
    for item in normalized_items:
        if storage.get_resume(str(item.resume_id), user["user_id"]) is None:
            raise HTTPException(404, "Resume not found.")
    try:
        record = storage.create_processing_queue(
            user["user_id"],
            [item.model_dump(mode="json") for item in normalized_items],
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


@router.get("", response_model=list[QueueResponse])
def list_queues(user: CurrentUser, storage: Storage) -> list[QueueResponse]:
    records = storage.list_processing_queues(user["user_id"])
    active = {"draft", "running", "paused"}
    records.sort(key=lambda record: record.get("status") not in active)
    return [_queue_response(record) for record in records]


@router.get("/{queue_id}", response_model=QueueResponse)
def get_queue(queue_id: UUID, user: CurrentUser, storage: Storage) -> QueueResponse:
    record = storage.get_processing_queue(str(queue_id), user["user_id"])
    if record is None:
        raise _not_found()
    return _queue_response(record)


@router.delete("/{queue_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_queue(queue_id: UUID, user: CurrentUser, storage: Storage) -> None:
    try:
        deleted = storage.delete_processing_queue(str(queue_id), user["user_id"])
    except httpx.HTTPError as error:
        logger.exception("queue_delete_failed queue_id=%s", queue_id)
        raise HTTPException(502, "The queue could not be deleted.") from error
    if deleted is None:
        raise _not_found()
    if not deleted:
        raise HTTPException(
            409,
            "Active queues cannot be deleted. Pause or wait for processing to finish.",
        )


@router.delete("/{queue_id}/items/{item_id}", status_code=204)
def remove_item(
    queue_id: UUID, item_id: UUID, user: CurrentUser, storage: Storage
) -> None:
    logger.info(
        "queue_task_delete_requested user_id=%s queue_id=%s item_id=%s",
        user["user_id"],
        queue_id,
        item_id,
    )
    try:
        deleted = storage.delete_processing_queue_task_permanently(
            user["user_id"], str(item_id)
        )
    except httpx.HTTPError as error:
        logger.exception(
            "queue_task_delete_failed user_id=%s queue_id=%s item_id=%s",
            user["user_id"],
            queue_id,
            item_id,
        )
        raise HTTPException(
            502, "The task could not be deleted. No records were removed."
        ) from error
    if deleted is None:
        # Do not reveal whether the task exists for another account.
        raise HTTPException(404, "Processing queue item not found.")
    logger.info(
        "queue_task_delete_succeeded user_id=%s queue_id=%s item_id=%s status_before=%s outreach_item_id=%s",
        user["user_id"],
        deleted.get("queue_id"),
        item_id,
        deleted.get("task_status"),
        deleted.get("outreach_item_id"),
    )


@router.patch("/{queue_id}/items/{item_id}", response_model=QueueItemResponse)
def update_item(
    queue_id: UUID,
    item_id: UUID,
    request: QueueItemUpdateRequest,
    user: CurrentUser,
    storage: Storage,
) -> QueueItemResponse:
    record = storage.update_processing_queue_item(
        str(queue_id),
        str(item_id),
        user["user_id"],
        request.model_dump(exclude_unset=True),
    )
    if record is None:
        raise HTTPException(
            409, "Only non-processing items in a draft or paused queue can be edited."
        )
    return QueueItemResponse.model_validate(record)


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
    storage.finalize_processing_queue_if_done(queue_id, user_id)
    while True:
        item = storage.claim_next_processing_queue_item(queue_id, user_id)
        if item is None:
            break
        process_queue_item(item, user_id, storage, generator)
        storage.finish_processing_queue_if_done(queue_id, user_id)
    storage.finish_processing_queue_if_done(queue_id, user_id)


def process_queue_item(
    item: dict[str, Any],
    user_id: str,
    storage: SupabaseAdmin,
    generator: EmailGenerator,
) -> None:
    """Process a claimed queue item; shared by normal processing and one-task retry."""
    stage = "retry_validation"
    item_id = item.get("id")
    outreach_item_id = item.get("outreach_item_id")
    logger.info(
        "processing_stage_started item_id=%s outreach_item_id=%s stage=%s",
        item_id,
        outreach_item_id,
        stage,
    )
    try:
        payload = QueueInput.model_validate(
            normalize_queue_input_payload(item["input_payload"])
        )
        logger.info("processing_stage_completed item_id=%s stage=%s", item_id, stage)

        stage = "resume_loading"
        logger.info("processing_stage_started item_id=%s stage=%s", item_id, stage)
        resume = storage.get_resume(str(payload.resume_id), user_id)
        if (
            resume is None
            or resume.get("parse_status") != "completed"
            or not isinstance(resume.get("extracted_text"), str)
        ):
            raise ValueError("resume")
        logger.info("processing_stage_completed item_id=%s stage=%s", item_id, stage)

        stage = "recipient_resolution"
        logger.info("processing_stage_started item_id=%s stage=%s", item_id, stage)
        if storage.find_active_duplicate_draft(
            user_id, payload.recipient_to, payload.linkedin_post_url
        ):
            raise DuplicateQueueItemError()
        logger.info("processing_stage_completed item_id=%s stage=%s", item_id, stage)

        stage = "ai_generation"
        logger.info("processing_stage_started item_id=%s stage=%s", item_id, stage)
        generated = generator.generate(
            build_generation_prompt(resume["extracted_text"], payload)
        )
        logger.info("processing_stage_completed item_id=%s stage=%s", item_id, stage)

        stage = "database_update"
        logger.info("processing_stage_started item_id=%s stage=%s", item_id, stage)
        draft_request = DraftCreateRequest(
            **payload.model_dump(), subject=generated.subject, body=generated.body
        )
        outreach = {
            "user_id": user_id,
            "linkedin_post_text": draft_request.linkedin_post_text,
            "linkedin_post_url": draft_request.linkedin_post_url,
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
        try:
            if storage.cleanup_completed_processing_queue(item["queue_id"], user_id):
                logger.info(
                    "completed_processing_queue_cleaned queue_id=%s", item["queue_id"]
                )
        except Exception as cleanup_error:
            logger.exception(
                "completed_queue_cleanup_failed queue_id=%s user_id=%s exception_type=%s",
                item["queue_id"],
                user_id,
                type(cleanup_error).__name__,
            )
        logger.info("processing_stage_completed item_id=%s stage=%s", item_id, stage)
    except Exception as error:
        failure_status, error_code, reason = _failure_details(error, stage)
        logger.exception(
            "processing_stage_failed item_id=%s outreach_item_id=%s stage=%s "
            "exception_type=%s exception_message=%s code=%s",
            item_id,
            outreach_item_id,
            stage,
            type(error).__name__,
            _safe_exception_message(error),
            error_code,
        )
        storage.fail_processing_queue_item(
            item["id"], user_id, error_code, failure_status, reason, stage
        )
