"""
信号总线

策略产出的交易信号通过此总线汇集，进行合并/冲突解决后下发到交易执行器。
"""

import asyncio
from typing import Optional

from backend.core.logging import get_logger
from backend.engine.strategy_base import Signal

logger = get_logger("signal_bus")


class SignalBus:
    """信号总线"""

    def __init__(self):
        self._queue: asyncio.Queue = asyncio.Queue()
        self._handlers: list[callable] = []

    def add_handler(self, handler):
        """注册信号处理器 (异步回调)"""
        self._handlers.append(handler)

    async def publish(self, signal: Signal) -> None:
        """发布信号"""
        logger.info(f"Signal: {signal.stock_code} {signal.side} x{signal.volume} ({signal.reason})")
        await self._queue.put(signal)

    async def consume(self):
        """消费信号: 从队列取信号，分发到所有处理器"""
        while True:
            signal = await self._queue.get()
            for handler in self._handlers:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        await handler(signal)
                    else:
                        handler(signal)
                except Exception as e:
                    logger.error(f"Signal handler error: {e}")
            self._queue.task_done()


class SignalMerger:
    """信号合并器: 相同股票的买卖方向合并/抵消"""

    @staticmethod
    def merge(signals: list[Signal]) -> list[Signal]:
        """合并多个策略的信号

        规则:
        - 同股票同方向: 成交量相加 (取最高价买/最低价卖)
        - 同股票反方向: 先抵消，剩余量按净方向执行
        """
        if not signals:
            return []

        # 按股票分组
        by_stock: dict[str, list[Signal]] = {}
        for s in signals:
            by_stock.setdefault(s.stock_code, []).append(s)

        merged = []
        for code, sigs in by_stock.items():
            buy_vol = sum(s.volume for s in sigs if s.side == "buy")
            sell_vol = sum(s.volume for s in sigs if s.side == "sell")
            net_vol = buy_vol - sell_vol

            if net_vol == 0:
                continue

            side = "buy" if net_vol > 0 else "sell"
            best_price = 0.0  # 市价
            reasons = " | ".join(s.reason for s in sigs if s.reason)
            indicators = {}
            for s in sigs:
                indicators.update(s.indicators)

            merged.append(Signal(
                stock_code=code,
                side=side,
                volume=abs(net_vol),
                price=best_price,
                reason=reasons,
                indicators=indicators,
            ))

        return merged
