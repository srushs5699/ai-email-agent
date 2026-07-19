from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from auth import AuthenticatedUser, get_current_user
from gmail_oauth import (
    GmailConnectionStatus,
    GmailOAuthError,
    GmailOAuthService,
    configured_callback_url,
)
from supabase_admin import SupabaseAdmin, get_supabase_admin

router = APIRouter(prefix="/api/v1/gmail", tags=["gmail"])
CurrentUser = Annotated[AuthenticatedUser, Depends(get_current_user)]
Storage = Annotated[SupabaseAdmin, Depends(get_supabase_admin)]


class GmailStatusResponse(BaseModel):
    configured: bool
    connected: bool
    authorization_required: bool
    google_email: str | None
    granted_scopes: list[str]


class GmailAuthorizationResponse(BaseModel):
    authorization_url: str


def get_gmail_oauth_service(storage: Storage) -> GmailOAuthService:
    return GmailOAuthService(storage)


GmailService = Annotated[GmailOAuthService, Depends(get_gmail_oauth_service)]


def _status_response(status: GmailConnectionStatus) -> GmailStatusResponse:
    return GmailStatusResponse(
        configured=status.configured,
        connected=status.connected,
        authorization_required=status.authorization_required,
        google_email=status.google_email,
        granted_scopes=list(status.granted_scopes),
    )


def _http_error(error: GmailOAuthError) -> HTTPException:
    return HTTPException(status_code=error.status_code, detail=error.code)


@router.get("/status", response_model=GmailStatusResponse)
def gmail_status(user: CurrentUser, service: GmailService) -> GmailStatusResponse:
    try:
        return _status_response(service.get_connection_status(user["user_id"]))
    except GmailOAuthError as error:
        raise _http_error(error) from None


@router.get("/authorize", response_model=GmailAuthorizationResponse)
def gmail_authorize(
    user: CurrentUser, service: GmailService
) -> GmailAuthorizationResponse:
    try:
        return GmailAuthorizationResponse(
            authorization_url=service.build_authorization_url(user["user_id"])
        )
    except GmailOAuthError as error:
        raise _http_error(error) from None


@router.get("/callback", response_model=None)
async def gmail_callback(
    service: GmailService,
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
) -> RedirectResponse | dict[str, str]:
    try:
        if error:
            await service.handle_oauth_denial(state)
        await service.handle_oauth_callback(code, state)
    except GmailOAuthError as oauth_error:
        error_url = configured_callback_url("GMAIL_OAUTH_ERROR_URL")
        if error_url:
            return RedirectResponse(error_url, status_code=303)
        raise _http_error(oauth_error) from None
    success_url = configured_callback_url("GMAIL_OAUTH_SUCCESS_URL")
    if success_url:
        return RedirectResponse(success_url, status_code=303)
    return {"status": "connected"}
