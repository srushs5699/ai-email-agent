import os

from fastapi import HTTPException, status

GMAIL_COMPOSE_SCOPE = "https://www.googleapis.com/auth/gmail.compose"


def gmail_scopes() -> tuple[str, ...]:
    configured = os.getenv("GMAIL_OAUTH_SCOPES", GMAIL_COMPOSE_SCOPE)
    return tuple(scope for scope in configured.split() if scope)


def required_gmail_config() -> dict[str, str]:
    names = (
        "GMAIL_OAUTH_CLIENT_ID",
        "GMAIL_OAUTH_CLIENT_SECRET",
        "GMAIL_OAUTH_REDIRECT_URI",
        "GMAIL_TOKEN_ENCRYPTION_KEY",
    )
    values = {name: os.getenv(name, "").strip() for name in names}
    if not all(values.values()):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Gmail integration is not configured.",
        )
    return values
