"""回测中心 API"""

import asyncio
import traceback
import math
from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.logging import get_logger
from backend.db.database import get_session, get_session_factory
from backend.db.repository import (
    get_backtest_runs, create_backtest_run, save_backtest_result,
)
from backend.db.models import BacktestRun
from backend.api.models import BacktestRequest, BacktestResultOut, ParamOptimizeRequest, AdvancedOptimizeRequest

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
    try:
        start_dt = datetime.strptime(body.start_date, "%Y%m%d")
        end_dt = datetime.strptime(body.end_date, "%Y%m%d")
    except ValueError as e:
        return {"status": "error", "error": f"Invalid date format (use YYYYMMDD): {e}"}

    run = await create_backtest_run(
        db,
        strategy_name=body.strategy_name,
        stock_code=body.stock_code,
        start_date=start_dt,
        end_date=end_dt,
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
        "error_msg": r.error_msg,
        "started_at": r.started_at.isoformat() if r.started_at else "",
    } for r in runs]


def _run_optimize_sync(
    run_id: int, strategy_name: str, stock_code: str,
    start_date: str, end_date: str, param_grid: dict,
):
    """在独立线程中执行参数优化并持久化 Top 10 结果"""
    from backend.backtest.optimizer import GridOptimizer

    try:
        from src.strategies.bonus_stocks import BonusStocksStrategy  # noqa
    except ImportError:
        pass

    opt = GridOptimizer(strategy_name, stock_code, start_date, end_date)
    try:
        results = opt.optimize(param_grid)
    except Exception as e:
        results = None
        error = str(e)
        logger.error(f"Optimize [{run_id}] failed: {e}")

    async def _persist():
        factory = get_session_factory()
        async with factory() as db:
            try:
                run = await db.get(BacktestRun, run_id)
                if run is None:
                    return
                if results is None:
                    run.status = "failed"
                    run.error_msg = error
                    run.completed_at = datetime.now()
                    await db.commit()
                    return

                # 持久化 Top 10 (每个作为独立 backtest_result)
                top10 = results[:10]
                for r in top10:
                    await save_backtest_result(db, run_id=run_id, result=r)

                run.status = "completed"
                run.completed_at = datetime.now()
                # 存优化元信息到 params
                run.params = {
                    "type": "optimization",
                    "total_combos": len(results),
                    "metric": "sharpe_ratio",
                }
                await db.commit()
            except Exception as e:
                logger.error(f"Failed to persist optimize [{run_id}]: {e}")
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
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        loop.run_until_complete(_persist())


@router.post("/optimize")
async def run_optimize(body: ParamOptimizeRequest, db: AsyncSession = Depends(get_session)):
    param_names = list(body.param_grid.keys())
    param_values = list(body.param_grid.values())
    total_combos = math.prod(len(v) for v in param_values)

    try:
        start_dt = datetime.strptime(body.start_date, "%Y%m%d")
        end_dt = datetime.strptime(body.end_date, "%Y%m%d")
    except ValueError as e:
        return {"status": "error", "error": f"Invalid date format: {e}"}

    run = await create_backtest_run(
        db,
        strategy_name=body.strategy_name,
        stock_code=body.stock_code,
        start_date=start_dt,
        end_date=end_dt,
        params={"type": "optimization", "param_grid": body.param_grid},
        status="running",
    )
    await db.commit()
    run_id = run.id

    loop = asyncio.get_running_loop()
    loop.run_in_executor(
        None,
        _run_optimize_sync,
        run_id,
        body.strategy_name,
        body.stock_code,
        body.start_date,
        body.end_date,
        body.param_grid,
    )

    logger.info(f"Optimization started: id={run_id} strategy={body.strategy_name} combos={total_combos}")
    return {
        "status": "accepted",
        "run_id": run_id,
        "strategy": body.strategy_name,
        "total_combos": total_combos,
    }


def _dispatch_optimizer(body: AdvancedOptimizeRequest, tuning_space: list):
    """根据优化方法创建对应的优化器实例"""
    if body.method == "grid":
        from backend.backtest.optimizers.grid_optimizer import GridOptimizer
        return GridOptimizer(
            strategy_name=body.strategy_name,
            stock_code=body.stock_code,
            start_date=body.start_date,
            end_date=body.end_date,
            tuning_space=tuning_space,
            metric=body.metric,
            n_trials=body.n_trials,
            n_jobs=body.n_jobs,
        )
    elif body.method == "random":
        from backend.backtest.optimizers.random_optimizer import RandomOptimizer
        return RandomOptimizer(
            strategy_name=body.strategy_name,
            stock_code=body.stock_code,
            start_date=body.start_date,
            end_date=body.end_date,
            tuning_space=tuning_space,
            metric=body.metric,
            n_trials=body.n_trials,
            n_jobs=body.n_jobs,
        )
    else:  # default optuna
        from backend.backtest.optimizers.optuna_optimizer import OptunaOptimizer
        return OptunaOptimizer(
            strategy_name=body.strategy_name,
            stock_code=body.stock_code,
            start_date=body.start_date,
            end_date=body.end_date,
            tuning_space=tuning_space,
            metric=body.metric,
            n_trials=body.n_trials,
            n_jobs=body.n_jobs,
        )


