from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, status

from src.api.deps import DbSession
from src.api.schemas.cabinet import TestConnectionOut
from src.repositories.api_key_repo import UserApiKeyRepository
from src.services.api_key_service import ApiKeyService

router = APIRouter(prefix="/api/external", tags=["external"])


_TEST_MESSAGE = "This is a test API connection implementation"


def _strip_bearer(auth: str | None) -> str | None:
    if not auth:
        return None
    parts = auth.split(None, 1)
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1].strip()
    return auth.strip()


@router.post("/test", response_model=TestConnectionOut)
async def test_connection(
    db: DbSession,
    authorization: Annotated[str | None, Header()] = None,
    x_client_id: Annotated[str | None, Header(alias="X-Client-Id")] = None,
) -> TestConnectionOut:
    """Внешняя ручка для проверки клиентских API-ключей.

    Принимает `Authorization: Bearer cd_xxx…` + `X-Client-Id: <uuid>`. Если оба
    переданы и ключ принадлежит указанному клиенту — отдаёт фиксированную
    английскую строку. Это заглушка для будущей интеграции бэка с внешними
    клиентами; формат ответа уже зафиксирован.
    """
    secret = _strip_bearer(authorization)
    if not secret or not x_client_id:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "missing Authorization or X-Client-Id header",
        )
    try:
        client_uuid = uuid.UUID(x_client_id)
    except ValueError as exc:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "invalid X-Client-Id"
        ) from exc

    service = ApiKeyService(UserApiKeyRepository(db))
    item = await service.verify(secret)
    if item is None or item.user_id != client_uuid:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid api key")

    return TestConnectionOut(message=_TEST_MESSAGE)
