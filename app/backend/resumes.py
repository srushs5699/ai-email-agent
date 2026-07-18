import os
import re
from io import BytesIO
from pathlib import Path
from typing import Annotated, Any
from uuid import UUID, uuid4

import httpx
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel
from pypdf import PdfReader
from pypdf.errors import PdfReadError

from auth import AuthenticatedUser, get_current_user
from supabase_admin import SupabaseAdmin, get_supabase_admin

router = APIRouter(prefix="/api/v1/resumes", tags=["resumes"])
CurrentUser = Annotated[AuthenticatedUser, Depends(get_current_user)]
Storage = Annotated[SupabaseAdmin, Depends(get_supabase_admin)]
MAX_UPLOAD_BYTES_DEFAULT = 10 * 1024 * 1024


class ResumeMetadata(BaseModel):
    id: UUID
    name: str
    mime_type: str
    file_size_bytes: int
    parse_status: str
    created_at: str


def _max_upload_bytes() -> int:
    configured_value = os.getenv(
        "RESUME_MAX_UPLOAD_BYTES", str(MAX_UPLOAD_BYTES_DEFAULT)
    )
    try:
        value = int(configured_value)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Resume upload is not configured.",
        ) from error
    if value <= 0:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Resume upload is not configured.",
        )
    return value


def _safe_pdf_filename(filename: str) -> str:
    base_name = Path(filename).stem.lower()
    sanitized = re.sub(r"[^a-z0-9]+", "-", base_name).strip("-")
    return f"{sanitized or 'resume'}.pdf"


def _extract_pdf_text(content: bytes) -> str:
    try:
        reader = PdfReader(BytesIO(content))
        if reader.is_encrypted and reader.decrypt("") == 0:
            raise ValueError("encrypted PDF")
        text = "\n".join(page.extract_text() or "" for page in reader.pages).strip()
    except (PdfReadError, ValueError, OSError) as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="The PDF could not be read. Upload a text-based PDF.",
        ) from error

    if not text:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="The PDF has no extractable text. OCR is not supported.",
        )
    return text


def _metadata(record: dict[str, Any]) -> ResumeMetadata:
    return ResumeMetadata.model_validate(record)


@router.post("", response_model=ResumeMetadata, status_code=status.HTTP_201_CREATED)
async def upload_resume(
    user: CurrentUser,
    storage: Storage,
    file: Annotated[UploadFile, File(...)],
) -> ResumeMetadata:
    filename = file.filename or ""
    if (
        Path(filename).suffix.lower() != ".pdf"
        or file.content_type != "application/pdf"
    ):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Only application/pdf files are accepted.",
        )

    max_upload_bytes = _max_upload_bytes()
    content = await file.read(max_upload_bytes + 1)
    if not content:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The uploaded PDF is empty.",
        )
    if len(content) > max_upload_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="The uploaded PDF exceeds the configured size limit.",
        )

    extracted_text = _extract_pdf_text(content)
    resume_id = uuid4()
    storage_path = f"{user['user_id']}/{resume_id}/{_safe_pdf_filename(filename)}"
    record = {
        "id": str(resume_id),
        "user_id": user["user_id"],
        "name": Path(filename).stem or "Resume",
        "storage_path": storage_path,
        "mime_type": "application/pdf",
        "file_size_bytes": len(content),
        "extracted_text": extracted_text,
        "parse_status": "completed",
        "parse_error": None,
    }

    try:
        storage.upload_resume(storage_path, content)
    except httpx.HTTPError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The resume file could not be stored.",
        ) from error

    try:
        inserted_record = storage.insert_resume(record)
    except (httpx.HTTPError, ValueError) as error:
        try:
            storage.remove_resume(storage_path)
        except httpx.HTTPError:
            pass
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The resume metadata could not be saved.",
        ) from error

    return _metadata(inserted_record)


@router.get("", response_model=list[ResumeMetadata])
def list_resumes(user: CurrentUser, storage: Storage) -> list[ResumeMetadata]:
    try:
        return [_metadata(record) for record in storage.list_resumes(user["user_id"])]
    except (httpx.HTTPError, ValueError) as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Resumes could not be loaded.",
        ) from error


@router.delete("/{resume_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_resume(resume_id: UUID, user: CurrentUser, storage: Storage) -> None:
    try:
        resume = storage.get_resume(str(resume_id), user["user_id"])
    except httpx.HTTPError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The resume could not be loaded.",
        ) from error
    if resume is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found."
        )

    storage_path = resume.get("storage_path")
    if not isinstance(storage_path, str):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The resume could not be deleted.",
        )
    try:
        storage.remove_resume(storage_path)
        deleted_resume = storage.delete_resume(str(resume_id), user["user_id"])
    except httpx.HTTPError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The resume could not be deleted.",
        ) from error
    if deleted_resume is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found."
        )
