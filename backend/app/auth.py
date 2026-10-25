"""Supabase JWT verification and the user dependencies routers depend on.

The browser signs in with Supabase Auth and sends its access token as
`Authorization: Bearer <jwt>`. We verify it locally: HS256 with the project's
JWT secret when SUPABASE_JWT_SECRET is set (legacy projects), otherwise against
the project's JWKS (asymmetric signing keys).
"""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated, Any

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from app.config import get_settings

AUDIENCE = "authenticated"

_bearer = HTTPBearer(auto_error=False)


class CurrentUser(BaseModel):
    id: str
    email: str = ""
    full_name: str = ""
    is_admin: bool = False
    is_demo: bool = False


class AuthError(Exception):
    """Token missing, malformed, expired or signed by someone else."""


@lru_cache
def _jwks_client() -> jwt.PyJWKClient:
    url = get_settings().supabase_url.rstrip("/")
    if not url:
        raise AuthError("SUPABASE_URL is not configured")
    return jwt.PyJWKClient(f"{url}/auth/v1/.well-known/jwks.json", cache_keys=True)


def decode_token(token: str) -> dict[str, Any]:
    """Verify a Supabase access token and return its claims."""
    settings = get_settings()
    try:
        if settings.supabase_jwt_secret:
            return jwt.decode(
                token, settings.supabase_jwt_secret, algorithms=["HS256"], audience=AUDIENCE
            )
        key = _jwks_client().get_signing_key_from_jwt(token).key
        return jwt.decode(token, key, algorithms=["ES256", "RS256"], audience=AUDIENCE)
    except jwt.PyJWTError as exc:
        raise AuthError(str(exc)) from exc


def user_from_claims(claims: dict[str, Any]) -> CurrentUser:
    app_meta = claims.get("app_metadata") or {}
    user_meta = claims.get("user_metadata") or {}
    return CurrentUser(
        id=claims["sub"],
        email=claims.get("email") or "",
        full_name=user_meta.get("full_name") or user_meta.get("name") or "",
        is_admin=app_meta.get("role") == "admin",
        is_demo=bool(app_meta.get("demo")),
    )


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> CurrentUser:
    if credentials is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Not signed in.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        return user_from_claims(decode_token(credentials.credentials))
    except (AuthError, KeyError) as exc:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Your session is invalid or has expired. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


def get_writer(user: Annotated[CurrentUser, Depends(get_current_user)]) -> CurrentUser:
    """A signed-in user allowed to change data (the shared demo account is read-only)."""
    if user.is_demo:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "This is the read-only demo. Create a free account to save your own profile.",
        )
    return user


def require_admin(user: Annotated[CurrentUser, Depends(get_current_user)]) -> CurrentUser:
    if not user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admins only.")
    return user


User = Annotated[CurrentUser, Depends(get_current_user)]
Writer = Annotated[CurrentUser, Depends(get_writer)]
Admin = Annotated[CurrentUser, Depends(require_admin)]
