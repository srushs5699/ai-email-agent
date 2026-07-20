"""Authenticated browser-extension import.

JD text is supplied only by the user/browser.
"""

from __future__ import annotations

import logging
import re
from html.parser import HTMLParser
from typing import Annotated, Literal
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator

from auth import AuthenticatedUser, get_current_user
from supabase_admin import (
    ExtensionOrphanRepairError,
    ExtensionQueueAppendError,
    SupabaseAdmin,
    get_supabase_admin,
)

router = APIRouter(prefix="/api/v1/extension", tags=["extension import"])
CurrentUser = Annotated[AuthenticatedUser, Depends(get_current_user)]
Storage = Annotated[SupabaseAdmin, Depends(get_supabase_admin)]
logger = logging.getLogger(__name__)


class ImportRequest(BaseModel):
    version: Literal[1]
    linkedin_post_url: str = Field(max_length=2048)
    author_name: str = Field(max_length=300)
    author_profile_url: str | None = Field(default=None, max_length=2048)
    linkedin_post_text: str = Field(max_length=12000)
    job_description_url: str | None = Field(default=None, max_length=2048)
    job_description_text: str | None = Field(default=None, max_length=50000)
    job_description_source: Literal["visible_page", "manual", "unavailable"] = (
        "unavailable"
    )
    idempotency_key: str = Field(
        default="legacy-extension-import", min_length=8, max_length=100
    )
    captured_at: str = Field(max_length=100)

    @field_validator(
        "author_name",
        "linkedin_post_text",
        "job_description_url",
        "author_profile_url",
        "job_description_text",
        mode="before",
    )
    @classmethod
    def strip_optional(cls, value: object) -> str | None:
        return value.strip() if isinstance(value, str) and value.strip() else None

    @field_validator("linkedin_post_url", "author_profile_url", "job_description_url")
    @classmethod
    def http_urls_only(cls, value: str | None) -> str | None:
        if value is None:
            return None
        parsed = urlsplit(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("URL must use http or https")
        return value


class ImportResult(BaseModel):
    outcome: Literal["queued", "existing", "validation_required", "error"]
    status: Literal["queued", "repaired", "duplicate", "failed"] | None = None
    queue_id: UUID | None = None
    queue_item_id: UUID | None = None
    outreach_item_id: UUID | None = None
    failed_task_id: UUID | None = None
    queue_item_count: int | None = None
    queue_capacity: Literal[10] = 10
    created_new_queue: bool | None = None
    queue_status: str | None = None
    reason: str | None = None
    existing_record_type: str | None = None
    existing_item_path: str | None = None
    job_description_url: str | None = None
    can_capture_in_browser: bool | None = None


class JobPageError(Exception):
    def __init__(self, reason: str) -> None:
        self.reason = reason


def normalize_public_url(value: str) -> str:
    try:
        parsed = urlsplit(value.strip())
    except ValueError as error:
        raise JobPageError("Job description URL was invalid") from error
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.netloc
        or parsed.username
        or parsed.password
    ):
        raise JobPageError("Job description URL was invalid")
    if parsed.hostname not in {"linkedin.com", "www.linkedin.com"}:
        return urlunsplit(
            (
                parsed.scheme,
                parsed.netloc,
                parsed.path.rstrip("/") or "/",
                parsed.query,
                "",
            )
        )
    tracking = {
        "trk",
        "trackingid",
        "lipi",
        "utm_source",
        "utm_medium",
        "utm_campaign",
        "utm_term",
        "utm_content",
    }
    query = urlencode(
        [
            (key, item)
            for key, item in parse_qsl(parsed.query, keep_blank_values=True)
            if key.lower() not in tracking
        ]
    )
    return urlunsplit(
        (
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            parsed.path.rstrip("/"),
            query,
            "",
        )
    )


