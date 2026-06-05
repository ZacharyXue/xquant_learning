"""Quote pump — bridges xtquant callbacks to Quote objects

Relies on RealExecutor._ensure_xtdata_runtime() to start xtdata.run()
in a daemon thread, which is required for subscribe_whole_quote callbacks.
"""
import asyncio
import threading
from datetime import datetime
from typing import Callable

from engine.strategy_base import Quote


def ensure_xtdata_runtime():
    """Start xtdata.run() in a daemon thread so callbacks fire.
    Idempotent — only starts once per process.
    """
    if getattr(ensure_xtdata_runtime, "_started", False):
        return
    ensure_xtdata_runtime._started = True
    try:
        import xtquant.xtdata as xtdata

        threading.Thread(target=xtdata.run, daemon=True).start()
    except ImportError:
        pass


class QuotePump:
    def __init__(self):
        self._callbacks: list[Callable] = []
        self._last_prices: dict[str, float] = {}
        self._running = False
        self._sub_seq: int = 0

    def on_quote(self, callback: Callable[[Quote], None]):
        self._callbacks.append(callback)

    async def subscribe(self, stock_codes: list[str]):
        self._running = True

        # Ensure xtdata.run() event loop is active (required for callbacks)
        ensure_xtdata_runtime()

        import xtquant.xtdata as xtdata

        # subscribe_whole_quote returns a sequence number for later unsubscribe
        # Callback fires on C++ thread — we handle synchronously (no asyncio queue)
        self._sub_seq = xtdata.subscribe_whole_quote(
            list(stock_codes), callback=self._on_tick
        )

    def _on_tick(self, data: dict):
        code = data.get("stockCode", "")
        if not code:
            return
        lp = data.get("lastPrice", 0)
        # Dedup: skip if price unchanged from last tick
        if code in self._last_prices and self._last_prices[code] == lp:
            return
        self._last_prices[code] = lp

        quote = Quote(
            stock_code=code,
            last_price=lp,
            open=data.get("open", 0),
            high=data.get("high", 0),
            low=data.get("low", 0),
            last_close=data.get("lastClose", 0),
            volume=data.get("volume", 0),
            amount=data.get("amount", 0),
            time=datetime.now(),
        )
        for cb in self._callbacks:
            try:
                cb(quote)
            except Exception:
                pass

    async def stop(self):
        self._running = False
        if self._sub_seq:
            try:
                import xtquant.xtdata as xtdata

                xtdata.unsubscribe_quote(self._sub_seq)
            except Exception:
                pass
