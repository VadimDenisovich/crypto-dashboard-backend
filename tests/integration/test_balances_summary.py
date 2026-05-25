from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from src.models.balance_snapshot import BalanceSnapshot
from src.models.exchange_credential import ExchangeCredential
from src.repositories.balance_repo import BalanceRepository
from src.services import balance_valuation


async def test_balances_summary_values_all_connected_exchange_balances(
    client,
    session,
    test_user,
    test_credential,
    access_token,
    monkeypatch,
) -> None:
    second_credential = ExchangeCredential(
        user_id=test_user.id,
        exchange="bybit",
        label="bybit-key",
        api_key_enc="encrypted-key",
        api_secret_enc="encrypted-secret",
    )
    session.add(second_credential)
    await session.flush()

    session.add_all(
        [
            BalanceSnapshot(
                credential_id=test_credential.id,
                currency="USDT",
                free=Decimal("100"),
                used=Decimal("10"),
                total=Decimal("110"),
            ),
            BalanceSnapshot(
                credential_id=test_credential.id,
                currency="BTC",
                free=Decimal("0.01"),
                used=Decimal("0.002"),
                total=Decimal("0.012"),
            ),
            BalanceSnapshot(
                credential_id=second_credential.id,
                currency="ETH",
                free=Decimal("2"),
                used=Decimal("1"),
                total=Decimal("3"),
            ),
        ]
    )
    await session.commit()
    await session.begin()

    price_calls: list[tuple[str, str]] = []

    async def fake_fetch_ticker_last(exchange: str, symbol: str) -> Decimal | None:
        price_calls.append((exchange, symbol))
        prices = {
            "BTC/USDT": Decimal("50000"),
            "ETH/USDT": Decimal("3000"),
        }
        return prices[symbol]

    monkeypatch.setattr(
        balance_valuation, "_fetch_ticker_last", fake_fetch_ticker_last
    )

    response = await client.get(
        "/api/balances/summary",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert Decimal(data["free_total"]) == Decimal("6600")
    assert Decimal(data["used_total"]) == Decimal("3110")
    assert Decimal(data["total_equity"]) == Decimal("9710")
    assert len(data["currencies"]) == 3
    assert ("binance", "USDT/USDT") not in price_calls
    assert ("binance", "BTC/USDT") in price_calls
    assert ("bybit", "ETH/USDT") in price_calls


async def test_latest_for_credential_returns_latest_snapshot_per_currency(
    session,
    test_credential,
) -> None:
    now = datetime.now(timezone.utc)
    session.add_all(
        [
            BalanceSnapshot(
                credential_id=test_credential.id,
                currency="USDT",
                free=Decimal("10"),
                used=Decimal("0"),
                total=Decimal("10"),
                observed_at=now - timedelta(minutes=5),
            ),
            BalanceSnapshot(
                credential_id=test_credential.id,
                currency="USDT",
                free=Decimal("25"),
                used=Decimal("5"),
                total=Decimal("30"),
                observed_at=now,
            ),
            BalanceSnapshot(
                credential_id=test_credential.id,
                currency="BTC",
                free=Decimal("0.01"),
                used=Decimal("0"),
                total=Decimal("0.01"),
                observed_at=now - timedelta(minutes=1),
            ),
        ]
    )
    await session.flush()

    rows = await BalanceRepository(session).latest_for_credential(test_credential.id)
    by_currency = {row.currency: row for row in rows}

    assert set(by_currency) == {"BTC", "USDT"}
    assert by_currency["USDT"].free == Decimal("25")
    assert by_currency["BTC"].free == Decimal("0.01")
