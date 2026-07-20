# ruff: noqa: E501, E701
import logging
from datetime import datetime, timezone
from typing import Annotated, Any
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, field_validator

from auth import AuthenticatedUser, get_current_user
from email_generation import (
    EmailGenerationRequest,
    EmailGenerator,
    ProviderUnavailableError,
    build_generation_prompt,
    get_email_generator,
)
from email_validation import (
    RecipientValidationError,
    approval_content_hash,
    normalize_recipients,
)
from gmail import get_gmail_oauth_service
from gmail_drafts import GmailDraftError, GmailDraftResult, GmailDraftService
from gmail_sending import GmailSendResult, GmailSendService
from supabase_admin import SupabaseAdmin, get_supabase_admin

router = APIRouter(prefix="/api/v1/drafts", tags=["drafts"])
logger = logging.getLogger(__name__)
CurrentUser = Annotated[AuthenticatedUser, Depends(get_current_user)]
Storage = Annotated[SupabaseAdmin, Depends(get_supabase_admin)]


class DraftCreateRequest(BaseModel):
    resume_id: UUID
    linkedin_post_url: str | None = None
    linkedin_post_text: str = ""
    job_description_text: str = ""
    no_job_description: bool = False
    recipient_to: str
    recipient_cc: str | None = None
    recipient_name: str | None = None
    company_name: str | None = None
    subject: str
    body: str

    @field_validator("recipient_to")
    @classmethod
    def valid_to(cls, value: str) -> str:
        try:
            return normalize_recipients(value, required=True) or ""
        except RecipientValidationError as error:
            raise ValueError(str(error)) from error

    @field_validator("recipient_cc")
    @classmethod
    def valid_cc(cls, value: str | None) -> str | None:
        try:
            return normalize_recipients(value, required=False)
        except RecipientValidationError as error:
            raise ValueError(str(error)) from error

    @field_validator("recipient_name", "company_name")
    @classmethod
    def strip_optional(cls, value: str | None) -> str | None:
        return value.strip() if value and value.strip() else None

    @field_validator("subject", "body")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Draft content must not be blank.")
        return value


class DraftUpdateRequest(BaseModel):
    subject: str
    body: str
    recipient_to: str | None = None
    recipient_cc: str | None = None
    resume_id: UUID | None = None

    @field_validator("subject", "body")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Draft content must not be blank.")
        return value

    @field_validator("recipient_to")
    @classmethod
    def valid_optional_to(cls, value: str | None) -> str | None:
        if value is None:
            return None
        try:
            return normalize_recipients(value, required=True)
        except RecipientValidationError as error:
            raise ValueError(str(error)) from error

    @field_validator("recipient_cc")
    @classmethod
    def valid_optional_cc(cls, value: str | None) -> str | None:
        if value is None:
            return None
        try:
            return normalize_recipients(value, required=False)
        except RecipientValidationError as error:
            raise ValueError(str(error)) from error


class DraftResponse(BaseModel):
    id: UUID
    outreach_item_id: UUID
    resume_id: UUID | None
    linkedin_post_text: str
    job_description_text: str
    no_job_description: bool
    recipient_to: str
    recipient_cc: str | None
    recipient_name: str | None
    company_name: str | None
    subject: str
    body: str
    status: str
    created_at: str
    updated_at: str
    gmail_draft_id: str | None = None
    gmail_message_id: str | None = None
    gmail_sync_status: str = "not_created"
    gmail_sync_error_code: str | None = None
    approval_status: str = "pending"
    approved_at: str | None = None
    send_status: str = "not_sent"
    sent_at: str | None = None
    gmail_sent_message_id: str | None = None
    send_error_code: str | None = None


class GmailDraftResponse(BaseModel):
    gmail_draft_id: str
    gmail_message_id: str | None
    sync_status: str
    created: bool


def get_gmail_draft_service(storage: Storage) -> GmailDraftService:
    return GmailDraftService(storage, get_gmail_oauth_service(storage))


