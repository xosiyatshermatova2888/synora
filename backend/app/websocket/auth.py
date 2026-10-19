"""Shared WebSocket auth helpers — used by every `/ws/*` endpoint (kitchen,
notifications). Auth happens BEFORE `accept()`, via the SAME
`core.security.decode_token` the REST dependencies use; tenant identity comes
only from the JWT's `rid` claim, never a client-supplied value (Section 5A).
"""

import uuid

from jose import JWTError
from sqlalchemy import select

from app.core.security import decode_token
from app.database.session import SessionLocal
from app.models.branch import Branch
from app.models.user import User

# Close codes (1015-4999 are app-defined in the WebSocket protocol).
AUTH_FAILED_CODE = 4001  # invalid / expired token
BAD_BRANCH_CODE = 4404   # branch_id does not belong to this restaurant


def extract_restaurant(token: str) -> uuid.UUID | None:
    try:
        payload = decode_token(token)
    except JWTError:
        return None
    if payload.get("typ") != "access":
        return None
    try:
        return uuid.UUID(str(payload["rid"]))
    except (KeyError, ValueError, TypeError):
        return None


async def user_still_active(token: str) -> bool:
    """REST re-checks the user on every request; a socket lives for hours, so
    check once at connect that the account is still active."""
    try:
        sub = uuid.UUID(str(decode_token(token)["sub"]))
    except (JWTError, KeyError, ValueError, TypeError):
        return False
    async with SessionLocal() as session:
        user = await session.get(User, sub)
    return user is not None and user.is_active and user.deleted_at is None


async def validate_branch(restaurant_id: uuid.UUID, raw: str | None) -> uuid.UUID | None:
    """Return the validated branch for the tenant, or None when absent/ambiguous."""
    if raw is None or raw == "":
        return None
    try:
        branch_uuid = uuid.UUID(str(raw))
    except ValueError:
        return None
    async with SessionLocal() as session:
        branch = await session.scalar(
            select(Branch).where(
                Branch.restaurant_id == restaurant_id,
                Branch.id == branch_uuid,
            )
        )
    return branch_uuid if branch is not None else None
