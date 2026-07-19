import logging
import re
from typing import Annotated, Any
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, field_validator

from auth import AuthenticatedUser, get_current_user
from supabase_admin import SupabaseAdmin, get_supabase_admin

router = APIRouter(prefix="/api/v1/drafts", tags=["drafts"])
logger = logging.getLogger(__name__)
CurrentUser = Annotated[AuthenticatedUser, Depends(get_current_user)]
Storage = Annotated[SupabaseAdmin, Depends(get_supabase_admin)]
EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


class DraftCreateRequest(BaseModel):
    resume_id: UUID
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
        value = value.strip()
        if not EMAIL_PATTERN.fullmatch(value):
            raise ValueError("Enter a valid email address.")
        return value

    @field_validator("recipient_cc", "recipient_name", "company_name")
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

    @field_validator("subject", "body")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Draft content must not be blank.")
        return value


class DraftResponse(BaseModel):
    id: UUID
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


def _response(record: dict[str, Any]) -> DraftResponse:
    outreach = record.get("outreach_items") or record.get("outreach_item")
    if not isinstance(outreach, dict):
        raise ValueError("Supabase returned an invalid draft.")
    return DraftResponse.model_validate(
        {
            "id": record["id"],
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
        record = storage.update_draft(
            str(draft_id),
            user["user_id"],
            {
                "subject": request.subject,
                "body": request.body,
                "draft_status": "ready_for_review",
            },
        )
        if record is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Draft not found."
            )
        return _response({**record, "outreach_items": existing.get("outreach_items")})
    except HTTPException:
        raise
    except (httpx.HTTPError, ValueError) as error:
        raise _persistence_error(error) from error
