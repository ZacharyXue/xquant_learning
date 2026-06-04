"""Quote pump — bridges xtquant callbacks to Quote objects"""
import asyncio
from datetime import datetime
from typing import Callable
from engine.strategy_base import Quote

class QuotePump:
    def __init__(self):
        self._callbacks: list[Callable] = []; self._last_prices: dict[str, float] = {}; self._running = False
    def on_quote(self, callback: Callable[[Quote], None]): self._callbacks.append(callback)
    async def subscribe(self, stock_codes: list[str]):
        self._running = True
        import xtquant.xtdata as xtdata
        for code in stock_codes:
            xtdata.subscribe_quote(code, period='1d', start_time='', end_time='', count=1, callback=self._on_tick)
    def _on_tick(self, data: dict):
        code = data.get("stockCode", "")
        if not code: return
        lp = data.get("lastPrice", 0)
        if code in self._last_prices and self._last_prices[code] == lp: return
        self._last_prices[code] = lp
        quote = Quote(stock_code=code, last_price=lp, open=data.get("open", 0), high=data.get("high", 0),
                      low=data.get("low", 0), last_close=data.get("lastClose", 0),
                      volume=data.get("volume", 0), amount=data.get("amount", 0), time=datetime.now())
        for cb in self._callbacks:
            try: cb(quote)
            except: pass
    async def stop(self): self._running = False
