"""
SQLAlchemy ORM 模型

所有数据表定义。
"""

from datetime import datetime

from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, Text, JSON,
    ForeignKey, Numeric
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class Strategy(Base):
    """策略定义"""
    __tablename__ = "strategies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), unique=True, nullable=False)
    display_name = Column(String(200), nullable=False)
    description = Column(Text)
    enabled = Column(Boolean, default=False)
    config = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class StrategySignal(Base):
    """策略信号日志"""
    __tablename__ = "strategy_signals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    strategy_name = Column(String(100), nullable=False)
    stock_code = Column(String(20), nullable=False)
    signal_type = Column(String(20), nullable=False)
    price = Column(Numeric(12, 4))
    volume = Column(Integer)
    reason = Column(Text)
    indicators = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.now)


class TradeRecord(Base):
    """交易记录"""
    __tablename__ = "trade_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    strategy_name = Column(String(100))
    stock_code = Column(String(20), nullable=False)
    stock_name = Column(String(100))
    side = Column(String(10), nullable=False)
    volume = Column(Integer, nullable=False)
    order_price = Column(Numeric(12, 4))
    filled_price = Column(Numeric(12, 4))
    order_id = Column(String(100))
    status = Column(String(20), default="pending")
    commission = Column(Numeric(12, 4), default=0)
    stamp_tax = Column(Numeric(12, 4), default=0)
    transfer_fee = Column(Numeric(12, 4), default=0)
    slippage = Column(Numeric(12, 4), default=0)
    amount = Column(Numeric(16, 4))
    trade_mode = Column(String(10), default="real")
    error_msg = Column(Text)
    order_remark = Column(Text)
    extra = Column(JSON, default=dict)
    trade_time = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.now)


class Position(Base):
    """持仓快照"""
    __tablename__ = "positions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    stock_code = Column(String(20), nullable=False)
    stock_name = Column(String(100))
    volume = Column(Integer, nullable=False)
    avg_cost = Column(Numeric(12, 4))
    current_price = Column(Numeric(12, 4))
    market_value = Column(Numeric(16, 4))
    profit_loss = Column(Numeric(16, 4))
    profit_loss_ratio = Column(Numeric(10, 6))
    trade_mode = Column(String(10), default="real")
    snapshot_time = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.now)


class AccountSnapshot(Base):
    """账户资金快照"""
    __tablename__ = "account_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    total_asset = Column(Numeric(16, 4))
    available_cash = Column(Numeric(16, 4))
    frozen_cash = Column(Numeric(16, 4))
    market_value = Column(Numeric(16, 4))
    total_profit_loss = Column(Numeric(16, 4))
    trade_mode = Column(String(10), default="real")
    snapshot_time = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.now)


class BacktestRun(Base):
    """回测运行记录"""
    __tablename__ = "backtest_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    strategy_name = Column(String(100), nullable=False)
    stock_code = Column(String(20), nullable=False)
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)
    params = Column(JSON, default=dict)
    status = Column(String(20), default="running")
    error_msg = Column(Text)
    started_at = Column(DateTime, default=datetime.now)
    completed_at = Column(DateTime)

    results = relationship("BacktestResult", backref="run", uselist=False)


class BacktestResult(Base):
    """回测绩效"""
    __tablename__ = "backtest_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(Integer, ForeignKey("backtest_runs.id", ondelete="CASCADE"))
    total_trades = Column(Integer, default=0)
    profitable_trades = Column(Integer, default=0)
    win_rate = Column(Numeric(10, 4))
    total_investment = Column(Numeric(16, 4))
    final_value = Column(Numeric(16, 4))
    total_return = Column(Numeric(16, 4))
    return_rate = Column(Numeric(10, 6))
    annualized_return = Column(Numeric(10, 6))
    max_drawdown = Column(Numeric(10, 6))
    volatility = Column(Numeric(10, 6))
    sharpe_ratio = Column(Numeric(10, 4))
    calmar_ratio = Column(Numeric(10, 4))
    xirr = Column(Numeric(10, 6))
    return_on_deployed = Column(Numeric(10, 6))
    equity_curve = Column(JSON, default=list)
    buy_signals = Column(JSON, default=list)
    drawdown_curve = Column(JSON, default=list)
    monthly_returns = Column(JSON, default=list)
    trades_json = Column(JSON, default=list)
    baseline = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.now)


class SystemConfig(Base):
    """系统配置 (KV)"""
    __tablename__ = "system_configs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    config_key = Column(String(200), unique=True, nullable=False)
    config_value = Column(JSON, nullable=False)
    description = Column(String(500))
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    created_at = Column(DateTime, default=datetime.now)
