"""Trade broker — Signal -> execute -> persist"""
from datetime import datetime
from engine.strategy_base import Signal
from db.queries import insert_trade

class Broker:
    def __init__(self, executor, mode="sim"):
        self._executor = executor; self._mode = mode
    async def handle_signal(self, signal: Signal, strategy_name: str) -> dict:
        if signal.side not in ("buy", "sell"): return {"executed": False, "reason": f"invalid side: {signal.side}"}
        result = await self._executor.place_order(stock_code=signal.stock_code, side=signal.side, volume=signal.volume, price=signal.price)
        if result.get("executed"):
            insert_trade(strategy=strategy_name, mode=self._mode, stock_code=signal.stock_code, side=signal.side,
                        volume=result.get("volume", signal.volume), price=result.get("price", signal.price),
                        commission=result.get("commission", 0), stamp_tax=result.get("stamp_tax", 0),
                        transfer_fee=result.get("transfer_fee", 0), slippage=result.get("slippage", 0),
                        total_cost=result.get("total_cost", 0), reason=signal.reason, indicators=signal.indicators,
                        trade_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        return result