def _run_advanced_optimize_sync(
    run_id: int, body: AdvancedOptimizeRequest,
):
    """在独立线程中执行高级优化并持久化结果"""
    from backend.engine.strategy_registry import get, create

    try:
        from src.strategies.bonus_stocks import BonusStocksStrategy  # noqa
    except ImportError:
        pass

    cls = get(body.strategy_name)
    if cls is None:
        error = f"Strategy '{body.strategy_name}' not found"
        logger.error(f"Advanced optimize [{run_id}]: {error}")
        _mark_run_failed(run_id, error)
        return

    instance = create(body.strategy_name, {})
    tuning_space = list(instance.get_tuning_space()) if hasattr(instance, 'get_tuning_space') else []

    if body.param_overrides:
        for p in tuning_space:
            if p.name in body.param_overrides:
                override = body.param_overrides[p.name]
                if isinstance(override, (int, float)):
                    p.low = min(override) if isinstance(override, list) else override
                    p.high = max(override) if isinstance(override, list) else override
                elif isinstance(override, list) and len(override) == 2:
                    p.low, p.high = override

    if body.validation == "walkforward":
        from backend.backtest.walkforward import WalkForwardValidator
        wf = WalkForwardValidator(
            start_date=body.start_date,
            end_date=body.end_date,
            train_years=body.walkforward_train_years,
            test_years=body.walkforward_test_years,
        )
        opt_cls = _get_optimizer_class(body.method)
        wf_result = wf.validate(
            strategy_name=body.strategy_name,
            stock_code=body.stock_code,
            optimizer_class=opt_cls,
            tuning_space=tuning_space,
            metric=body.metric,
            n_trials=body.n_trials,
            n_jobs=body.n_jobs,
        )
        _persist_advanced_result(run_id, wf_result)
        return

    optimizer = _dispatch_optimizer(body, tuning_space)
    try:
        results = optimizer.optimize()
    except Exception as e:
        logger.error(f"Advanced optimize [{run_id}] failed: {e}")
        _mark_run_failed(run_id, str(e))
        return

    top10 = results[:10]
    _persist_advanced_trials(run_id, top10, body.metric, len(results))


def _get_optimizer_class(method: str):
    if method == "grid":
        from backend.backtest.optimizers.grid_optimizer import GridOptimizer
        return GridOptimizer
    elif method == "random":
        from backend.backtest.optimizers.random_optimizer import RandomOptimizer
        return RandomOptimizer
    else:
        from backend.backtest.optimizers.optuna_optimizer import OptunaOptimizer
        return OptunaOptimizer


def _mark_run_failed(run_id: int, error: str):
    async def _mark():
        from backend.db.database import get_session_factory
        from backend.db.models import BacktestRun
        from datetime import datetime
        factory = get_session_factory()
        async with factory() as db:
            run = await db.get(BacktestRun, run_id)
            if run:
                run.status = "failed"
                run.error_msg = str(error)[:500]
                run.completed_at = datetime.now()
                await db.commit()
    try:
        asyncio.run(_mark())
    except RuntimeError:
        loop = asyncio.new_event_loop()
        loop.run_until_complete(_mark())
        loop.close()


def _persist_advanced_trials(run_id: int, results: list, metric: str, total_combos: int):
    async def _persist():
        from backend.db.database import get_session_factory
        from backend.db.models import BacktestRun
        from backend.db.repository import save_backtest_result
        from datetime import datetime
        factory = get_session_factory()
        async with factory() as db:
            run = await db.get(BacktestRun, run_id)
            if run is None:
                return
            for r in results:
                save_data = {**r.metrics, "total_trades": r.metrics.get("total_trades", 0)}
                await save_backtest_result(db, run_id=run_id, result=save_data)
            run.status = "completed"
            run.completed_at = datetime.now()
            run.params = {
                "type": "optimization_advanced",
                "method": "advanced",
                "total_trials": total_combos,
                "metric": metric,
            }
            await db.commit()
    try:
        asyncio.run(_persist())
    except RuntimeError:
        loop = asyncio.new_event_loop()
        loop.run_until_complete(_persist())
        loop.close()


