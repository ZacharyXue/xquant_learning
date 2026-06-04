"""Backtest engine — event-driven daily loop"""

import json
import uuid
from datetime import datetime
from typing import Optional

import numpy as np
import pandas as pd

from engine.strategy_base import Quote, Signal, StrategyBase
from engine.strategy_registry import create as create_strategy
from engine.indicators import round_to_lot
from backtest.data_provider import DataProvider
from backtest.metrics import MetricsCalculator
from trade.fees import FeeCalculator
from db.queries import insert_trade, insert_backtest_run


def _weekday_from_name(day_name: str) -> int:
    """Convert weekday name to 0-6 (Mon=0). Supports Chinese, English full/short."""
    mapping = {
        "monday": 0, "mon": 0, "周一": 0,
        "tuesday": 1, "tue": 1, "周二": 1,
        "wednesday": 2, "wed": 2, "周三": 2,
        "thursday": 3, "thu": 3, "周四": 3,
        "friday": 4, "fri": 4, "周五": 4,
        "saturday": 5, "sat": 5, "周六": 5,
        "sunday": 6, "sun": 6, "周日": 6,
    }
    return mapping.get(day_name.lower().strip(), -1)


class BacktestEngine:
    def __init__(self):
        self._data = DataProvider()
        self._fee = FeeCalculator()
        self._metrics = MetricsCalculator()

    def run(
        self,
        strategy_name: str,
        stock_code: str,
        start_date: str,
        end_date: str,
        params: dict = None,
        initial_capital: float = 100000.0,
        save_to_db: bool = True,
    ) -> dict:
        """Run backtest and return results dict."""
        df = self._data.get_kline(stock_code, start_date, end_date)
        if df is None or len(df) == 0:
            return {"error": f"No data for {stock_code}"}

        strategy = create_strategy(strategy_name, params or {})

        cash = initial_capital
        position = 0
        avg_cost = 0.0
        trades = []
        equity_curve = []

        n_rows = len(df)
        for i in range(n_rows):
            row = df.iloc[i]
            date_str = str(row["time"])
            close = float(row["close"])
            open_price = float(row.get("open", close))
            high = float(row.get("high", close))
            low = float(row.get("low", close))
            volume_val = int(row.get("volume", 0))
            last_close = float(df["close"].iloc[i - 1]) if i > 0 else close

            if close <= 0 or np.isnan(close):
                equity = cash + position * last_close
                equity_curve.append({"date": date_str, "value": round(equity, 2)})
                continue

            try:
                dt = datetime.strptime(date_str.strip()[:8], "%Y%m%d")
            except ValueError:
                continue

            quote = Quote(
                stock_code=stock_code, last_price=close,
                open=open_price, high=high, low=low,
                last_close=last_close,
                volume=volume_val, amount=close * volume_val,
                time=dt,
            )

            self._feed_daily_close(strategy, stock_code, close, date_str)

            signal = strategy.on_quote(quote)

            equity = cash + position * close
            equity_curve.append({"date": date_str, "value": round(equity, 2)})

            if signal is None or signal.side == "skip" or signal.volume <= 0:
                continue

            if signal.side == "buy":
                vol = round_to_lot(signal.volume, 100)
                if vol <= 0:
                    continue

                price = close
                cost = self._fee.calc_trade_cost(price, vol, "buy")
                needed = price * vol + cost.total
                if cash < needed:
                    continue

                cash -= needed
                old_total = avg_cost * position
                position += vol
                avg_cost = (old_total + price * vol) / position if position > 0 else 0

                trade = {
                    "date": date_str, "side": "buy",
                    "price": price, "volume": vol,
                    "amount": price * vol,
                    "commission": cost.commission,
                    "stamp_tax": cost.stamp_tax,
                    "transfer_fee": cost.transfer_fee,
                    "slippage": cost.slippage_cost,
                    "total_fee": cost.total,
                    "cash_after": round(cash, 4),
                    "position_after": position,
                }
                trades.append(trade)

                if save_to_db:
                    try:
                        insert_trade(
                            strategy=strategy_name, mode="backtest",
                            stock_code=stock_code, side="buy",
                            volume=vol, price=price,
                            commission=cost.commission, stamp_tax=cost.stamp_tax,
                            transfer_fee=cost.transfer_fee, slippage=cost.slippage_cost,
                            total_cost=cost.total,
                            reason=signal.reason, indicators=signal.indicators,
                            trade_time=f"{date_str} 10:30:00",
                        )
                    except Exception:
                        pass

            elif signal.side == "sell" and position > 0:
                vol = min(signal.volume, position)
                vol = round_to_lot(vol, 100)
                if vol <= 0:
                    continue

                price = close
                cost = self._fee.calc_trade_cost(price, vol, "sell")
                income = price * vol - cost.total
                cash += income
                position -= vol
                if position <= 0:
                    avg_cost = 0.0

                trade = {
                    "date": date_str, "side": "sell",
                    "price": price, "volume": vol,
                    "amount": price * vol,
                    "commission": cost.commission,
                    "stamp_tax": cost.stamp_tax,
                    "transfer_fee": cost.transfer_fee,
                    "slippage": cost.slippage_cost,
                    "total_fee": cost.total,
                    "cash_after": round(cash, 4),
                    "position_after": position,
                }
                trades.append(trade)

                if save_to_db:
                    try:
                        insert_trade(
                            strategy=strategy_name, mode="backtest",
                            stock_code=stock_code, side="sell",
                            volume=vol, price=price,
                            commission=cost.commission, stamp_tax=cost.stamp_tax,
                            transfer_fee=cost.transfer_fee, slippage=cost.slippage_cost,
                            total_cost=cost.total,
                            reason=signal.reason, indicators=signal.indicators,
                            trade_time=f"{date_str} 10:30:00",
                        )
                    except Exception:
                        pass

        last_close = float(df["close"].iloc[-1])
        final_equity = cash + position * last_close

        equity_values = [e["value"] for e in equity_curve]
        m = self._metrics.calculate(equity_values, initial_capital, trades)

        result = {
            "total_trades": len(trades),
            "final_value": round(final_equity, 2),
            "total_return": m["total_return"],
            "return_rate": m["return_rate"],
            "annualized_return": m["annualized_return"],
            "max_drawdown": m["max_drawdown"],
            "sharpe_ratio": m["sharpe_ratio"],
            "calmar_ratio": m["calmar_ratio"],
            "win_rate": m["win_rate"],
            "equity_curve": equity_curve,
            "trades": trades,
        }

        if save_to_db:
            try:
                run_id = f"bt_{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}"
                insert_backtest_run({
                    "run_id": run_id,
                    "strategy": strategy_name,
                    "start_date": start_date,
                    "end_date": end_date,
                    "params": params or {},
                    "initial_cash": initial_capital,
                    "final_equity": result["final_value"],
                    "total_return": result["return_rate"],
                    "annual_return": result["annualized_return"],
                    "max_drawdown": result["max_drawdown"],
                    "sharpe_ratio": result["sharpe_ratio"],
                    "win_rate": result["win_rate"],
                    "total_trades": result["total_trades"],
                    "equity_curve": equity_curve,
                })
                result["run_id"] = run_id
            except Exception:
                pass

        return result

    def _feed_daily_close(self, strategy: StrategyBase, stock_code: str, close: float, date_str: str):
        """Feed daily close to strategy for MA/RSI accumulation."""
        if not hasattr(strategy, '_price_history'):
            strategy._price_history = {}
        if stock_code not in strategy._price_history:
            strategy._price_history[stock_code] = []
        if not strategy._price_history[stock_code] or date_str != getattr(strategy, '_last_feed_date', ''):
            strategy._price_history[stock_code].append(close)
            if len(strategy._price_history[stock_code]) > 500:
                strategy._price_history[stock_code] = strategy._price_history[stock_code][-500:]
            strategy._last_feed_date = date_str
