"""
行情泵 (QuotePump)

从 xtquant 订阅实时行情，跨线程桥接到 asyncio 事件循环，
限速去重后分发 Quote 对象到策略引擎。
"""

import asyncio
import threading
from datetime import datetime
from typing import Optional, Callable

import backend.core.xtquant_setup  # noqa: F401

from backend.core.logging import get_logger
from backend.engine.strategy_base import Quote

logger = get_logger("quote_pump")

try:
    from xtquant import xtdata
    _XTQUANT_AVAILABLE = True
except ImportError:
    xtdata = None
    _XTQUANT_AVAILABLE = False


class QuotePump:
    def __init__(
        self,
        stock_codes: list[str],
        on_quote: Callable[[Quote], None] = None,
        min_interval: float = 0.1,
    ):
        self._stock_codes = list(stock_codes)
        self._on_quote = on_quote
        self._min_interval = min_interval
        self._quote_queue: asyncio.Queue = asyncio.Queue(maxsize=1000)
        self._last_tick: dict[str, str] = {}
        self._running = False
        self._task: Optional[asyncio.Task] = None

    @property
    def stock_codes(self) -> list[str]:
        return self._stock_codes

    def subscribe(self, loop: asyncio.AbstractEventLoop) -> None:
        if not _XTQUANT_AVAILABLE:
            logger.warning("xtquant not available, QuotePump disabled")
            self._running = False
            return

        def _on_quote(data: dict) -> None:
            for code, tick in data.items():
                if not self._running:
                    return
                try:
                    asyncio.run_coroutine_threadsafe(
                        self._quote_queue.put((code, tick)), loop
                    )
                except Exception:
                    pass

        try:
            xtdata.subscribe_whole_quote(self._stock_codes, callback=_on_quote)
            logger.info(f"Subscribed to {len(self._stock_codes)} stock(s)")
        except Exception as e:
            logger.error(f"Failed to subscribe quotes: {e}")

    def unsubscribe(self) -> None:
        if _XTQUANT_AVAILABLE:
            try:
                xtdata.unsubscribe_whole_quote(self._stock_codes)
            except Exception:
                pass
        logger.info("Unsubscribed from quotes")

    async def run(self) -> None:
        self._running = True
        self._task = asyncio.current_task()

        if _XTQUANT_AVAILABLE:
            self.subscribe(asyncio.get_running_loop())

        logger.info("QuotePump started")
        while self._running:
            await self._pump_one()

        self.unsubscribe()
        logger.info("QuotePump stopped")

    async def _pump_one(self) -> None:
        try:
            code, tick = await asyncio.wait_for(
                self._quote_queue.get(), timeout=1.0
            )
        except asyncio.TimeoutError:
            return
        except Exception:
            return

        # 去重
        tick_time = tick.get("time", "")
        last = self._last_tick.get(code, "")
        if tick_time and tick_time == last:
            return
        self._last_tick[code] = tick_time

        quote = Quote(
            stock_code=code,
            last_price=float(tick.get("lastPrice", 0)),
            open=float(tick.get("open", 0)),
            high=float(tick.get("high", 0)),
            low=float(tick.get("low", 0)),
            last_close=float(tick.get("lastClose", 0)),
            volume=float(tick.get("volume", 0)),
            amount=float(tick.get("amount", 0)),
            time=tick_time,
        )

        if self._on_quote:
            try:
                self._on_quote(quote)
            except Exception as e:
                logger.error(f"on_quote handler error: {e}")

        if self._min_interval > 0:
            await asyncio.sleep(self._min_interval)

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
