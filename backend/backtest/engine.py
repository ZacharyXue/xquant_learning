"""
核心回测引擎

事件驱动回测循环，支持日线级别的策略回测。
包含完整的费率计算 (佣金/印花税/过户费/滑点)。
"""

import asyncio
from datetime import datetime, timedelta
from typing import Optional

import numpy as np
import pandas as pd

from backend.core.logging import get_logger
from backend.backtest.data_provider import DataProvider
from backend.backtest.metrics import MetricsCalculator
from backend.trade.fees import FeeCalculator, TradeCost

logger = get_logger("backtest_engine")


class BacktestEngine:
    """回测引擎

    按交易日逐日执行策略计算，记录每次交易的费率和净值变化。
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
        # 加载数据
        logger.info(f"Loading data for {stock_code} {start_date}-{end_date}")
        df = self._data_provider.get_kline(
            stock_code, start_date, end_date,
            fields=["close", "open", "high", "low", "volume"],
        )

        if df is None or len(df) == 0:
            logger.error(f"No data for {stock_code}")
            return {"error": f"No data for {stock_code}"}

        # 导入策略
        strategy = self._load_strategy(strategy_name, params)
        if strategy is None:
            return {"error": f"Strategy '{strategy_name}' not found"}

        # 执行回测
        return self._run_strategy_loop(df, strategy, initial_capital, stock_code)

    def _load_strategy(self, name: str, params: dict = None):
        """加载策略实例"""
        from backend.engine.strategy_registry import get, create
        cls = get(name)
        if cls is None:
            return None
        instance = create(name, params or {})
        return instance

    def _run_strategy_loop(
        self, df: pd.DataFrame, strategy, initial_capital: float, stock_code: str,
    ) -> dict:
        """逐日执行策略回测循环"""
        cash = initial_capital
        position = 0  # 持仓数量
        avg_cost = 0.0

        trades = []  # 交易记录
        equity_curve = []  # 权益曲线
        buy_signals = []  # 买入信号

        param = strategy.params
        days = param.get("investment_days", ["周三"])
        weekday_map = {"周一": 0, "周二": 1, "周三": 2, "周四": 3, "周五": 4,
                       "Monday": 0, "Tuesday": 1, "Wednesday": 2, "Thursday": 3, "Friday": 4}

        for i, row in df.iterrows():
            date_str = str(row["time"])
            close = float(row["close"])
            open_price = float(row["open"]) if pd.notna(row.get("open")) else close

            # 权益曲线
            equity = cash + position * close
            equity_curve.append({"date": date_str, "value": round(equity, 2)})

            # 检查是否为定投日
            try:
                dt = datetime.strptime(date_str, "%Y%m%d")
            except ValueError:
                continue

            weekday = dt.weekday()
            is_day = any(weekday_map.get(d.strip(), -1) == weekday for d in days)
            if not is_day:
                continue

            # 计算信号
            from backend.engine.strategy_base import Quote
            quote = Quote(
                stock_code=stock_code,
                last_price=close,
                open=open_price,
                high=float(row["high"]) if pd.notna(row.get("high")) else close,
                low=float(row["low"]) if pd.notna(row.get("low")) else close,
                last_close=float(df["close"].iloc[i - 1]) if i > 0 else close,
            )

            # Call strategy synchronously via asyncio.run
            signal = None
            try:
                signal = asyncio.run(strategy.on_quote(quote))
            except RuntimeError:
                # If already in an event loop, warn and skip
                logger.warning(f"Skipping async signal for {date_str}: nested event loop")
            except Exception as e:
                logger.error(f"Strategy error on {date_str}: {e}")

            if signal is None or signal.side == "skip" or signal.volume <= 0:
                continue

            buy_volume = signal.volume
            buy_price = close  # 回测中以收盘价成交

            # 费率计算
            cost = self._fee_calc.calc_trade_cost(buy_price, buy_volume, "buy")

            # 风控: 资金检查
            total_needed = buy_price * buy_volume + cost.total
            if cash < total_needed:
                continue

            # 执行交易
            cash -= total_needed
            old_cost_total = avg_cost * position
            position += buy_volume
            avg_cost = (old_cost_total + buy_price * buy_volume) / position if position > 0 else 0

            trades.append({
                "date": date_str,
                "price": buy_price,
                "volume": buy_volume,
                "commission": cost.commission,
                "stamp_tax": cost.stamp_tax,
                "transfer_fee": cost.transfer_fee,
                "slippage": cost.slippage_cost,
                "total_fee": cost.total,
                "amount": buy_price * buy_volume,
            })

            buy_signals.append({"date": date_str, "price": buy_price})
            logger.debug(f"[{date_str}] Buy {stock_code} x{buy_volume} @ {buy_price:.4f} (fee={cost.total:.2f})")

        # 最终平仓
        if position > 0:
            last_close = float(df["close"].iloc[-1])
            final_equity = cash + position * last_close
        else:
            final_equity = cash

        # 计算指标
        equity_values = [e["value"] for e in equity_curve]
        metrics = self._metrics.calculate(equity_values, initial_capital, trades)

        return {
            "total_trades": len(trades),
            "profitable_trades": sum(1 for t in trades if t["price"] > 0),
            "total_investment": sum(t["amount"] for t in trades),
            "final_value": round(final_equity, 2),
            "return_rate": metrics["return_rate"],
            "annualized_return": metrics["annualized_return"],
            "max_drawdown": metrics["max_drawdown"],
            "volatility": metrics["volatility"],
            "sharpe_ratio": metrics["sharpe_ratio"],
            "calmar_ratio": metrics["calmar_ratio"],
            "win_rate": metrics.get("win_rate", 0),
            "equity_curve": equity_curve,
            "buy_signals": buy_signals,
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
