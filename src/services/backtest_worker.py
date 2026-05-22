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


def _resolve_parquet_path(historical_dir: Path, exchange: str, symbol: str, timeframe: str) -> Path:
    """Возвращает путь к parquet-кэшу для (exchange, symbol, timeframe).

    Если уже есть подходящий файл `{exchange}_{slug}_{timeframe}*.parquet` — берём
    первый. Иначе возвращаем канонический путь `{exchange}_{slug}_{timeframe}.parquet`
    (файла может ещё не быть — движок скачает данные с биржи и запишет кэш сюда).
    """
    historical_dir = Path(historical_dir)
    base = _slugify(symbol)
    canonical = historical_dir / f"{exchange}_{base}_{timeframe}.parquet"
    if historical_dir.exists():
        matches = sorted(historical_dir.glob(f"{exchange}_{base}_{timeframe}*.parquet"))
        if matches:
            return matches[0]
    return canonical


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


def _build_config_payload(job: BacktestJob, settings: Settings) -> dict[str, Any]:
    params = dict(job.params)
    # MlRsi strategy needs absolute path to model checkpoints inside the container.
    if job.strategy_class == "MlRsi" and "model_dir" not in params:
        params["model_dir"] = settings.backend_ml_model_dir
    return {
        "exchange": job.exchange,
        "strategy": job.strategy_class,
        "symbol": job.symbol,
        "timeframe": job.timeframe,
        "params": params,
        "initial_balance": dict(job.initial_balance),
        # Диапазон дат передаём в мс — движок фильтрует свечи и/или докачивает
        # недостающие данные с реальной биржи (гибрид parquet + CCXT).
        "date_from_ms": int(job.date_from.timestamp() * 1000),
        "date_to_ms": int(job.date_to.timestamp() * 1000),
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

        # Путь к parquet-кэшу для биржи job'а. Файла может не быть — движок сам
        # скачает данные с реальной биржи (CCXT) и запишет кэш сюда.
        parquet = _resolve_parquet_path(
            Path(settings.backend_historical_dir),
            exchange=job.exchange,
            symbol=job.symbol,
            timeframe=job.timeframe,
        )

        config = _build_config_payload(job, settings)
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