GmailService = Annotated[GmailDraftService, Depends(get_gmail_draft_service)]


def get_gmail_send_service(storage: Storage) -> GmailSendService:
    return GmailSendService(storage, get_gmail_oauth_service(storage))


GmailSend = Annotated[GmailSendService, Depends(get_gmail_send_service)]
Generator = Annotated[EmailGenerator, Depends(get_email_generator)]


class ApprovalResponse(BaseModel):
    approval_status: str
    approved_at: str


class SendResponse(BaseModel):
    send_status: str
    sent_at: str
    gmail_sent_message_id: str


class DraftListResponse(BaseModel):
    drafts: list[DraftResponse]


def _response(record: dict[str, Any]) -> DraftResponse:
    outreach = record.get("outreach_items") or record.get("outreach_item")
    if not isinstance(outreach, dict):
        raise ValueError("Supabase returned an invalid draft.")
    return DraftResponse.model_validate(
        {
            "id": record["id"],
            "outreach_item_id": outreach["id"],
            "resume_id": outreach.get("selected_resume_id"),
            "linkedin_post_text": outreach.get("linkedin_post_text") or "",
            "job_description_text": outreach.get("job_description_text") or "",
            "no_job_description": outreach.get("no_job_description", False),
            "recipient_to": outreach["recipient_to"],
            "recipient_cc": outreach.get("recipient_cc"),
            "recipient_name": outreach.get("recipient_name"),
            "company_name": outreach.get("company_name"),
            "subject": record["subject"],
            "body": record["body"],
            "status": record["draft_status"],
            "created_at": record["created_at"],
            "updated_at": record["updated_at"],
            "gmail_draft_id": record.get("gmail_draft_id"),
            "gmail_message_id": record.get("gmail_message_id"),
            "gmail_sync_status": record.get("gmail_sync_status") or "not_created",
            "gmail_sync_error_code": record.get("gmail_sync_error_code"),
            "approval_status": record.get("approval_status") or "pending",
            "approved_at": record.get("approved_at"),
            "send_status": record.get("send_status") or "not_sent",
            "sent_at": record.get("sent_at"),
            "gmail_sent_message_id": record.get("gmail_sent_message_id"),
            "send_error_code": record.get("send_error_code"),
        }
    )


def _persistence_error(error: Exception) -> HTTPException:
    response = error.response if isinstance(error, httpx.HTTPStatusError) else None
    error_code: object = None
    message: object = None
    details: object = None
    if response is not None:
        try:
            payload = response.json()
        except ValueError:
            payload = {}
        if isinstance(payload, dict):
            error_code = payload.get("code")
            message = payload.get("message")
            details = payload.get("details")
    logger.warning(
        "Draft persistence failure category=%s upstream_status=%s "
        "supabase_code=%s message=%s details=%s",
        type(error).__name__,
        response.status_code if response is not None else None,
        str(error_code)[:100] if error_code is not None else None,
        str(message)[:500] if message is not None else None,
        str(details)[:500] if details is not None else None,
    )
    return HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail="The draft could not be saved. Please try again.",
    )


@router.post("", response_model=DraftResponse, status_code=status.HTTP_201_CREATED)
def create_draft(
    request: DraftCreateRequest, user: CurrentUser, storage: Storage
) -> DraftResponse:
    try:
        resume = storage.get_resume(str(request.resume_id), user["user_id"])
    except httpx.HTTPError as error:
        raise _persistence_error(error) from error
    if resume is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found."
        )
    outreach = {
        "user_id": user["user_id"],
        "linkedin_post_text": request.linkedin_post_text,
        "linkedin_post_url": request.linkedin_post_url,
        "job_description_text": request.job_description_text or None,
        "no_job_description": request.no_job_description,
        "recipient_to": request.recipient_to,
        "recipient_cc": request.recipient_cc,
        "recipient_name": request.recipient_name,
        "company_name": request.company_name,
        "selected_resume_id": str(request.resume_id),
        "status": "ready",
    }
    draft = {
        "user_id": user["user_id"],
        "subject": request.subject,
        "body": request.body,
        "generation_status": "completed",
        "draft_status": "ready_for_review",
    }
    try:
        return _response(storage.create_draft(outreach, draft))
    except (httpx.HTTPError, KeyError, ValueError) as error:
        raise _persistence_error(error) from error