class _TextExtractor(HTMLParser):
    ignored = {
        "script",
        "style",
        "noscript",
        "svg",
        "nav",
        "footer",
        "header",
        "aside",
        "form",
        "button",
    }
    blocks = {
        "p",
        "div",
        "li",
        "h1",
        "h2",
        "h3",
        "h4",
        "section",
        "article",
        "br",
        "main",
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self.ignored:
            self.skip += 1
        if not self.skip and tag in self.blocks:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in self.ignored and self.skip:
            self.skip -= 1
        if not self.skip and tag in self.blocks:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self.skip:
            self.parts.append(data)


def extract_job_description(html: str) -> str:
    parser = _TextExtractor()
    parser.feed(html)
    lines = [
        re.sub(r"\s+", " ", line).strip() for line in "".join(parser.parts).splitlines()
    ]
    boilerplate = re.compile(
        r"^(cookie|privacy|terms|sign in|log in|accept all|skip to content|navigation)",
        re.I,
    )
    return "\n".join(
        line for line in lines if len(line) > 1 and not boilerplate.match(line)
    )[:50000]


def classify_job_description_unavailable(
    status_code: int | None = None,
    body: str = "",
    content_type: str | None = None,
    timed_out: bool = False,
) -> str | None:
    """Classify unsafe/unavailable retrieval outcomes without attempting a request."""
    if timed_out:
        return "Job description retrieval timed out"
    if status_code in {401, 403, 429}:
        return "Job description is unavailable from this page"
    if content_type and not content_type.lower().startswith(
        ("text/html", "text/plain")
    ):
        return "Job description returned unsupported content"
    if re.search(
        (
            r"captcha|cloudflare|access denied|verify you are human|login|required|"
            r"enable javascript"
        ),
        body,
        re.I,
    ):
        return "Job description is unavailable from this page"
    return None


def _metadata(
    request: ImportRequest,
    source_url: str,
    job_url: str | None = None,
    text: str | None = None,
    capture_source: str | None = None,
) -> dict[str, object]:
    return {
        "linkedin_post_url": source_url,
        "author_name": request.author_name,
        "author_profile_url": request.author_profile_url,
        "linkedin_post_text": request.linkedin_post_text,
        "job_description_url": job_url or request.job_description_url,
        "job_description_text": text,
        "job_description_source": capture_source or request.job_description_source,
        "capture_source": "browser_extension",
        "captured_at": request.captured_at,
        "job_description_warning": (
            "The job description could not be extracted automatically. You can "
            "paste it manually or continue without it."
        )
        if not text
        else None,
        "idempotency_key": request.idempotency_key,
    }


@router.post("/import", response_model=ImportResult)
def import_capture(
    request: ImportRequest, user: CurrentUser, storage: Storage
) -> ImportResult:
    try:
        source_url = normalize_public_url(request.linkedin_post_url)
    except JobPageError as error:
        return ImportResult(outcome="validation_required", reason=error.reason)
    reviewed_text = request.job_description_text
    metadata = _metadata(request, source_url, text=reviewed_text)
    if not request.author_name:
        return ImportResult(
            outcome="validation_required", reason="Author name is required"
        )
    if len(request.linkedin_post_text) < 3:
        return ImportResult(
            outcome="validation_required", reason="LinkedIn post text is required"
        )
    logger.info(
        "extension_import_lookup user_id=%s linkedin_url=%s",
        user["user_id"],
        source_url,
    )
    duplicate = storage.find_extension_duplicate(user["user_id"], source_url)
    if duplicate:
        logger.info(
            "extension_import_duplicate user_id=%s state=%s record_id=%s "
            "outreach_item_id=%s",
            user["user_id"],
            duplicate.get("record_type"),
            duplicate.get("id"),
            duplicate.get("outreach_item_id"),
        )
        # A failed prior transaction may leave the outreach capture without its
        # queue row. Repair it atomically; it is not a user-visible duplicate.
        if duplicate.get("record_type") == "orphaned_outreach":
            try:
                logger.info(
                    "extension_orphan_repair_attempt user_id=%s outreach_item_id=%s",
                    user["user_id"],
                    duplicate["outreach_item_id"],
                )
                saved = storage.repair_extension_orphan(
                    user["user_id"], str(duplicate["outreach_item_id"]), metadata
                )
            except ExtensionOrphanRepairError as error:
                logger.warning(
                    "extension_orphan_repair_rejected user_id=%s detail=%s",
                    user["user_id"],
                    error,
                )
                raise HTTPException(
                    status.HTTP_502_BAD_GATEWAY,
                    "Unable to repair the existing extension capture because storage "
                    "rejected the operation.",
                ) from error
            if saved is not None:
                logger.info(
                    "extension_orphan_repair_succeeded user_id=%s "
                    "outreach_item_id=%s result=%s",
                    user["user_id"],
                    saved.get("outreach_item_id"),
                    saved.get("repair_status", "repaired"),
                )
                return ImportResult(
                    outcome="queued",
                    status="repaired",
                    queue_id=saved["queue_id"],
                    queue_item_id=saved["queue_item_id"],
                    outreach_item_id=saved.get("outreach_item_id"),
                    queue_item_count=saved.get("queue_item_count"),
                    created_new_queue=saved.get("created_new_queue"),
                    queue_status=saved.get("queue_status"),
                    reason="Existing capture repaired.",
                )
            logger.info(
                "extension_orphan_repair_missing_fallback_create user_id=%s "
                "outreach_item_id=%s",
                user["user_id"],
                duplicate.get("outreach_item_id"),
            )
        if duplicate.get("record_type") != "orphaned_outreach":
            return ImportResult(
                outcome="existing",
                status="duplicate",
                queue_id=duplicate.get("queue_id"),
                queue_item_id=duplicate.get("id"),
                outreach_item_id=duplicate.get("outreach_item_id"),
                reason=duplicate["location"],
                existing_record_type=duplicate.get("record_type"),
                existing_item_path=duplicate.get("open_path"),
            )
    # Never fetch an arbitrary job site from the backend. A missing/blocked JD is
    # useful context, not an outreach processing failure.
    metadata = _metadata(
        request, source_url, request.job_description_url, reviewed_text
    )
    try:
        saved = storage.append_extension_processing_queue_item(
            user["user_id"], metadata
        )
    except ExtensionQueueAppendError as error:
        logger.warning(
            "extension_queue_append_rejected user_id=%s reason=%s",
            user["user_id"],
            error,
        )
        return ImportResult(outcome="error", reason=str(error))
    return ImportResult(
        outcome="queued",
        status="queued",
        queue_id=saved["queue_id"],
        queue_item_id=saved["queue_item_id"],
        outreach_item_id=saved.get("outreach_item_id"),
        queue_item_count=saved["queue_item_count"],
        created_new_queue=saved["created_new_queue"],
        queue_status=saved["queue_status"],
    )


def _failed(
    storage: SupabaseAdmin,
    user_id: str,
    metadata: dict[str, object],
    reason: str,
    stage: str,
) -> ImportResult:
    failed = storage.create_extension_failed_task(user_id, metadata, reason, stage)
    if not failed.get("id") or failed.get("status") != "failed":
        raise RuntimeError(
            "Failed-task persistence did not return a visible failed record."
        )
    confirmed = storage.get_failed_task(str(failed["id"]), user_id)
    if (
        not confirmed
        or confirmed.get("status") != "failed"
        or confirmed.get("hidden_at") is not None
    ):
        raise RuntimeError("Failed-task persistence could not be verified.")
    return ImportResult(
        outcome="error", status="failed", failed_task_id=failed["id"], reason=reason
    )
