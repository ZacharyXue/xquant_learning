"""回测中心 API"""

import asyncio
import traceback
from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.logging import get_logger
from backend.db.database import get_session, get_session_factory
from backend.db.repository import (
    get_backtest_runs, create_backtest_run, save_backtest_result,
)
from backend.db.models import BacktestRun
from backend.api.models import BacktestRequest, BacktestResultOut

logger = get_logger("api.backtest")
router = APIRouter()


def _run_backtest_sync(
    run_id: int, strategy_name: str, stock_code: str,
    start_date: str, end_date: str, params: dict,
):
    """在独立线程中同步执行回测并持久化结果"""
    from backend.backtest.engine import BacktestEngine

    # 确保策略已在 registry 中注册
    try:
        from src.strategies.bonus_stocks import BonusStocksStrategy  # noqa: F401
    except ImportError:
        pass

    engine = BacktestEngine()
    try:
        result = engine.run(
            strategy_name=strategy_name,
            stock_code=stock_code,
            start_date=start_date,
            end_date=end_date,
            params=params or {},
        )
    except Exception as e:
        result = {"error": str(e), "traceback": traceback.format_exc()}
        logger.error(f"Backtest [{run_id}] engine failed: {e}")

    # 持久化 (同步 asyncio.run)
    async def _persist():
        factory = get_session_factory()
        async with factory() as db:
            try:
                run = await db.get(BacktestRun, run_id)
                if run is None:
                    return
                if "error" in result:
                    run.status = "failed"
                    run.error_msg = result.get("error", "Unknown")
                    run.completed_at = datetime.now()
                else:
                    run.status = "completed"
                    run.completed_at = datetime.now()
                    await save_backtest_result(db, run_id=run_id, result=result)
                await db.commit()
            except Exception as e:
                logger.error(f"Failed to persist backtest [{run_id}]: {e}")
                try:
                    run = await db.get(BacktestRun, run_id)
                    if run:
                        run.status = "failed"
                        run.error_msg = str(e)[:500]
                        run.completed_at = datetime.now()
                        await db.commit()
                except Exception:
                    await db.rollback()

    try:
        asyncio.run(_persist())
    except RuntimeError:
        # 已有事件循环时创建新任务
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        loop.run_until_complete(_persist())


@router.post("/run")
async def run_backtest(body: BacktestRequest, db: AsyncSession = Depends(get_session)):
    run = await create_backtest_run(
        db,
        strategy_name=body.strategy_name,
        stock_code=body.stock_code,
        start_date=datetime.strptime(body.start_date, "%Y%m%d"),
        end_date=datetime.strptime(body.end_date, "%Y%m%d"),
        params=body.params or {},
        status="running",
    )
    await db.commit()
    run_id = run.id

    # 在线程池中执行回测 (不阻塞 API 响应)
    loop = asyncio.get_running_loop()
    loop.run_in_executor(
        None,
        _run_backtest_sync,
        run_id,
        body.strategy_name,
        body.stock_code,
        body.start_date,
        body.end_date,
        body.params,
    )

    logger.info(f"Backtest started: id={run_id} strategy={body.strategy_name} stock={body.stock_code}")
    return {
        "status": "accepted",
        "run_id": run_id,
        "strategy": body.strategy_name,
        "stock_code": body.stock_code,
    }


@router.get("/history")
async def get_history(limit: int = 20, db: AsyncSession = Depends(get_session)):
    runs = await get_backtest_runs(db, limit)
    return [{
        "id": r.id,
        "strategy_name": r.strategy_name,
        "stock_code": r.stock_code,
        "start_date": r.start_date.strftime("%Y%m%d") if r.start_date else "",
        "end_date": r.end_date.strftime("%Y%m%d") if r.end_date else "",
        "status": r.status,
        "started_at": r.started_at.isoformat() if r.started_at else "",
    } for r in runs]


@router.get("/result/{run_id}", response_model=BacktestResultOut)
async def get_result(run_id: int, db: AsyncSession = Depends(get_session)):
    from sqlalchemy import select
    from backend.db.models import BacktestResult, BacktestRun

    q = select(BacktestResult).where(BacktestResult.run_id == run_id)
    r = await db.execute(q)
    row = r.scalar_one_or_none()

    q2 = select(BacktestRun).where(BacktestRun.id == run_id)
    r2 = await db.execute(q2)
    run = r2.scalar_one_or_none()

    if row is None:
        return BacktestResultOut(
            run_id=run_id,
            total_trades=0,
            error_msg=run.error_msg if run else "Result not found",
        )

    return BacktestResultOut(
        run_id=run_id,
        total_trades=row.total_trades or 0,
        profitable_trades=row.profitable_trades or 0,
        win_rate=float(row.win_rate or 0),
        total_investment=float(row.total_investment or 0),
        final_value=float(row.final_value or 0),
        return_rate=float(row.return_rate or 0),
        annualized_return=float(row.annualized_return or 0),
        max_drawdown=float(row.max_drawdown or 0),
        sharpe_ratio=float(row.sharpe_ratio or 0),
        calmar_ratio=float(row.calmar_ratio or 0),
        equity_curve=row.equity_curve or [],
        buy_signals=row.buy_signals or [],
    )