@router.get("/latest", response_model=DraftResponse)
def get_latest_draft(user: CurrentUser, storage: Storage) -> DraftResponse:
    try:
        record = storage.get_latest_draft(user["user_id"])
        if record is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Draft not found."
            )
        return _response(record)
    except HTTPException:
        raise
    except (httpx.HTTPError, ValueError) as error:
        raise _persistence_error(error) from error


@router.get("", response_model=DraftListResponse)
def list_review_drafts(user: CurrentUser, storage: Storage) -> DraftListResponse:
    try:
        return DraftListResponse(
            drafts=[
                _response(record)
                for record in storage.list_review_drafts(user["user_id"])
            ]
        )
    except (httpx.HTTPError, ValueError) as error:
        raise _persistence_error(error) from error


@router.get("/{draft_id}", response_model=DraftResponse)
def get_draft(draft_id: UUID, user: CurrentUser, storage: Storage) -> DraftResponse:
    try:
        record = storage.get_draft(str(draft_id), user["user_id"])
        if record is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Draft not found."
            )
        return _response(record)
    except HTTPException:
        raise
    except (httpx.HTTPError, ValueError) as error:
        raise _persistence_error(error) from error


@router.patch("/{draft_id}", response_model=DraftResponse)
def update_draft(
    draft_id: UUID, request: DraftUpdateRequest, user: CurrentUser, storage: Storage
) -> DraftResponse:
    try:
        existing = storage.get_draft(str(draft_id), user["user_id"])
        if existing is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Draft not found."
            )
        if existing.get("send_status") == "sent":
            raise HTTPException(status_code=409, detail="draft_already_sent")
        record = storage.update_draft(
            str(draft_id),
            user["user_id"],
            {
                "subject": request.subject,
                "body": request.body,
                "draft_status": "ready_for_review",
                "approval_status": "pending",
                "approved_at": None,
                "approved_content_hash": None,
            },
        )
        if record is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Draft not found."
            )
        outreach = existing.get("outreach_items")
        if not isinstance(outreach, dict):
            raise ValueError("Supabase returned an invalid draft.")
        recipient_update = {
            key: value
            for key, value in {
                "recipient_to": request.recipient_to,
                "recipient_cc": request.recipient_cc,
            }.items()
            if value is not None
        }
        if recipient_update:
            updated_outreach = storage.update_draft_recipients(
                str(outreach["id"]), user["user_id"], recipient_update
            )
            if updated_outreach is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="Draft not found."
                )
            outreach = updated_outreach
        resume_changed = request.resume_id is not None and str(
            request.resume_id
        ) != outreach.get("selected_resume_id")
        if resume_changed:
            if storage.get_resume(str(request.resume_id), user["user_id"]) is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found."
                )
            updated_outreach = storage.update_draft_recipients(
                str(outreach["id"]),
                user["user_id"],
                {"selected_resume_id": str(request.resume_id)},
            )
            if updated_outreach is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="Draft not found."
                )
            outreach = updated_outreach
        return _response({**record, "outreach_items": outreach})
    except HTTPException:
        raise
    except (httpx.HTTPError, ValueError) as error:
        raise _persistence_error(error) from error


