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
from app.services.subscription import ensure_can_write, require_feature_for
from app.utils.errors import ForbiddenError, RateLimitedError, UnauthorizedError
from app.utils.rate_limit import login_blocked, record_login_failure

bearer_scheme = HTTPBearer(auto_error=False)


async def get_client_ip(request: Request) -> str:
    # Trust Proxy headers in production; for local dev, fall back to socket.
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        # The LAST entry is the one our own proxy (Caddy/Next) appended; earlier
        # entries are whatever the client claimed, so they must not pick the
        # rate-limit bucket.
        return forwarded.split(",")[-1].strip()
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


# URL segments (after /api/v1/) a restaurant may still WRITE to once its
# subscription has lapsed: it must be able to log in/out and pay to recover.
_WRITABLE_WHEN_EXPIRED = {"auth", "subscription", "platform", "uploads"}
_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def _api_segment(path: str) -> str:
    parts = [p for p in path.split("/") if p]
    return parts[2] if len(parts) > 2 and parts[0] == "api" else ""


async def get_current_tenant(
    request: Request,
    auth: tuple[User, dict] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> uuid.UUID:
    """Dependency returning the current restaurant_id from JWT claims.

    Also the read-only gate: after the 7-day grace period a lapsed
    subscription refuses every state-changing request (402).
    """
    _, payload = auth
    try:
        tenant_id = uuid.UUID(str(payload["rid"]))
    except (KeyError, ValueError):
        raise UnauthorizedError(detail="Invalid tenant in token.")

    if request.method not in _SAFE_METHODS and _api_segment(request.url.path) not in _WRITABLE_WHEN_EXPIRED:
        await ensure_can_write(db, tenant_id)
    return tenant_id


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


def require_feature(feature: str):
    """Plan gate: 402 `plan_upgrade_required` unless the plan includes `feature`."""

    async def _check(
        tenant_id: uuid.UUID = Depends(get_current_tenant),
        db: AsyncSession = Depends(get_db),
    ) -> None:
        await require_feature_for(db, tenant_id, feature)

    return _check


async def require_platform_admin(auth: tuple[User, dict] = Depends(get_current_user)) -> User:
    user, _ = auth
    if not user.is_platform_admin:
        raise ForbiddenError(detail="Platform administrator access required.")
    return user


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