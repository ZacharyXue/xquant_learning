"""
回测模块

提供历史数据获取和回测功能
"""

from .history_data import (
    get_historical_kline,
    get_stock_info,
    calculate_date_range,
    generate_date_range,
)
from .backtest_engine import (
    BacktestEngine,
    BacktestResult,
    run_backtest,
    main,
)

__all__ = [
    "get_historical_kline",
    "get_stock_info",
    "calculate_date_range",
    "generate_date_range",
    "BacktestEngine",
    "BacktestResult",
    "run_backtest",
    "main",
]