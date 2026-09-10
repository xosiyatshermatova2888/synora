"""Authenticated kitchen WebSocket endpoint (Phase K).

WS /api/v1/ws/kitchen?token=<access_token>[&branch_id=<uuid>]

Auth happens BEFORE `accept()`: the token is decoded with the SAME
`core.security.decode_token` the REST dependencies use (never a re-implementation
of JWT verification). Invalid/expired tokens are rejected with a close code —
never a silent hang.

Tenant identity comes only from the JWT claims (`rid`); a client-supplied
`branch_id` is validated to belong to that restaurant or the connection is
closed. Events are registered under the tenant key and fan out only within it
(Section 5A / Section 3).
"""

import uuid

from fastapi import APIRouter, WebSocket
from jose import JWTError
from sqlalchemy import select

from app.core.security import decode_token
from app.database.session import SessionLocal
from app.models.branch import Branch
from app.websocket.manager import manager

router = APIRouter()

# Close codes (1015-4999 are app-defined in the WebSocket protocol).
AUTH_FAILED_CODE = 4001  # invalid / expired token
BAD_BRANCH_CODE = 4404   # branch_id does not belong to this restaurant


def _extract_restaurant(token: str) -> uuid.UUID | None:
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


async def _validate_branch(restaurant_id: uuid.UUID, raw: str | None) -> uuid.UUID | None:
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


@router.websocket("/ws/kitchen")
async def kitchen_ws(websocket: WebSocket) -> None:
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=AUTH_FAILED_CODE)
        return
    restaurant_id = _extract_restaurant(token)
    if restaurant_id is None:
        await websocket.close(code=AUTH_FAILED_CODE)
        return

    branch_id = await _validate_branch(restaurant_id, websocket.query_params.get("branch_id"))
    if "branch_id" in websocket.query_params and branch_id is None:
        await websocket.close(code=BAD_BRANCH_CODE)
        return

    await websocket.accept()
    await manager.connect(restaurant_id, branch_id, websocket)
    try:
        # This endpoint only pushes events; we ignore client frames and simply
        # await the disconnect so the registry entry is cleaned up correctly.
        while True:
            message = await websocket.receive()
            if message["type"] == "websocket.disconnect":
                break
    except Exception:
        pass
    finally:
        await manager.disconnect(restaurant_id, branch_id, websocket)