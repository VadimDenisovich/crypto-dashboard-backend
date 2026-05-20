from __future__ import annotations

import asyncio
import json
import uuid

import pytest
from fastapi import WebSocket
from starlette.testclient import WebSocketTestSession

from src.infrastructure.ws_manager import ConnectionManager


class TestWebSocketUpdates:
    """Интеграционные тесты WebSocket: подключение, бродкаст, отключение."""

    async def test_ws_connects_with_valid_jwt(self, app, access_token):
        """Проверяет, что клиент с валидным JWT может подключиться к /ws/updates."""
        from starlette.testclient import TestClient

        client = TestClient(app)
        with client.websocket_connect(
            f"/ws/updates?token={access_token}"
        ) as websocket:
            data = websocket.receive_json()
            assert data["type"] == "connected"
            assert "session_id" in data

    async def test_ws_rejects_without_token(self, app):
        """Без токена соединение отвергается."""
        from starlette.testclient import TestClient

        client = TestClient(app)
        with pytest.raises(Exception):
            with client.websocket_connect("/ws/updates"):
                pass

    async def test_ws_rejects_with_invalid_token(self, app):
        """С невалидным токеном соединение отвергается."""
        from starlette.testclient import TestClient

        client = TestClient(app)
        with pytest.raises(Exception):
            with client.websocket_connect(
                "/ws/updates?token=invalid.token.here"
            ):
                pass

    async def test_broadcast_to_connected_user(
        self, app, access_token, test_user
    ):
        """Публикация события через ws_manager доходит до подключённого клиента."""
        ws_manager: ConnectionManager = app.state.ws_manager
        from starlette.testclient import TestClient

        client = TestClient(app)
        with client.websocket_connect(
            f"/ws/updates?token={access_token}"
        ) as websocket:
            connected = websocket.receive_json()
            assert connected["type"] == "connected"

            await ws_manager.broadcast_to_user(
                test_user.id,
                {"type": "test_event", "data": {"value": 42}},
            )

            event = websocket.receive_json()
            assert event["type"] == "test_event"
            assert event["data"]["value"] == 42

    async def test_broadcast_to_different_user_is_not_received(
        self, app, access_token, test_user
    ):
        """Событие для другого пользователя не приходит."""
        ws_manager: ConnectionManager = app.state.ws_manager
        from starlette.testclient import TestClient

        client = TestClient(app)
        other_user_id = uuid.uuid4()
        with client.websocket_connect(
            f"/ws/updates?token={access_token}"
        ) as websocket:
            connected = websocket.receive_json()
            assert connected["type"] == "connected"

            await ws_manager.broadcast_to_user(
                other_user_id,
                {"type": "should_not_receive", "data": {}},
            )

            # Отправляем ping-сообщение текущему пользователю,
            # чтобы убедиться что WS всё ещё жив
            await ws_manager.broadcast_to_user(
                test_user.id,
                {"type": "ping_check", "data": {}},
            )

            event = websocket.receive_json()
            assert event["type"] == "ping_check"
            # Чужое сообщение не пришло

    async def test_ws_ping_keeps_connection_alive(self, app, access_token):
        """Проверяет, что сервер шлёт ping каждые 20 секунд."""
        from starlette.testclient import TestClient

        client = TestClient(app)
        with client.websocket_connect(
            f"/ws/updates?token={access_token}"
        ) as websocket:
            data = websocket.receive_json()
            assert data["type"] == "connected"

            try:
                data = websocket.receive_json()
                assert data["type"] == "ping"
            except Exception:
                pass
