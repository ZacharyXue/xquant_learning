"""
订单追踪器 (OrderTracker)

监听 xtquant 订单回调，桥接到 asyncio 事件循环。
提供超时兜底：N秒无回调则主动查询订单状态。
"""

import asyncio
import time
from datetime import datetime
from typing import Optional, Any

import backend.core.xtquant_setup  # noqa: F401

from backend.core.logging import get_logger

logger = get_logger("order_tracker")

try:
    from xtquant.xttrader import XtQuantTraderCallback
    _XTQUANT_AVAILABLE = True
except ImportError:
    XtQuantTraderCallback = object
    _XTQUANT_AVAILABLE = False


_ORDER_STATUS_MAP = {
    48: "pending",
    49: "pending",
    50: "reported",
    51: "cancelling",
    52: "partial",
    53: "filled",
    54: "rejected",
    55: "partial_cancelled",
    56: "cancelled",
    57: "rejected",
}


def order_status_name(status_code: int) -> str:
    return _ORDER_STATUS_MAP.get(status_code, "unknown")


class OrderRecord:
    __slots__ = (
        "order_id", "stock_code", "side", "volume", "price",
        "strategy_name", "status", "filled_volume", "filled_price",
        "created_at", "last_update",
    )

    def __init__(self, order_id: str, stock_code: str, side: str,
                 volume: int, price: float, strategy_name: str = ""):
        self.order_id = order_id
        self.stock_code = stock_code
        self.side = side
        self.volume = volume
        self.price = price
        self.strategy_name = strategy_name
        self.status = "pending"
        self.filled_volume = 0
        self.filled_price = 0.0
        self.created_at = time.time()
        self.last_update = time.time()


class OrderTracker:
    def __init__(self, timeout: float = 5.0, poll_interval: float = 5.0):
        self._pending: dict[str, OrderRecord] = {}
        self._timeout = timeout
        self._poll_interval = poll_interval
        self._executor = None
        self._on_update: Optional[Any] = None
        self._on_trade: Optional[Any] = None
        self._running = False
        self._task: Optional[asyncio.Task] = None

    def set_executor(self, executor) -> None:
        self._executor = executor

    def set_on_update(self, callback) -> None:
        self._on_update = callback

    def set_on_trade(self, callback) -> None:
        self._on_trade = callback

    def register(self, seq: str, order: OrderRecord) -> None:
        self._pending[seq] = order
        logger.info(f"Order registered: seq={seq}, {order.stock_code} {order.side} x{order.volume}")

    def get_pending(self) -> list[OrderRecord]:
        return list(self._pending.values())

    def on_stock_order(self, order) -> None:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        asyncio.run_coroutine_threadsafe(
            self._handle_order_update(order), loop
        )

    def on_stock_trade(self, trade) -> None:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        asyncio.run_coroutine_threadsafe(
            self._handle_trade_update(trade), loop
        )

    async def _handle_order_update(self, order) -> None:
        status = order_status_name(order.order_status)
        oid = str(order.order_id)

        record = self._pending.get(oid)
        if record:
            record.status = status
            record.filled_volume = getattr(order, "traded_volume", 0)
            record.filled_price = getattr(order, "traded_price", 0.0)
            record.last_update = time.time()

            if status in ("filled", "cancelled", "rejected"):
                self._pending.pop(oid, None)
                logger.info(f"Order completed: id={oid}, status={status}")

        if self._on_update:
            try:
                await self._on_update(order, status)
            except Exception as e:
                logger.error(f"on_update callback error: {e}")

    async def _handle_trade_update(self, trade) -> None:
        logger.info(
            f"Trade: {trade.stock_code} x{trade.traded_volume}"
            f" @ {trade.traded_price}"
        )
        if self._on_trade:
            try:
                await self._on_trade(trade)
            except Exception as e:
                logger.error(f"on_trade callback error: {e}")

    async def run(self) -> None:
        self._running = True
        self._task = asyncio.current_task()
        logger.info("OrderTracker started")
        while self._running:
            try:
                await asyncio.sleep(self._poll_interval)
                await self._check_timeouts()
            except asyncio.CancelledError:
                break

    async def _check_timeouts(self) -> None:
        if not self._pending or not self._executor:
            return

        now = time.time()
        timed_out = []
        for seq, record in self._pending.items():
            if now - record.last_update > self._timeout:
                timed_out.append(seq)

        if not timed_out:
            return

        try:
            from backend.grpc import trade_pb2
            response = await self._executor.get_orders(trade_pb2.OrdersRequest())
            if not response.success:
                return

            for order in response.orders:
                oid = order.order_id
                if oid in timed_out:
                    record = self._pending.get(oid)
                    if record:
                        record.status = order.status
                        record.filled_volume = order.traded_volume
                        record.filled_price = order.traded_price
                        record.last_update = now
                        if order.status in ("filled", "cancelled", "rejected"):
                            self._pending.pop(oid, None)
                        logger.info(f"Timeout recovery: id={oid}, status={order.status}")
        except Exception as e:
            logger.error(f"Timeout check failed: {e}")

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("OrderTracker stopped")


class TraderCallbackBridge(XtQuantTraderCallback):
    def __init__(self, tracker: OrderTracker):
        super().__init__()
        self._tracker = tracker

    def on_stock_order(self, order):
        self._tracker.on_stock_order(order)

    def on_stock_trade(self, trade):
        self._tracker.on_stock_trade(trade)

    def on_order_error(self, order_error):
        logger.error(f"Order error: {order_error.error_msg}")

    def on_cancel_error(self, cancel_error):
        logger.error(f"Cancel error: {cancel_error}")

    def on_disconnected(self):
        logger.warning("QMT connection disconnected")

    def on_account_status(self, status):
        logger.info(f"Account status: {status}")
