"""
数据访问层 (DAO)

提供各表的 CRUD 操作。
"""

from datetime import datetime
from typing import Optional, Any

from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import (
    Strategy, StrategySignal, TradeRecord, Position,
    AccountSnapshot, BacktestRun, BacktestResult, SystemConfig,
)


# === Trade Records ===

async def insert_trade(db: AsyncSession, **kwargs) -> TradeRecord:
    record = TradeRecord(**kwargs)
    db.add(record)
    await db.flush()
    return record


async def query_trades(
    db: AsyncSession,
    strategy_name: str = None,
    stock_code: str = None,
    side: str = None,
    status: str = None,
    trade_mode: str = None,
    start_time: datetime = None,
    end_time: datetime = None,
    limit: int = 100,
    offset: int = 0,
) -> list[TradeRecord]:
    q = select(TradeRecord)
    if strategy_name:
        q = q.where(TradeRecord.strategy_name == strategy_name)
    if stock_code:
        q = q.where(TradeRecord.stock_code == stock_code)
    if side:
        q = q.where(TradeRecord.side == side)
    if status:
        q = q.where(TradeRecord.status == status)
    if trade_mode:
        q = q.where(TradeRecord.trade_mode == trade_mode)
    if start_time:
        q = q.where(TradeRecord.trade_time >= start_time)
    if end_time:
        q = q.where(TradeRecord.trade_time <= end_time)
    q = q.order_by(desc(TradeRecord.trade_time)).offset(offset).limit(limit)
    result = await db.execute(q)
    return result.scalars().all()


async def count_trades(db: AsyncSession, **filters) -> int:
    q = select(func.count(TradeRecord.id))
    if "strategy_name" in filters:
        q = q.where(TradeRecord.strategy_name == filters["strategy_name"])
    if "trade_mode" in filters:
        q = q.where(TradeRecord.trade_mode == filters["trade_mode"])
    result = await db.execute(q)
    return result.scalar() or 0


# === Positions ===

async def save_positions(db: AsyncSession, positions: list[dict]) -> None:
    snapshot_time = datetime.now()
    for p in positions:
        pos = Position(**p, snapshot_time=snapshot_time)
        db.add(pos)
    await db.flush()


async def get_latest_positions(db: AsyncSession, trade_mode: str = "real") -> list[Position]:
    subq = (
        select(
            Position.stock_code,
            func.max(Position.snapshot_time).label("max_time")
        )
        .where(Position.trade_mode == trade_mode)
        .group_by(Position.stock_code)
        .subquery()
    )
    q = (
        select(Position)
        .join(subq, (Position.stock_code == subq.c.stock_code) & (Position.snapshot_time == subq.c.max_time))
    )
    result = await db.execute(q)
    return result.scalars().all()


# === Account ===

async def save_account_snapshot(db: AsyncSession, **kwargs) -> AccountSnapshot:
    snap = AccountSnapshot(**kwargs, snapshot_time=datetime.now())
    db.add(snap)
    await db.flush()
    return snap


async def get_latest_account(db: AsyncSession, trade_mode: str = "real") -> Optional[AccountSnapshot]:
    q = (
        select(AccountSnapshot)
        .where(AccountSnapshot.trade_mode == trade_mode)
        .order_by(desc(AccountSnapshot.snapshot_time))
        .limit(1)
    )
    result = await db.execute(q)
    return result.scalar_one_or_none()


# === Strategy ===

async def get_strategies(db: AsyncSession) -> list[Strategy]:
    result = await db.execute(select(Strategy).order_by(Strategy.name))
    return result.scalars().all()


async def upsert_strategy(db: AsyncSession, name: str, **kwargs) -> Strategy:
    q = select(Strategy).where(Strategy.name == name)
    result = await db.execute(q)
    row = result.scalar_one_or_none()
    if row:
        for k, v in kwargs.items():
            setattr(row, k, v)
        row.updated_at = datetime.now()
    else:
        row = Strategy(name=name, **kwargs)
        db.add(row)
    await db.flush()
    return row


async def toggle_strategy_enabled(db: AsyncSession, name: str, enabled: bool) -> Optional[Strategy]:
    q = select(Strategy).where(Strategy.name == name)
    result = await db.execute(q)
    row = result.scalar_one_or_none()
    if row:
        row.enabled = enabled
        row.updated_at = datetime.now()
        await db.flush()
    return row


async def save_signal(db: AsyncSession, **kwargs) -> StrategySignal:
    signal = StrategySignal(**kwargs)
    db.add(signal)
    await db.flush()
    return signal


# === Backtest ===

async def create_backtest_run(db: AsyncSession, **kwargs) -> BacktestRun:
    run = BacktestRun(**kwargs)
    db.add(run)
    await db.flush()
    return run


async def save_backtest_result(db: AsyncSession, run_id: int, result: dict) -> BacktestResult:
    mapped = dict(result)
    if "trades" in mapped and "trades_json" not in mapped:
        mapped["trades_json"] = mapped.pop("trades")
    res = BacktestResult(run_id=run_id, **mapped)
    db.add(res)
    await db.flush()
    return res


async def get_backtest_runs(db: AsyncSession, limit: int = 20) -> list[BacktestRun]:
    q = select(BacktestRun).order_by(desc(BacktestRun.started_at)).limit(limit)
    result = await db.execute(q)
    return result.scalars().all()


# === System Config ===

async def get_system_config(db: AsyncSession, key: str) -> Optional[dict]:
    q = select(SystemConfig).where(SystemConfig.config_key == key)
    result = await db.execute(q)
    row = result.scalar_one_or_none()
    return row.config_value if row else None


async def set_system_config(db: AsyncSession, key: str, value: Any, description: str = "") -> None:
    q = select(SystemConfig).where(SystemConfig.config_key == key)
    result = await db.execute(q)
    row = result.scalar_one_or_none()
    if row:
        row.config_value = value
        row.description = description
    else:
        db.add(SystemConfig(config_key=key, config_value=value, description=description))
    await db.flush()
