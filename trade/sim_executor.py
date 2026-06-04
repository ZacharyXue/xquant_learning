"""Simulated trade executor with virtual account"""
from trade.fees import FeeCalculator

class SimAccount:
    def __init__(self, cash=100000.0):
        self.cash = cash; self.positions: dict[str, dict] = {}
    def get_position(self, code): return self.positions.get(code, {"volume": 0, "avg_cost": 0.0})
    def can_buy(self, price, volume, fee_calc):
        cost = fee_calc.calc_trade_cost(price, volume, "buy"); return self.cash >= price * volume + cost.total
    def can_sell(self, code, volume): return self.get_position(code)["volume"] >= volume
    def execute_buy(self, code, price, volume, fee_calc):
        cost = fee_calc.calc_trade_cost(price, volume, "buy"); total = price * volume + cost.total
        self.cash -= total
        pos = self.positions.setdefault(code, {"volume": 0, "avg_cost": 0.0})
        old = pos["avg_cost"] * pos["volume"]; pos["volume"] += volume
        pos["avg_cost"] = (old + price * volume) / pos["volume"]
        return {"executed": True, "side": "buy", "price": price, "volume": volume,
                "commission": cost.commission, "stamp_tax": cost.stamp_tax,
                "transfer_fee": cost.transfer_fee, "slippage": cost.slippage_cost,
                "total_cost": cost.total, "cash_after": round(self.cash, 4)}
    def execute_sell(self, code, price, volume, fee_calc):
        pos = self.positions.get(code, {"volume": 0, "avg_cost": 0.0}); vol = min(volume, pos["volume"])
        if vol <= 0: return {"executed": False, "reason": "no position"}
        cost = fee_calc.calc_trade_cost(price, vol, "sell"); self.cash += price * vol - cost.total
        pos["volume"] -= vol; 
        if pos["volume"] <= 0: self.positions.pop(code, None)
        return {"executed": True, "side": "sell", "price": price, "volume": vol,
                "commission": cost.commission, "stamp_tax": cost.stamp_tax,
                "transfer_fee": cost.transfer_fee, "slippage": cost.slippage_cost,
                "total_cost": cost.total, "cash_after": round(self.cash, 4)}

class SimExecutor:
    def __init__(self, initial_capital=100000.0):
        self.account = SimAccount(cash=initial_capital); self.fee_calc = FeeCalculator()
    async def place_order(self, stock_code, side, volume, price):
        if side == "buy":
            if not self.account.can_buy(price, volume, self.fee_calc): return {"executed": False, "reason": "insufficient cash"}
            return self.account.execute_buy(stock_code, price, volume, self.fee_calc)
        elif side == "sell":
            if not self.account.can_sell(stock_code, volume): return {"executed": False, "reason": "insufficient position"}
            return self.account.execute_sell(stock_code, price, volume, self.fee_calc)
        return {"executed": False, "reason": f"unknown side: {side}"}
    def get_account(self): return {"mode": "sim", "available_cash": self.account.cash}
    def get_positions(self):
        return [{"stock_code": c, "volume": p["volume"], "avg_cost": p["avg_cost"]}
                for c, p in self.account.positions.items() if p["volume"] > 0]
