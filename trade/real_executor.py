"""Real trade executor — wraps xtquant XtQuantTrader (Windows only)"""
from trade.fees import FeeCalculator

class RealExecutor:
    def __init__(self, qmt_path: str, account_id: str):
        self._qmt_path = qmt_path; self._account_id = account_id
        self._trader = None; self._connected = False; self.fee_calc = FeeCalculator()
    async def initialize(self) -> bool:
        try:
            from xtquant.xttrader import XtQuantTrader
            from xtquant.xttype import StockAccount
        except ImportError:
            raise RuntimeError("xtquant not available. Real trading requires QMT SDK on Windows.")
        self._trader = XtQuantTrader(self._qmt_path, 0)
        acc = StockAccount(self._account_id); self._trader.start()
        self._connected = self._trader.connect() == 0
        if self._connected: self._trader.subscribe(acc)
        return self._connected
    async def place_order(self, stock_code, side, volume, price=0.0):
        if not self._connected: return {"executed": False, "reason": "not connected"}
        from xtquant.xttype import StockAccount
        acc = StockAccount(self._account_id)
        slippage_price = self.fee_calc.calc_slippage_price(price, side) if price > 0 else 0
        seq = self._trader.order_stock(account=acc, stock_code=stock_code, order_type=0,
                                       order_volume=volume, price=slippage_price if slippage_price > 0 else price,
                                       strategy_name="xtquant_learning", order_remark="auto")
        return {"executed": True, "order_seq": seq, "stock_code": stock_code, "side": side, "volume": volume, "price": slippage_price if slippage_price > 0 else 0}
    def get_account(self):
        if not self._connected: return {}
        from xtquant.xttype import StockAccount
        acc = StockAccount(self._account_id)
        asset = self._trader.query_stock_asset(acc)
        return {"total_asset": getattr(asset, '总资产', 0), "available_cash": getattr(asset, '可用资金', 0)}
    def get_positions(self):
        if not self._connected: return []
        from xtquant.xttype import StockAccount
        acc = StockAccount(self._account_id); positions = self._trader.query_stock_positions(acc)
        return [{"stock_code": p.stock_code, "volume": p.volume, "avg_cost": p.avg_price} for p in positions if p.volume > 0]
    async def close(self):
        if self._trader: self._trader.stop(); self._connected = False
