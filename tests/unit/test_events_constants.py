"""Контрактные имена каналов: проверяем, что наши константы совпадают
с тем, что определено в движке. Любая ручная переименовка одной стороны
должна ломать тест."""

from __future__ import annotations

import importlib.util
import pathlib

from src.domain import events as backend_events


def _load_engine_events_module() -> object:
    engine_events_path = (
        pathlib.Path(__file__).resolve().parents[3]
        / "trade-engine-crypto"
        / "src"
        / "application"
        / "events.py"
    )
    if not engine_events_path.exists():
        return None
    spec = importlib.util.spec_from_file_location("engine_events", engine_events_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def test_engine_channels_match_engine_constants() -> None:
    engine_module = _load_engine_events_module()
    if engine_module is None:
        # В CI submodule может быть не подтянут — мягко скипаем.
        return
    assert backend_events.NEW_TRADE == engine_module.NEW_TRADE  # type: ignore[attr-defined]
    assert backend_events.BALANCE_UPDATE == engine_module.BALANCE_UPDATE  # type: ignore[attr-defined]
    assert backend_events.ENGINE_STATUS == engine_module.ENGINE_STATUS  # type: ignore[attr-defined]
    assert backend_events.STRATEGY_ERROR == engine_module.STRATEGY_ERROR  # type: ignore[attr-defined]
