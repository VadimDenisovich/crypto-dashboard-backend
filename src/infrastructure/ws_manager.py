from __future__ import annotations

import asyncio
import uuid
from collections import defaultdict
from typing import Any

from fastapi import WebSocket

from src.logging_setup import get_logger

log = get_logger(__name__)


class ConnectionManager:
    def __init__(self, *, max_queue: int = 100, send_timeout: float = 2.0) -> None:
        self._connections: dict[uuid.UUID, set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()
        self._max_queue = max_queue
        self._send_timeout = send_timeout

    async def connect(self, user_id: uuid.UUID, ws: WebSocket) -> None:
        async with self._lock:
            self._connections[user_id].add(ws)

    async def disconnect(self, user_id: uuid.UUID, ws: WebSocket) -> None:
        async with self._lock:
            self._connections[user_id].discard(ws)
            if not self._connections[user_id]:
                self._connections.pop(user_id, None)

    async def broadcast_to_user(self, user_id: uuid.UUID, message: dict[str, Any]) -> None:
        async with self._lock:
            sockets = list(self._connections.get(user_id, ()))
        if not sockets:
            return
        await asyncio.gather(
            *(self._send_one(ws, user_id, message) for ws in sockets),
            return_exceptions=True,
        )

    async def _send_one(self, ws: WebSocket, user_id: uuid.UUID, message: dict[str, Any]) -> None:
        try:
            await asyncio.wait_for(ws.send_json(message), timeout=self._send_timeout)
        except (asyncio.TimeoutError, Exception) as exc:
            log.warning("ws.send_failed", user_id=str(user_id), error=str(exc))
            await self.disconnect(user_id, ws)
            try:
                await ws.close(code=1013)
            except Exception:
                pass

    async def close_all(self) -> None:
        async with self._lock:
            sockets = [ws for s in self._connections.values() for ws in s]
            self._connections.clear()
        for ws in sockets:
            try:
                await ws.close(code=1001)
            except Exception:
                pass
