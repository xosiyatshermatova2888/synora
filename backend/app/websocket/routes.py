"""Authenticated WebSocket endpoints (Phase K, extended Phase 4).

WS /api/v1/ws/kitchen?token=<access_token>[&branch_id=<uuid>]
WS /api/v1/ws/notifications?token=<access_token>[&branch_id=<uuid>]

Auth happens BEFORE `accept()` — see `app/websocket/auth.py` (shared by both
endpoints, not duplicated). Tenant identity comes only from the JWT claims
(`rid`); a client-supplied `branch_id` is validated to belong to that
restaurant or the connection is closed. Events are registered under the
tenant key and fan out only within it (Section 5A / Section 3).
"""

from fastapi import APIRouter, WebSocket

from app.websocket.auth import (
    AUTH_FAILED_CODE,
    BAD_BRANCH_CODE,
    extract_restaurant,
    user_still_active,
    validate_branch,
)
from app.websocket.manager import manager

router = APIRouter()


async def _run_socket(websocket: WebSocket) -> None:
    """Shared connect/listen/cleanup loop — identical for every `/ws/*`
    endpoint below; only the registry key scope differs per caller."""
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=AUTH_FAILED_CODE)
        return None
    restaurant_id = extract_restaurant(token)
    if restaurant_id is None:
        await websocket.close(code=AUTH_FAILED_CODE)
        return None

    if not await user_still_active(token):
        await websocket.close(code=AUTH_FAILED_CODE)
        return None

    branch_id = await validate_branch(restaurant_id, websocket.query_params.get("branch_id"))
    if "branch_id" in websocket.query_params and branch_id is None:
        await websocket.close(code=BAD_BRANCH_CODE)
        return None

    await websocket.accept()
    await manager.connect(restaurant_id, branch_id, websocket)
    try:
        # These endpoints only push events; we ignore client frames and simply
        # await the disconnect so the registry entry is cleaned up correctly.
        while True:
            message = await websocket.receive()
            if message["type"] == "websocket.disconnect":
                break
    except Exception:
        pass
    finally:
        await manager.disconnect(restaurant_id, branch_id, websocket)


@router.websocket("/ws/kitchen")
async def kitchen_ws(websocket: WebSocket) -> None:
    await _run_socket(websocket)


@router.websocket("/ws/notifications")
async def notifications_ws(websocket: WebSocket) -> None:
    await _run_socket(websocket)
