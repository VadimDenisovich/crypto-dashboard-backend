"""BacktestWorker — asyncio-таска в lifespan-handler'е, обрабатывает очередь job'ов.

Принимает job_id из `asyncio.Queue`, загружает запись из БД, готовит JSON-конфиг,
запускает движок subprocess'ом (`python -m backtest_main --config <path>`),
парсит результат из stdout и пишет обратно в БД.

Subprocess-изоляция:
- pandas/pyarrow живут в engine-образе, не тянут backend memory во время прогона
- можно kill subprocess по timeout
- stdout строго JSON — никаких print'ов из движка (логи валим в stderr)

Ограничения MVP:
- одна job-таска одновременно (один worker). При желании поднять параллельность —
  запустить несколько workers, читающих ту же очередь.
"""

from __future__ import annotations

import asyncio
import json
import shlex
import tempfile
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from src.config import Settings
from src.logging_setup import get_logger
from src.models.backtest_job import BacktestJob, BacktestStatus
from src.repositories.backtest_repo import BacktestJobRepository

log = get_logger(__name__)


def _slugify(value: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in value).lower()


def _resolve_parquet_path(historical_dir: Path, exchange: str, symbol: str, timeframe: str) -> Path | None:
    """Ищем parquet по имени: {exchange}_{base}_{quote}_{timeframe}*.parquet.

    Это первый соответствующий файл; точный диапазон дат не проверяем (для MVP
    предполагаем что admin/CI скачали единственный файл на (symbol, timeframe)).
    """
    historical_dir = Path(historical_dir)
    if not historical_dir.exists():
        return None
    base = _slugify(symbol)
    pattern = f"{exchange}_{base}_{timeframe}*.parquet"
    matches = sorted(historical_dir.glob(pattern))
    if matches:
        return matches[0]
    # Fallback: без exchange-префикса
    matches = sorted(historical_dir.glob(f"*{base}*{timeframe}*.parquet"))
    return matches[0] if matches else None


async def _run_subprocess(
    cmd: str,
    config_path: Path,
    timeout_sec: int,
) -> tuple[int, str, str]:
    parts = shlex.split(cmd) + ["--config", str(config_path)]
    proc = await asyncio.create_subprocess_exec(
        *parts,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout_b, stderr_b = await asyncio.wait_for(
            proc.communicate(), timeout=timeout_sec
        )
    except asyncio.TimeoutError:
        proc.kill()
        await proc.communicate()
        raise
    return (proc.returncode or 0, stdout_b.decode("utf-8", errors="replace"), stderr_b.decode("utf-8", errors="replace"))


def _build_config_payload(job: BacktestJob) -> dict[str, Any]:
    return {
        "strategy": job.strategy_class,
        "symbol": job.symbol,
        "timeframe": job.timeframe,
        "params": dict(job.params),
        "initial_balance": dict(job.initial_balance),
        # date_from/date_to пока не передаём в engine — он гонит весь файл целиком.
        # В Phase 5 добавим фильтрацию диапазона на стороне CSVMarketDataProvider.
    }


async def _process_job(
    job_id: uuid.UUID,
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
) -> None:
    async with session_factory() as session:
        repo = BacktestJobRepository(session)
        job = await repo.get(job_id)
        if job is None:
            log.warning("backtest.job_missing", job_id=str(job_id))
            return
        await repo.update_status(job, BacktestStatus.RUNNING)
        await session.commit()

        # Найти parquet файл. exchange пока всегда binance (берём первый matching).
        parquet = _resolve_parquet_path(
            Path(settings.backend_historical_dir),
            exchange="binance",
            symbol=job.symbol,
            timeframe=job.timeframe,
        )
        if parquet is None:
            await repo.mark_failed(
                job,
                f"Нет исторических данных для {job.symbol} {job.timeframe}. "
                f"Выполните scripts/fetch_historical.py.",
            )
            await session.commit()
            return

        config = _build_config_payload(job)
        config["parquet_path"] = str(parquet)
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".json", delete=False, encoding="utf-8"
            ) as tmp:
                json.dump(config, tmp)
                tmp_path = Path(tmp.name)

            try:
                code, stdout, stderr = await _run_subprocess(
                    settings.backend_backtest_cmd,
                    tmp_path,
                    settings.backend_backtest_timeout_sec,
                )
            finally:
                tmp_path.unlink(missing_ok=True)

            if code != 0:
                # backtest_main даже при ошибке пишет JSON с error в stdout
                err_blob: dict[str, Any] = {}
                try:
                    err_blob = json.loads(stdout) if stdout.strip() else {}
                except Exception:
                    pass
                msg = err_blob.get("error") or stderr[:500] or f"exit code {code}"
                await repo.mark_failed(job, str(msg))
                await session.commit()
                return

            try:
                result = json.loads(stdout)
            except json.JSONDecodeError as exc:
                await repo.mark_failed(
                    job, f"Невалидный JSON в stdout движка: {exc}"
                )
                await session.commit()
                return

            await repo.mark_completed(job, result)
            await session.commit()
            log.info(
                "backtest.completed",
                job_id=str(job_id),
                trades_count=result.get("trades_count"),
            )
        except asyncio.TimeoutError:
            await repo.mark_failed(
                job, f"Превышен таймаут {settings.backend_backtest_timeout_sec}s"
            )
            await session.commit()
        except Exception as exc:
            log.exception("backtest.process_error", job_id=str(job_id))
            await repo.mark_failed(job, f"Ошибка воркера: {exc}")
            await session.commit()


async def backtest_worker(
    queue: asyncio.Queue[uuid.UUID],
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
) -> None:
    log.info("backtest.worker.started")
    while True:
        job_id = await queue.get()
        try:
            await _process_job(job_id, session_factory, settings)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("backtest.worker.unhandled", job_id=str(job_id))
