import os
from functools import lru_cache
from typing import Annotated, Any, 
from typing_extensions import TypedDict

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient, PyJWKClientError
from jwt.exceptions import InvalidTokenError

bearer_scheme = HTTPBearer(auto_error=False)
_asymmetric_algorithms = {"ES256", "ES384", "ES512", "RS256", "RS384", "RS512"}


class AuthenticatedUser(TypedDict):
    email: str | None
    user_id: str


def _unauthorized_exception() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired access token",
        headers={"WWW-Authenticate": "Bearer"},
    )


def _supabase_url() -> str:
    supabase_url = os.getenv("SUPABASE_URL")
    if not supabase_url:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="SUPABASE_URL is not configured",
        )

    return supabase_url.rstrip("/")


def _expected_audience() -> str:
    return os.getenv("SUPABASE_JWT_AUDIENCE", "authenticated")


@lru_cache
def _get_jwks_client(supabase_url: str) -> PyJWKClient:
    return PyJWKClient(
        f"{supabase_url}/auth/v1/.well-known/jwks.json",
        cache_keys=True,
        cache_jwk_set=True,
        lifespan=300,
    )


def _decode_access_token(token: str) -> dict[str, Any]:
    supabase_url = _supabase_url()
    issuer = f"{supabase_url}/auth/v1"

    try:
        algorithm = jwt.get_unverified_header(token).get("alg")

        if algorithm == "HS256":
            jwt_secret = os.getenv("SUPABASE_JWT_SECRET")
            if not jwt_secret:
                raise _unauthorized_exception()
            signing_key: str | Any = jwt_secret
        elif algorithm in _asymmetric_algorithms:
            signing_key = (
                _get_jwks_client(supabase_url).get_signing_key_from_jwt(token).key
            )
        else:
            raise _unauthorized_exception()

        return jwt.decode(
            token,
            signing_key,
            algorithms=[algorithm],
            audience=_expected_audience(),
            issuer=issuer,
        )
    except HTTPException:
        raise
    except (InvalidTokenError, PyJWKClientError, ValueError) as error:
        raise _unauthorized_exception() from error


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> AuthenticatedUser:
    if credentials is None or not credentials.credentials:
        raise _unauthorized_exception()

    claims = _decode_access_token(credentials.credentials)
    user_id = claims.get("sub")

    if not isinstance(user_id, str) or not user_id:
        raise _unauthorized_exception()

    email = claims.get("email")
    return {"user_id": user_id, "email": email if isinstance(email, str) else None}
