"""
核心回测引擎

事件驱动回测循环，支持日线级别的策略回测。
包含完整的费率计算 (佣金/印花税/过户费/滑点)。
基准由独立的 BaselineEngine 执行，策略通过 strategy_type 声明基准类型。
"""

import asyncio
import concurrent.futures
from datetime import datetime
from typing import Optional

import numpy as np
import pandas as pd

from backend.core.logging import get_logger
from backend.backtest.data_provider import DataProvider
from backend.backtest.metrics import MetricsCalculator, calc_xirr
from backend.backtest.baseline import BaselineEngine
from backend.engine.indicators import round_to_lot
from backend.trade.fees import FeeCalculator

logger = get_logger("backtest_engine")

_EXECUTOR = concurrent.futures.ThreadPoolExecutor(max_workers=4)


def _run_coro_in_thread(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


class BacktestEngine:
    """回测引擎

    按交易日逐日执行策略计算，记录每次交易的费率和净值变化。
    基准对比由 BaselineEngine 独立执行。
    """

    def __init__(self):
        self._data_provider = DataProvider(prefer="xtquant")
        self._fee_calc = FeeCalculator()
        self._metrics = MetricsCalculator()

    def run(
        self,
        strategy_name: str,
        stock_code: str,
        start_date: str,
        end_date: str,
        params: dict = None,
        initial_capital: float = 100000.0,
    ) -> dict:
        """运行回测

        Args:
            strategy_name: 策略名称
            stock_code: 股票代码
            start_date: 开始日期 YYYYMMDD
            end_date: 结束日期 YYYYMMDD
            params: 策略参数
            initial_capital: 初始资金

        Returns:
            回测结果 dict
        """
        logger.info(f"Loading data for {stock_code} {start_date}-{end_date}")
        df = self._data_provider.get_kline(
            stock_code, start_date, end_date,
            fields=["close", "open", "high", "low", "volume"],
        )

        if df is None or len(df) == 0:
            logger.error(f"No data for {stock_code}")
            return {"error": f"No data for {stock_code}"}

        strategy = self._load_strategy(strategy_name, params)
        if strategy is None:
            return {"error": f"Strategy '{strategy_name}' not found"}

        coro = self._run_strategy_loop(df, strategy, initial_capital, stock_code)
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return _run_coro_in_thread(coro)
        else:
            future = _EXECUTOR.submit(_run_coro_in_thread, coro)
            return future.result()

    def _load_strategy(self, name: str, params: dict = None):
        from backend.engine.strategy_registry import get, create
        cls = get(name)
        if cls is None:
            return None
        instance = create(name, params or {})
        return instance

    async def _run_strategy_loop(
        self, df: pd.DataFrame, strategy, initial_capital: float, stock_code: str,
    ) -> dict:
        """逐日执行策略回测循环"""
        import importlib
        from unittest.mock import patch

        cash = initial_capital
        position = 0
        avg_cost = 0.0

        trades = []
        equity_curve = []
        buy_signals = []
        cash_flows = []

        cash_flows.append({"date": str(df.iloc[0]["time"]), "amount": float(-initial_capital)})

        param = strategy.params
        days = param.get("investment_days", ["Wednesday"])
        from backend.core.trading_calendar import _WEEKDAY_MAP as weekday_map

        strategy_module = importlib.import_module(strategy.__class__.__module__)
        utils_module = importlib.import_module(
            strategy.__class__.__module__.rsplit(".", 1)[0] + ".strategy_utils"
        )

        for i, row in df.iterrows():
            date_str = str(row["time"])
            close = float(row["close"])
            open_price = float(row["open"]) if pd.notna(row.get("open")) else close

            if close <= 0 or np.isnan(close):
                continue

            equity = cash + position * close
            equity_curve.append({"date": date_str, "value": round(equity, 2)})

            try:
                dt = datetime.strptime(date_str, "%Y%m%d")
            except ValueError:
                continue
            bt_datetime = dt.replace(hour=10, minute=30)

            weekday = dt.weekday()
            is_day = any(weekday_map.get(d.strip().lower(), -1) == weekday for d in days)

            if not is_day:
                code = stock_code
                if code not in strategy._price_history:
                    strategy._price_history[code] = []
                strategy._price_history[code].append(close)
                if len(strategy._price_history[code]) > 400:
                    strategy._price_history[code] = strategy._price_history[code][-400:]
                continue

            from backend.engine.strategy_base import Quote
            quote = Quote(
                stock_code=stock_code,
                last_price=close,
                open=open_price,
                high=float(row["high"]) if pd.notna(row.get("high")) else close,
                low=float(row["low"]) if pd.notna(row.get("low")) else close,
                last_close=float(df["close"].iloc[i - 1]) if i > 0 else close,
            )

            with patch.object(strategy_module, 'datetime') as mock_dt1, \
                 patch.object(utils_module, 'datetime') as mock_dt2:
                for m in (mock_dt1, mock_dt2):
                    m.now.return_value = bt_datetime
                    m.side_effect = lambda *args, **kw: datetime(*args, **kw)

                try:
                    signal = await strategy.on_quote(quote)
                except Exception as e:
                    logger.error(f"Strategy error on {date_str}: {e}")
                    continue

            if signal is None or signal.side == "skip" or signal.volume <= 0:
                continue

            buy_volume = signal.volume
            buy_price = close

            cost = self._fee_calc.calc_trade_cost(buy_price, buy_volume, "buy")
            total_needed = buy_price * buy_volume + cost.total
            if cash < total_needed:
                continue

            cash -= total_needed
            old_cost_total = avg_cost * position
            position += buy_volume
            avg_cost = (old_cost_total + buy_price * buy_volume) / position if position > 0 else 0
            new_equity = cash + position * close

            trades.append({
                "date": date_str, "side": "buy",
                "price": buy_price, "volume": buy_volume,
                "amount": buy_price * buy_volume,
                "commission": cost.commission,
                "stamp_tax": cost.stamp_tax,
                "transfer_fee": cost.transfer_fee,
                "slippage": cost.slippage_cost,
                "total_fee": cost.total,
                "cash_after": round(cash, 4),
                "position_after": position,
                "avg_cost_after": round(avg_cost, 4),
                "equity_after": round(new_equity, 2),
            })

            cash_flows.append({"date": date_str, "amount": float(-total_needed)})
            buy_signals.append({"date": date_str, "price": buy_price})
            logger.debug(f"[{date_str}] Buy {stock_code} x{buy_volume} @ {buy_price:.4f} (fee={cost.total:.2f})")

        last_close = float(df["close"].iloc[-1])
        if position > 0:
            final_equity = cash + position * last_close
        else:
            final_equity = cash
        cash_flows.append({"date": str(df.iloc[-1]["time"]), "amount": float(final_equity)})

        equity_values = [e["value"] for e in equity_curve]
        metrics = self._metrics.calculate(equity_values, initial_capital, trades)
        xirr = calc_xirr(cash_flows)
        return_on_deployed = _calc_return_on_deployed(trades, final_equity)
        drawdown_curve = _calc_drawdown_curve(equity_curve)
        monthly_returns = _calc_monthly_returns(equity_curve, initial_capital)

        baseline_config = getattr(strategy, 'get_baseline_config', lambda: {})()
        baseline_type = getattr(strategy, 'strategy_type', 'buy_hold')
        baseline_engine = BaselineEngine(self._fee_calc)
        df_for_baseline = self._data_provider.get_kline(
            stock_code, str(df.iloc[0]["time"]), str(df.iloc[-1]["time"]),
            fields=["close", "open", "high", "low", "volume"],
        ) if df is not None else df

        baseline_result = baseline_engine.run(
            baseline_type=baseline_type,
            df=df_for_baseline,
            baseline_config=baseline_config,
            initial_capital=initial_capital,
        )

        return {
            "total_trades": len(trades),
            "profitable_trades": sum(1 for t in trades if t["price"] > 0),
            "total_investment": sum(t["amount"] for t in trades),
            "final_value": round(final_equity, 2),
            "total_return": round(final_equity - initial_capital, 2),
            "return_rate": metrics["return_rate"],
            "annualized_return": metrics["annualized_return"],
            "max_drawdown": metrics["max_drawdown"],
            "volatility": metrics["volatility"],
            "sharpe_ratio": metrics["sharpe_ratio"],
            "calmar_ratio": metrics["calmar_ratio"],
            "win_rate": metrics.get("win_rate", 0),
            "xirr": xirr,
            "return_on_deployed": return_on_deployed,
            "equity_curve": equity_curve,
            "buy_signals": buy_signals,
            "trades": trades,
            "drawdown_curve": drawdown_curve,
            "monthly_returns": monthly_returns,
            "baseline": baseline_result,
        }


def run_backtest(
    strategy: str,
    stock_code: str,
    duration: str = "1y",
    initial_capital: float = 100000.0,
) -> dict:
    """便捷回测接口"""
    from backend.backtest.data_provider import calculate_date_range
    start, end = calculate_date_range(duration)

    engine = BacktestEngine()
    return engine.run(strategy, stock_code, start, end, initial_capital=initial_capital)


def _calc_drawdown_curve(equity_curve: list) -> list:
    if not equity_curve:
        return []
    values = np.array([e["value"] for e in equity_curve], dtype=float)
    peak = np.maximum.accumulate(values)
    drawdowns = (values - peak) / np.where(peak != 0, peak, 1.0)
    return [{"date": equity_curve[i]["date"], "drawdown": round(float(drawdowns[i]), 6)}
            for i in range(len(equity_curve))]


def _calc_monthly_returns(equity_curve: list, initial_capital: float) -> list:
    if not equity_curve or len(equity_curve) < 2:
        return []
    monthly = {}
    for e in equity_curve:
        date_str = e["date"]
        if len(date_str) < 6:
            continue
        ym = date_str[:6]
        monthly[ym] = e["value"]

    if not monthly:
        return []

    sorted_months = sorted(monthly.keys())
    result = []
    prev_value = initial_capital
    for i, ym in enumerate(sorted_months):
        curr_value = monthly[ym]
        ret = (curr_value / prev_value - 1) if prev_value > 0 else 0.0
        result.append({
            "year": int(ym[:4]),
            "month": int(ym[4:6]),
            "return": round(ret, 6),
        })
        prev_value = curr_value
    return result


def _calc_return_on_deployed(trades: list, final_equity: float) -> float:
    total_invested = sum(t["amount"] + t.get("total_fee", 0)
                         for t in trades if t.get("side") == "buy")
    if total_invested <= 0:
        return 0.0
    return round((final_equity - total_invested) / total_invested, 6)