@router.post("/{draft_id}/regenerate", response_model=DraftResponse)
def regenerate_draft(
    draft_id: UUID, user: CurrentUser, storage: Storage, generator: Generator
) -> DraftResponse:
    try:
        existing = storage.get_draft(str(draft_id), user["user_id"])
        if existing is None or existing.get("draft_status") not in {
            "draft",
            "ready_for_review",
        }:
            raise HTTPException(404, "Draft not found.")
        outreach = existing.get("outreach_items")
        if not isinstance(outreach, dict):
            raise ValueError("Supabase returned an invalid draft.")
        resume_id = outreach.get("selected_resume_id")
        if not isinstance(resume_id, str):
            raise HTTPException(
                422, "The selected resume is not ready for email generation."
            )
        resume = storage.get_resume(resume_id, user["user_id"])
        if (
            resume is None
            or resume.get("parse_status") != "completed"
            or not isinstance(resume.get("extracted_text"), str)
        ):
            raise HTTPException(
                422, "The selected resume is not ready for email generation."
            )
        request = EmailGenerationRequest(
            resume_id=UUID(resume_id),
            linkedin_post_text=outreach.get("linkedin_post_text") or "",
            job_description_text=outreach.get("job_description_text") or "",
            no_job_description=outreach.get("no_job_description", False),
            recipient_to=outreach["recipient_to"],
            recipient_cc=outreach.get("recipient_cc"),
            recipient_name=outreach.get("recipient_name"),
            company_name=outreach.get("company_name"),
        )
        generated = generator.generate(
            build_generation_prompt(resume["extracted_text"], request)
        )
        updated = storage.update_draft(
            str(draft_id),
            user["user_id"],
            {
                "subject": generated.subject,
                "body": generated.body,
                "draft_status": "ready_for_review",
                "approval_status": "pending",
                "approved_at": None,
                "approved_content_hash": None,
            },
        )
        if updated is None:
            raise HTTPException(404, "Draft not found.")
        return _response({**updated, "outreach_items": outreach})
    except ProviderUnavailableError as error:
        raise HTTPException(
            502, "Email generation is temporarily unavailable. Please try again."
        ) from error
    except ValueError as error:
        raise HTTPException(
            502, "Email generation returned an invalid response. Please try again."
        ) from error
    except HTTPException:
        raise
    except httpx.HTTPError as error:
        raise _persistence_error(error) from error


@router.post("/{draft_id}/reject", status_code=status.HTTP_204_NO_CONTENT)
def reject_draft(draft_id: UUID, user: CurrentUser, storage: Storage) -> None:
    record = storage.update_draft(
        str(draft_id),
        user["user_id"],
        {"draft_status": "rejected", "approval_status": "rejected"},
    )
    if record is None:
        raise HTTPException(404, "Draft not found.")


