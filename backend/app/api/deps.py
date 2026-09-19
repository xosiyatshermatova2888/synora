"""Auth + tenant + RBAC dependencies.

- `get_current_user`: resolves the bearer access token, returns the User.
- `get_current_tenant`: extracts `restaurant_id` from the JWT claims (Section
  5A) — the ONLY source of tenant identity; never trusts a request body/param.
- `require_permission`: guards a route against the user's resolved permission
  set (from the JWT `perms` claim). Single place where authorization lives.
- `require_login_rate_limit`: protects the login endpoint (per IP + account).
"""

import uuid

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import decode_token
from app.database.session import get_db
from app.models.user import User
from app.utils.errors import ForbiddenError, RateLimitedError, UnauthorizedError
from app.utils.rate_limit import login_blocked, record_login_failure

bearer_scheme = HTTPBearer(auto_error=False)


async def get_client_ip(request: Request) -> str:
    # Trust Proxy headers in production; for local dev, fall back to socket.
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> tuple[User, dict]:
    if credentials is None:
        raise UnauthorizedError(detail="Not authenticated.")
    try:
        payload = decode_token(credentials.credentials)
    except JWTError as exc:
        raise UnauthorizedError(detail="Invalid or expired access token.") from exc

    if payload.get("typ") != "access":
        raise UnauthorizedError(detail="Invalid token type.")

    user = await db.get(User, uuid.UUID(str(payload["sub"])))
    if user is None or not user.is_active or user.deleted_at is not None:
        raise UnauthorizedError(detail="User is inactive or deleted.")
    return user, payload


async def get_current_tenant(
    auth: tuple[User, dict] = Depends(get_current_user),
) -> uuid.UUID:
    """Dependency returning the current restaurant_id from JWT claims."""
    _, payload = auth
    try:
        return uuid.UUID(str(payload["rid"]))
    except (KeyError, ValueError):
        raise UnauthorizedError(detail="Invalid tenant in token.")


async def get_current_user_restaurant(
    auth: tuple[User, dict] = Depends(get_current_user),
) -> User:
    user, _ = auth
    return user


def require_permission(permission_code: str):
    async def _check(auth: tuple[User, dict] = Depends(get_current_user)) -> None:
        _, payload = auth
        perms = payload.get("perms") or []
        if permission_code not in perms:
            raise ForbiddenError(detail=f"Permission '{permission_code}' required.")
        return None

    return _check


async def require_login_rate_limit(
    request: Request,
    username: str | None = None,
) -> None:
    ip = await get_client_ip(request)
    key = username.lower() if username else "?"
    if login_blocked(key, ip):
        raise RateLimitedError(detail="Too many login attempts. Try again later.")

    # record a failure marker for the pre-check on next request (even before
    # we attempt credentials); real failure accounting happens in the route.
    return None