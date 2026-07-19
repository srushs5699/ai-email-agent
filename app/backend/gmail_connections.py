"""Internal Gmail persistence models.

These records are deliberately not FastAPI response models.  Encrypted token
values stay within backend persistence and OAuth services.
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class GmailConnectionRecord:
    id: str
    user_id: str
    google_email: str | None
    encrypted_refresh_token: str
    access_token: str | None
    access_token_expires_at: datetime | None
    granted_scopes: tuple[str, ...]
    revoked_at: datetime | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class GmailConnectionUpsert:
    google_email: str | None = None
    encrypted_refresh_token: str | None = None
    access_token: str | None = None
    access_token_expires_at: datetime | None = None
    granted_scopes: tuple[str, ...] | None = None


@dataclass(frozen=True)
class OAuthStateRecord:
    state_hash: str
    user_id: str
    expires_at: datetime
    created_at: datetime
