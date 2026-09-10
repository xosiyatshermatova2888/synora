"""In-memory WebSocket connection manager (Phase K).

Connections are keyed by tenant `(restaurant_id, branch_id)`, so `broadcast`
fan-out can never cross restaurant boundaries — a WebSocket-specific instance of
the same tenant-isolation rule the REST layer enforces (Section 5A / backend
master prompt Section 3).

This registry is intentionally a single-instance in-memory dict. A multi-instance
deployment would replace it with a pub/sub broker (e.g. Redis) using the exact
same tenant keys — build that only when the deployment actually grows.
"""

import asyncio
import json
import uuid

from starlette.websockets import WebSocket

# (restaurant_id, branch_id | None) -> set of live connections.
# branch_id None = "all branches" subscriber (sees every event for the restaurant).
_Key = tuple[uuid.UUID, uuid.UUID | None]


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: dict[_Key, set[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, restaurant_id: uuid.UUID, branch_id: uuid.UUID | None, websocket: WebSocket) -> None:
        async with self._lock:
            self._connections.setdefault((restaurant_id, branch_id), set()).add(websocket)

    async def disconnect(self, restaurant_id: uuid.UUID, branch_id: uuid.UUID | None, websocket: WebSocket) -> None:
        async with self._lock:
            key = (restaurant_id, branch_id)
            conns = self._connections.get(key)
            if conns is None:
                return
            conns.discard(websocket)
            if not conns:
                self._connections.pop(key, None)

    def _targets(self, restaurant_id: uuid.UUID, branch_id: uuid.UUID | None) -> list[_Key]:
        # "all branches" subscribers see every event too; branch subscribers only
        # their own branch. restaurant_id is always included -> no cross-tenant leak.
        keys = [(restaurant_id, branch_id)]
        if branch_id is not None:
            keys.append((restaurant_id, None))
        return keys

    async def broadcast(self, restaurant_id: uuid.UUID, branch_id: uuid.UUID | None, message: dict) -> None:
        """Send a JSON message to every matching connection; drop dead sockets."""
        payload = json.dumps(message, default=str)
        async with self._lock:
            dead: list[tuple[WebSocket, _Key]] = []
            for key in self._targets(restaurant_id, branch_id):
                for ws in list(self._connections.get(key, ())):
                    try:
                        await ws.send_text(payload)
                    except Exception:
                        dead.append((ws, key))
            for ws, key in dead:
                conns = self._connections.get(key)
                if conns is not None:
                    conns.discard(ws)
                    if not conns:
                        self._connections.pop(key, None)


manager = ConnectionManager()