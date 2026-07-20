"""Permanent, owned deletion of a workflow item and its dependent data."""

import logging
from typing import Annotated
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth import AuthenticatedUser, get_current_user
from supabase_admin import SupabaseAdmin, get_supabase_admin

router = APIRouter(prefix="/api/v1/outreach-items", tags=["outreach items"])
logger = logging.getLogger(__name__)
CurrentUser = Annotated[AuthenticatedUser, Depends(get_current_user)]
Storage = Annotated[SupabaseAdmin, Depends(get_supabase_admin)]


class DeleteOutreachItemResponse(BaseModel):
    deleted: bool
    outreach_item_id: UUID


@router.delete("/{outreach_item_id}", response_model=DeleteOutreachItemResponse)
def delete_outreach_item(
    outreach_item_id: UUID, user: CurrentUser, storage: Storage
) -> DeleteOutreachItemResponse:
    logger.info(
        "outreach_delete_requested user_id=%s outreach_item_id=%s",
        user["user_id"],
        outreach_item_id,
    )
    try:
        if not storage.delete_outreach_item_permanently(
            user["user_id"], str(outreach_item_id)
        ):
            raise HTTPException(404, "Outreach item not found.")
    except HTTPException:
        raise
    except httpx.HTTPError as error:
        logger.exception(
            "outreach_delete_failed user_id=%s outreach_item_id=%s",
            user["user_id"],
            outreach_item_id,
        )
        raise HTTPException(
            502, "The task could not be deleted. No records were removed."
        ) from error
    logger.info(
        "outreach_delete_succeeded user_id=%s outreach_item_id=%s "
        "related_records=transactional",
        user["user_id"],
        outreach_item_id,
    )
    return DeleteOutreachItemResponse(deleted=True, outreach_item_id=outreach_item_id)