def _persist_advanced_result(run_id: int, wf_result: dict):
    async def _persist():
        from backend.db.database import get_session_factory
        from backend.db.models import BacktestRun
        from datetime import datetime
        factory = get_session_factory()
        async with factory() as db:
            run = await db.get(BacktestRun, run_id)
            if run is None:
                return
            run.status = "completed"
            run.completed_at = datetime.now()
            run.params = {
                "type": "walkforward",
                "summary": wf_result.get("summary", {}),
            }
            await db.commit()
    try:
        asyncio.run(_persist())
    except RuntimeError:
        loop = asyncio.new_event_loop()
        loop.run_until_complete(_persist())
        loop.close()


@router.post("/optimize/advanced")
async def advanced_optimize(body: AdvancedOptimizeRequest, db: AsyncSession = Depends(get_session)):
    try:
        start_dt = datetime.strptime(body.start_date, "%Y%m%d")
        end_dt = datetime.strptime(body.end_date, "%Y%m%d")
    except ValueError as e:
        return {"status": "error", "error": f"Invalid date format (use YYYYMMDD): {e}"}

    run = await create_backtest_run(
        db,
        strategy_name=body.strategy_name,
        stock_code=body.stock_code,
        start_date=start_dt,
        end_date=end_dt,
        params={"method": body.method, "metric": body.metric, "validation": body.validation},
        status="running",
    )
    await db.commit()
    run_id = run.id

    loop = asyncio.get_running_loop()
    loop.run_in_executor(None, _run_advanced_optimize_sync, run_id, body)

    logger.info(
        f"Advanced optimize started: id={run_id} strategy={body.strategy_name} "
        f"method={body.method} validation={body.validation}"
    )
    return {
        "status": "accepted",
        "run_id": run_id,
        "strategy": body.strategy_name,
        "method": body.method,
        "validation": body.validation,
    }


@router.get("/optimize/{run_id}")
async def get_optimize_results(run_id: int, db: AsyncSession = Depends(get_session)):
    """获取参数优化结果 (Top 10 按 sharpe 排序)"""
    from sqlalchemy import select
    from backend.db.models import BacktestResult

    q = select(BacktestResult).where(BacktestResult.run_id == run_id).order_by(
        BacktestResult.sharpe_ratio.desc()
    ).limit(10)
    r = await db.execute(q)
    rows = r.scalars().all()

    return [{
        "run_id": row.run_id,
        "total_trades": row.total_trades or 0,
        "return_rate": float(row.return_rate or 0),
        "annualized_return": float(row.annualized_return or 0),
        "max_drawdown": float(row.max_drawdown or 0),
        "sharpe_ratio": float(row.sharpe_ratio or 0),
        "calmar_ratio": float(row.calmar_ratio or 0),
        "total_investment": float(row.total_investment or 0),
        "final_value": float(row.final_value or 0),
        "xirr": float(row.xirr or 0),
        "return_on_deployed": float(row.return_on_deployed or 0),
    } for row in rows]


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
        total_return=float(row.total_return or 0),
        return_rate=float(row.return_rate or 0),
        annualized_return=float(row.annualized_return or 0),
        max_drawdown=float(row.max_drawdown or 0),
        volatility=float(row.volatility or 0),
        sharpe_ratio=float(row.sharpe_ratio or 0),
        calmar_ratio=float(row.calmar_ratio or 0),
        xirr=float(row.xirr or 0),
        return_on_deployed=float(row.return_on_deployed or 0),
        equity_curve=row.equity_curve or [],
        buy_signals=row.buy_signals or [],
        trades=row.trades_json or [],
        drawdown_curve=row.drawdown_curve or [],
        monthly_returns=row.monthly_returns or [],
        baseline=row.baseline or {},
    )


@router.post("/cache/cleanup")
async def cleanup_cache(max_age_hours: int = 168):
    """清理过期的文件缓存"""
    from backend.backtest.data_provider import _file_cache
    _file_cache.cleanup(max_age_hours=max_age_hours)
    return {"status": "ok", "remaining_files": _file_cache.file_count}


@router.get("/cache/status")
async def cache_status():
    """获取文件缓存状态"""
    from backend.backtest.data_provider import _file_cache
    return {
        "cache_dir": str(_file_cache._dir),
        "file_count": _file_cache.file_count,
        "ttl_hours": _file_cache._ttl / 3600,
    }