@router.delete("/{draft_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_draft(draft_id: UUID, user: CurrentUser, storage: Storage) -> None:
    record = storage.get_draft(str(draft_id), user["user_id"])
    outreach = record.get("outreach_items") if record else None
    if not isinstance(outreach, dict):
        raise HTTPException(404, "Draft not found.")
    try:
        deleted = storage.delete_outreach_item_permanently(
            user["user_id"], str(outreach["id"])
        )
    except httpx.HTTPError as error:
        raise HTTPException(
            502, "The task could not be deleted. No records were removed."
        ) from error
    if not deleted:
        raise HTTPException(404, "Draft not found.")


@router.post("/{draft_id}/approve", response_model=ApprovalResponse)
def approve_draft(
    draft_id: UUID, user: CurrentUser, storage: Storage
) -> ApprovalResponse:
    try:
        record = storage.get_draft_for_gmail(str(draft_id), user["user_id"])
        if record is None:
            raise HTTPException(status_code=404, detail="Draft not found.")
        if record.get("send_status") == "sent":
            raise HTTPException(status_code=409, detail="draft_already_sent")
        connection = storage.get_gmail_connection(user["user_id"])
        if connection is None or connection.revoked_at is not None:
            raise HTTPException(status_code=409, detail="gmail_authorization_required")
        if not record.get("gmail_draft_id"):
            raise HTTPException(status_code=409, detail="gmail_draft_not_created")
        if record.get("gmail_sync_status") != "synced":
            raise HTTPException(status_code=409, detail="gmail_sync_not_ready")
        content_hash = approval_content_hash(record)
        updated = storage.update_draft(
            str(draft_id),
            user["user_id"],
            {
                "approval_status": "approved",
                "approved_at": datetime.now(timezone.utc).isoformat(),
                "approved_content_hash": content_hash,
            },
        )
        if updated is None:
            raise HTTPException(status_code=404, detail="Draft not found.")
        approved_at = updated.get("approved_at")
        return ApprovalResponse(
            approval_status="approved",
            approved_at=approved_at if isinstance(approved_at, str) else "",
        )
    except RecipientValidationError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None
    except HTTPException:
        raise
    except (httpx.HTTPError, ValueError) as error:
        raise _persistence_error(error) from error


@router.post("/{draft_id}/send", response_model=SendResponse)
async def send_draft(
    draft_id: UUID, user: CurrentUser, storage: Storage, service: GmailSend
) -> SendResponse:
    try:
        record = storage.get_draft_for_gmail(str(draft_id), user["user_id"])
        if record is None:
            raise HTTPException(status_code=404, detail="Draft not found.")
        if record.get("send_status") == "sent":
            raise HTTPException(status_code=409, detail="draft_already_sent")
        connection = storage.get_gmail_connection(user["user_id"])
        if connection is None or connection.revoked_at is not None:
            raise HTTPException(status_code=409, detail="gmail_authorization_required")
        if not record.get("gmail_draft_id"):
            raise HTTPException(status_code=409, detail="gmail_draft_not_created")
        if record.get("gmail_sync_status") != "synced":
            raise HTTPException(status_code=409, detail="gmail_sync_not_ready")
        if record.get("approval_status") != "approved":
            raise HTTPException(status_code=409, detail="draft_not_approved")
        content_hash = approval_content_hash(record)
        if record.get("approved_content_hash") != content_hash:
            raise HTTPException(status_code=409, detail="draft_approval_stale")
        result: GmailSendResult = await service.send(
            user["user_id"], str(draft_id), content_hash
        )
        return SendResponse(
            send_status="sent",
            sent_at=result.sent_at,
            gmail_sent_message_id=result.gmail_sent_message_id,
        )
    except RecipientValidationError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None
    except GmailDraftError as error:
        raise HTTPException(status_code=error.status_code, detail=error.code) from None
    except HTTPException:
        raise
    except (httpx.HTTPError, ValueError) as error:
        raise _persistence_error(error) from error


@router.post("/{draft_id}/gmail", response_model=GmailDraftResponse)
async def create_gmail_draft(
    draft_id: UUID, user: CurrentUser, service: GmailService
) -> GmailDraftResponse:
    try:
        result: GmailDraftResult = await service.create_gmail_draft(
            user["user_id"], str(draft_id)
        )
    except GmailDraftError as error:
        raise HTTPException(status_code=error.status_code, detail=error.code) from None
    if result.gmail_draft_id is None:
        raise HTTPException(status_code=502, detail="gmail_draft_creation_failed")
    return GmailDraftResponse(
        gmail_draft_id=result.gmail_draft_id,
        gmail_message_id=result.gmail_message_id,
        sync_status=result.sync_status,
        created=result.created,
    )


@router.post("/{draft_id}/gmail/sync", response_model=GmailDraftResponse)
async def sync_gmail_draft(
    draft_id: UUID, user: CurrentUser, service: GmailService
) -> GmailDraftResponse:
    try:
        result = await service.update_gmail_draft(user["user_id"], str(draft_id))
    except GmailDraftError as error:
        raise HTTPException(status_code=error.status_code, detail=error.code) from None
    if result.gmail_draft_id is None:
        raise HTTPException(status_code=502, detail="gmail_sync_failed")
    return GmailDraftResponse(
        gmail_draft_id=result.gmail_draft_id,
        gmail_message_id=result.gmail_message_id,
        sync_status=result.sync_status,
        created=False,
    )
