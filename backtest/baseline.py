"""Baseline comparison: DCA and Buy & Hold"""
import pandas as pd
from trade.fees import FeeCalculator
from backtest.engine import _weekday_from_name
from engine.indicators import round_to_lot

def run_dca_baseline(df, stock_code, initial_capital, investment_days, base_volume, lot_size=100):
    """DCA baseline — same frequency, same amount, no timing"""
    fee = FeeCalculator()
    target_days = {_weekday_from_name(d) for d in investment_days}
    target_days.discard(-1)
    cash = initial_capital; position = 0; trades_count = 0; equity_curve = []
    for _, row in df.iterrows():
        date_str = str(row["time"]); close = float(row["close"])
        try:
            from datetime import datetime
            dt = datetime.strptime(date_str.strip()[:8], "%Y%m%d")
        except ValueError:
            continue
        in_day = dt.weekday() in target_days
        if in_day:
            vol = round_to_lot(base_volume, lot_size)
            if vol > 0:
                cost = fee.calc_trade_cost(close, vol, "buy")
                needed = close * vol + cost.total
                if cash >= needed:
                    cash -= needed; position += vol; trades_count += 1
        equity_curve.append({"date": date_str, "value": round(cash + position * close, 2)})
    last_close = float(df["close"].iloc[-1]); final_equity = cash + position * last_close
    return {"baseline_type": "dca", "final_value": round(final_equity, 2),
            "total_return": round((final_equity / initial_capital - 1) if initial_capital > 0 else 0, 6),
            "total_trades": trades_count, "equity_curve": equity_curve}

def run_buyhold_baseline(df, stock_code, initial_capital, lot_size=100):
    """Buy & Hold baseline — buy all on day 1, sell on last day"""
    fee = FeeCalculator()
    first_close = float(df["close"].iloc[0]); last_close = float(df["close"].iloc[-1])
    vol = round_to_lot(int(initial_capital / first_close), lot_size)
    if vol <= 0:
        return {"baseline_type": "buy_hold", "final_value": initial_capital, "total_return": 0.0, "total_trades": 0, "equity_curve": []}
    cost = fee.calc_trade_cost(first_close, vol, "buy")
    cash = initial_capital - (first_close * vol + cost.total)
    equity_curve = []
    for _, row in df.iterrows():
        date_str = str(row["time"]); c = float(row["close"])
        equity_curve.append({"date": date_str, "value": round(cash + vol * c, 2)})
    sell_cost = fee.calc_trade_cost(last_close, vol, "sell")
    final_equity = cash + vol * last_close - sell_cost.total
    return {"baseline_type": "buy_hold", "final_value": round(final_equity, 2),
            "total_return": round((final_equity / initial_capital - 1) if initial_capital > 0 else 0, 6),
            "total_trades": 2, "equity_curve": equity_curve}
