"""Quote pump — bridges xtquant callbacks to Quote objects

xtquant callback data formats (verified against SDK source):
  subscribe_whole_quote:  {stock_code1: {lastPrice, open, ...}, stock_code2: {...}}
  subscribe_quote:        {stock_code: [{time, lastPrice, ...}, ...]}

xtdata.run() runs in a daemon thread (started by real_executor.py on init).
"""

from datetime import datetime
from typing import Callable

from engine.strategy_base import Quote


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
        import xtquant.xtdata as xtdata

        # xtdata.py:747 — returns int subscription seq, callback gets {stock_code: data_dict}
        self._sub_seq = xtdata.subscribe_whole_quote(list(stock_codes), callback=self._on_tick)

    def _on_tick(self, datas: dict):
        """Callback for subscribe_whole_quote.

        xtdata.py:747-760 — datas format: {stock_code1: quote_dict1, stock_code2: ...}
        Each quote_dict has keys: lastPrice, open, high, low, lastClose, volume, amount, etc.
        """
        for code, data in datas.items():
            lp = data.get("lastPrice", 0)
            if code in self._last_prices and self._last_prices[code] == lp:
                continue
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

                # xtdata.py:763 — unsubscribe by seq number
                xtdata.unsubscribe_quote(self._sub_seq)
            except Exception:
                pass
