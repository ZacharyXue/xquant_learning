"""
交易执行器抽象基类

定义统一的交易接口，RealTradeExecutor 和 SimTradeExecutor 均实现此接口。
策略引擎仅依赖此抽象，不感知底层是真实交易还是模拟交易。
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import AsyncIterator, Optional, Any


class TradeExecutor(ABC):
    """交易执行器统一接口"""

    def __init__(self, config: dict = None):
        self._config = config or {}
        self._initialized = False

    @property
    def initialized(self) -> bool:
        return self._initialized

    @abstractmethod
    async def initialize(self) -> bool:
        """初始化交易环境 (连接QMT或初始化虚拟账户)"""

    @abstractmethod
    async def place_order(self, request: Any) -> Any:
        """下单"""

    @abstractmethod
    async def cancel_order(self, request: Any) -> Any:
        """撤单"""

    @abstractmethod
    async def get_account(self, request: Any) -> Any:
        """查询账户"""

    @abstractmethod
    async def get_positions(self, request: Any) -> Any:
        """查询持仓"""

    @abstractmethod
    async def get_orders(self, request: Any) -> Any:
        """查询委托"""

    @abstractmethod
    async def get_trades(self, request: Any) -> Any:
        """查询成交"""

    @abstractmethod
    async def subscribe_quotes(
        self, stock_codes: list[str]) -> AsyncIterator[Any]:
        """订阅实时行情 (streaming)"""

    @abstractmethod
    async def get_history_kline(self, request: Any) -> Any:
        """获取历史K线"""

    @abstractmethod
    async def get_stock_list(self, request: Any) -> Any:
        """获取股票列表"""

    @abstractmethod
    async def close(self) -> None:
        """关闭交易环境"""
