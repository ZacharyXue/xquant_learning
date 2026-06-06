"""Real trade executor — wraps xtquant XtQuantTrader (Windows only)

Connection sequence (per xtquant SDK):
  1. XtQuantTrader(path, session_id)
  2. trader.register_callback(callback)   <-- BEFORE start()
  3. trader.start()
  4. trader.connect() == 0  (success)
  5. trader.subscribe(account)
"""
import threading
from trade.fees import FeeCalculator


def _ensure_xtdata_runtime():
    """Start xtdata.run() in a daemon thread so subscribe_whole_quote callbacks fire."""
    try:
        import xtquant.xtdata as xtdata
    except ImportError:
        return
    if not getattr(_ensure_xtdata_runtime, "_started", False):
        _ensure_xtdata_runtime._started = True
        threading.Thread(target=xtdata.run, daemon=True).start()


class _TraderCallback:
    """Minimal callback bridge for order/trade/error notifications."""

    def __init__(self):
        self.orders: dict[int, object] = {}
        self.trades: list[object] = []
        self.errors: list[object] = []
        self.last_error: str = ""

    def on_disconnected(self):
        pass

    def on_stock_order(self, order):
        self.orders[order.order_id] = order

    def on_stock_trade(self, trade):
        self.trades.append(trade)

    def on_stock_asset(self, asset):
        pass

    def on_stock_position(self, position):
        pass

    def on_order_error(self, order_error):
        self.errors.append(order_error)
        self.last_error = getattr(order_error, "error_msg", str(order_error))

    def on_cancel_error(self, cancel_error):
        self.last_error = getattr(cancel_error, "error_msg", str(cancel_error))

    def on_order_stock_async_response(self, response):
        pass

    def on_cancel_order_stock_async_response(self, response):
        pass


class RealExecutor:
    def __init__(self, qmt_path: str, account_id: str):
        self._qmt_path = qmt_path
        self._account_id = account_id
        self._trader = None
        self._connected = False
        self._callback = _TraderCallback()
        self.fee_calc = FeeCalculator()

    async def initialize(self) -> bool:
        """Connect to QMT following xttrader.py SDK sequence (line 340, 343, 358, 379):
          1. register_callback()  2. start()  3. connect()  4. subscribe(account)
        """
        try:
            from xtquant.xttrader import XtQuantTrader
            from xtquant.xttype import StockAccount
        except ImportError:
            raise RuntimeError(
                "xtquant not available. Real trading requires QMT SDK on Windows."
            )

        # xttrader.py:109  — XtQuantTrader(path, session_id)
        self._trader = XtQuantTrader(self._qmt_path, 0)

        # xttrader.py:340 — register_callback BEFORE start()
        self._trader.register_callback(self._callback)

        # xttrader.py:343 — start()
        self._trader.start()

        # xttrader.py:358 — connect(), returns 0 on success
        result = self._trader.connect()
        self._connected = result == 0
        if not self._connected:
            return False

        # xttype.py:13 — StockAccount(account_id, account_type='STOCK'), defaults to STOCK
        acc = StockAccount(self._account_id)

        # xttrader.py:379 — subscribe(account)
        self._trader.subscribe(acc)

        # xtdata.py:772 — start xtdata.run() in daemon thread for quote callbacks
        _ensure_xtdata_runtime()

        return True

    async def place_order(self, stock_code, side, volume, price=0.0):
        if not self._connected:
            return {"executed": False, "reason": "not connected"}

        try:
            from xtquant.xttype import StockAccount
            from xtquant.xtconstant import STOCK_BUY, STOCK_SELL, FIX_PRICE
        except ImportError:
            return {"executed": False, "reason": "xtquant import failed"}

        acc = StockAccount(self._account_id)

        # xtconstant.py:77-78 — STOCK_BUY=23, STOCK_SELL=24
        order_type = STOCK_BUY if side == "buy" else STOCK_SELL

        slippage_price = self.fee_calc.calc_slippage_price(price, side) if price > 0 else 0

        # xtconstant.py:119 — FIX_PRICE=11 (limit), 5=LATEST_PRICE (market-ish)
        price_type = FIX_PRICE if slippage_price > 0 else 5

        # xttrader.py:429 — order_stock returns order_id (>0 success, -1 failure)
        order_id = self._trader.order_stock(
            account=acc,
            stock_code=stock_code,
            order_type=order_type,            # 23=buy, 24=sell
            order_volume=volume,
            price_type=price_type,            # 11=limit, 5=latest
            price=slippage_price if slippage_price > 0 else 0,
            strategy_name="xtquant_learning",
            order_remark="auto",
        )

        error_msg = self._callback.last_error if order_id <= 0 else None

        return {
            "executed": order_id > 0,
            "order_id": order_id,
            "stock_code": stock_code,
            "side": side,
            "volume": volume,
            "price": slippage_price if slippage_price > 0 else 0,
            "error": error_msg,
        }

    def get_account(self):
        if not self._connected:
            return {}
        from xtquant.xttype import StockAccount

        acc = StockAccount(self._account_id)
        asset = self._trader.query_stock_asset(acc)
        return {
            "total_asset": getattr(asset, "总资产", 0),
            "available_cash": getattr(asset, "可用资金", 0),
        }

    def get_positions(self):
        if not self._connected:
            return []
        from xtquant.xttype import StockAccount

        acc = StockAccount(self._account_id)
        positions = self._trader.query_stock_positions(acc)
        return [
            {"stock_code": p.stock_code, "volume": p.volume, "avg_cost": p.avg_price}
            for p in positions
            if p.volume > 0
        ]

    async def close(self):
        if self._trader:
            self._trader.stop()
            self._connected = False
