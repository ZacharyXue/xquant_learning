"""Pydantic 请求/响应模型"""

from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel, Field


# === Trade ===

class OrderRequest(BaseModel):
    stock_code: str
    volume: int
    side: str  # buy / sell
    price: float = 0.0
    strategy_name: str = ""
    order_remark: str = ""


class OrderResponse(BaseModel):
    success: bool
    order_id: str = ""
    error: str = ""
    estimated_fee: float = 0.0
    slippage_price: float = 0.0


# === Strategy ===

class StrategyInfo(BaseModel):
    name: str
    display_name: str
    description: str = ""
    enabled: bool = False
    config: dict = {}


class StrategyToggle(BaseModel):
    name: str
    enabled: bool


# === Trade History ===

class TradeRecordOut(BaseModel):
    id: int
    strategy_name: Optional[str]
    stock_code: str
    side: str
    volume: int
    order_price: Optional[float]
    filled_price: Optional[float]
    status: str
    commission: float
    stamp_tax: float
    transfer_fee: float
    slippage: float
    amount: Optional[float]
    trade_mode: str
    trade_time: datetime
    created_at: datetime


class PaginatedTrades(BaseModel):
    items: list[TradeRecordOut]
    total: int
    page: int
    page_size: int


# === Dashboard ===

class DashboardData(BaseModel):
    total_asset: float = 0.0
    available_cash: float = 0.0
    market_value: float = 0.0
    total_profit_loss: float = 0.0
    positions: list[dict] = []
    recent_trades: list[dict] = []
    active_strategies: list[str] = []


# === Backtest ===

class BacktestRequest(BaseModel):
    strategy_name: str
    stock_code: str
    start_date: str  # YYYYMMDD
    end_date: str
    params: dict = {}


class BacktestResultOut(BaseModel):
    run_id: int
    total_trades: int = 0
    profitable_trades: int = 0
    win_rate: float = 0.0
    total_investment: float = 0.0
    final_value: float = 0.0
    return_rate: float = 0.0
    annualized_return: float = 0.0
    max_drawdown: float = 0.0
    sharpe_ratio: float = 0.0
    calmar_ratio: float = 0.0
    equity_curve: list = []
    buy_signals: list = []
    error_msg: str = ""
    benchmark: dict = {}


class ParamOptimizeRequest(BaseModel):
    strategy_name: str
    stock_code: str
    start_date: str
    end_date: str
    param_grid: dict


# === Settings ===

class FeeSettingsUpdate(BaseModel):
    commission_rate: Optional[float] = None
    stamp_tax_rate: Optional[float] = None
    transfer_fee_rate: Optional[float] = None
    min_commission: Optional[float] = None


class SlippageSettingsUpdate(BaseModel):
    rate: Optional[float] = None
    mode: Optional[str] = None
