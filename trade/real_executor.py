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
        """Connect to QMT following the correct SDK sequence."""
        try:
            from xtquant.xttrader import XtQuantTrader
            from xtquant.xttype import StockAccount
            from xtquant.xtconstant import ACCOUNT_TYPE_STOCK
        except ImportError:
            raise RuntimeError(
                "xtquant not available. Real trading requires QMT SDK on Windows."
            )

        # Step 1: Create trader
        self._trader = XtQuantTrader(self._qmt_path, 0)

        # Step 2: Register callback BEFORE start()
        self._trader.register_callback(self._callback)

        # Step 3: Start
        self._trader.start()

        # Step 4: Connect
        result = self._trader.connect()
        self._connected = result == 0
        if not self._connected:
            return False

        # Step 5: Subscribe to account
        acc = StockAccount(self._account_id, ACCOUNT_TYPE_STOCK)
        self._trader.subscribe(acc)

        # Ensure xtdata.run() is active for quote callbacks
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

        # Map side string to xtconstant order type
        order_type = STOCK_BUY if side == "buy" else STOCK_SELL

        # Calculate slippage-adjusted price
        slippage_price = self.fee_calc.calc_slippage_price(price, side) if price > 0 else 0

        # Use FIX_PRICE (limit order, type=11) if price specified, otherwise market price (type=5)
        price_type = FIX_PRICE if slippage_price > 0 else 5  # 5 = latest price

        seq = self._trader.order_stock(
            account=acc,
            stock_code=stock_code,
            order_type=order_type,
            order_volume=volume,
            price_type=price_type,
            price=slippage_price if slippage_price > 0 else 0,
            strategy_name="xtquant_learning",
            order_remark="auto",
        )

        error_msg = self._callback.last_error

        return {
            "executed": seq > 0,
            "order_seq": seq,
            "stock_code": stock_code,
            "side": side,
            "volume": volume,
            "price": slippage_price if slippage_price > 0 else 0,
            "error": error_msg if seq <= 0 else None,
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
