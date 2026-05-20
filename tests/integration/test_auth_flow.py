from __future__ import annotations

import pytest


class TestAuthFlow:
    """Интеграционные тесты auth API: email-код → JWT → защищённые эндпоинты."""

    async def test_healthz_returns_ok(self, client):
        response = await client.get("/healthz")
        assert response.status_code == 200
        data = response.json()
        assert data["backend"] == "ok"

    async def test_me_without_token_returns_401(self, client):
        response = await client.get("/api/auth/me")
        assert response.status_code in (401, 403)

    async def test_me_with_valid_token_returns_user(
        self, client, access_token, test_user
    ):
        response = await client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == test_user.email
        assert data["id"] == str(test_user.id)
        assert data["role"] == test_user.role.value

    async def test_email_code_request_with_captcha_disabled(self, client):
        response = await client.post(
            "/api/auth/email/request",
            json={
                "email": "new-user@example.com",
                "captcha_token": "test-captcha",
            },
        )
        assert response.status_code in (200, 429)

        if response.status_code == 200:
            assert response.json()["status"] == "sent"

    async def test_exchanges_supported_returns_catalog(self, client, access_token):
        response = await client.get(
            "/api/exchanges/supported",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        exchanges = {e["name"] for e in data}
        assert "binance" in exchanges

    async def test_refresh_token_flow(self, client, access_token, test_user):
        from src.config import get_settings
        from src.infrastructure.security import encode_refresh_token

        settings = get_settings()
        refresh_token = encode_refresh_token(
            user_id=test_user.id,
            secret=settings.backend_jwt_secret,
            algorithm=settings.backend_jwt_algorithm,
            ttl_days=settings.backend_refresh_token_ttl_days,
        )

        response = await client.post(
            "/api/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "Bearer"

    async def test_bots_endpoint_with_valid_auth(
        self, client, access_token, test_bot
    ):
        response = await client.get(
            "/api/bots",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        bot_ids = [b["id"] for b in data]
        assert str(test_bot.id) in bot_ids
