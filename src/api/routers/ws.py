from __future__ import annotations

import asyncio
import uuid

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, status

from src.config import get_settings
from src.infrastructure import security
from src.infrastructure.ws_manager import ConnectionManager
from src.logging_setup import get_logger

router = APIRouter(tags=["ws"])
log = get_logger(__name__)


@router.websocket("/ws/updates")
async def ws_updates(ws: WebSocket, token: str = Query(...)) -> None:
    settings = get_settings()
    try:
        payload = security.decode_token(
            token, settings.backend_jwt_secret, settings.backend_jwt_algorithm
        )
    except ValueError:
        await ws.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    if payload.get("type") != "access":
        await ws.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    user_id = uuid.UUID(payload["sub"])
    manager: ConnectionManager = ws.app.state.ws_manager
    await ws.accept()
    await manager.connect(user_id, ws)
    await ws.send_json({"type": "connected"})
    log.info("ws.connected", user_id=str(user_id))

    async def _ping_loop() -> None:
        while True:
            await asyncio.sleep(20)
            try:
                await ws.send_json({"type": "ping"})
            except Exception:
                return

    pinger = asyncio.create_task(_ping_loop())
    try:
        while True:
            # Клиент может отправлять keepalive/pong; payload не используется.
            await ws.receive_text()
    except WebSocketDisconnect:
        log.info("ws.disconnect", user_id=str(user_id))
    finally:
        pinger.cancel()
        await manager.disconnect(user_id, ws)
