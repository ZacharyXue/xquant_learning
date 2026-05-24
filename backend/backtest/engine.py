"""
核心回测引擎

事件驱动回测循环，支持日线级别的策略回测。
包含完整的费率计算 (佣金/印花税/过户费/滑点)。
"""

import asyncio
import concurrent.futures
from datetime import datetime, timedelta
from typing import Optional

import numpy as np
import pandas as pd

from backend.core.logging import get_logger
from backend.backtest.data_provider import DataProvider
from backend.backtest.metrics import MetricsCalculator
from backend.engine.indicators import round_to_lot
from backend.trade.fees import FeeCalculator, TradeCost

logger = get_logger("backtest_engine")

# 全局线程池用于回测
_EXECUTOR = concurrent.futures.ThreadPoolExecutor(max_workers=4)


def _run_coro_in_thread(coro):
    """在线程中运行协程并返回结果"""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


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

        # 执行回测 (在线程池中运行，避免事件循环冲突)
        coro = self._run_strategy_loop(df, strategy, initial_capital, stock_code)
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return _run_coro_in_thread(coro)
        else:
            future = _EXECUTOR.submit(_run_coro_in_thread, coro)
            return future.result()

    def _load_strategy(self, name: str, params: dict = None):
        """加载策略实例"""
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
        position = 0  # 持仓数量
        avg_cost = 0.0

        trades = []  # 交易记录
        equity_curve = []  # 权益曲线
        buy_signals = []  # 买入信号

        # Benchmark: 同周期固定金额定投 (同等资金、同等定投日、不做择时)
        bench_cash = initial_capital
        bench_position = 0
        bench_avg_cost = 0.0
        bench_equity_curve = []  # benchmark 权益曲线

        param = strategy.params
        bench_base_volume = param.get("base_volume", 500)
        bench_lot_size = param.get("lot_size", 100)
        days = param.get("investment_days", ["Wednesday"])
        from backend.core.trading_calendar import _WEEKDAY_MAP as weekday_map

        # 策略所在的模块 (用于 mock datetime)
        strategy_module = importlib.import_module(strategy.__class__.__module__)
        # 也 mock strategy_utils 的 datetime
        utils_module = importlib.import_module(
            strategy.__class__.__module__.rsplit(".", 1)[0] + ".strategy_utils"
        )

        for i, row in df.iterrows():
            date_str = str(row["time"])
            close = float(row["close"])
            open_price = float(row["open"]) if pd.notna(row.get("open")) else close

            # 跳过无效价格 (未上市日期、停牌等)
            if close <= 0 or np.isnan(close):
                continue

            # 权益曲线 (策略)
            equity = cash + position * close
            equity_curve.append({"date": date_str, "value": round(equity, 2)})

            # Benchmark 权益曲线
            bench_equity = bench_cash + bench_position * close
            bench_equity_curve.append({"date": date_str, "value": round(bench_equity, 2)})

            # 解析日期并构造回测时间 (10:30 AM, 交易时段内)
            try:
                dt = datetime.strptime(date_str, "%Y%m%d")
            except ValueError:
                continue
            bt_datetime = dt.replace(hour=10, minute=30)

            # 检查是否为定投日
            weekday = dt.weekday()
            is_day = any(weekday_map.get(d.strip().lower(), -1) == weekday for d in days)

            if not is_day:
                # 非定投日: 仅更新价格历史 (策略需要积累足够数据)
                code = stock_code
                if code not in strategy._price_history:
                    strategy._price_history[code] = []
                strategy._price_history[code].append(close)
                if len(strategy._price_history[code]) > 400:
                    strategy._price_history[code] = strategy._price_history[code][-400:]
                continue

            # === 定投日: Benchmark 固定金额买入 ===
            bench_vol = round_to_lot(bench_base_volume, bench_lot_size)
            bench_cost = self._fee_calc.calc_trade_cost(close, bench_vol, "buy")
            bench_total = close * bench_vol + bench_cost.total
            if bench_cash >= bench_total:
                bench_cash -= bench_total
                old_bench = bench_avg_cost * bench_position
                bench_position += bench_vol
                bench_avg_cost = (old_bench + close * bench_vol) / bench_position if bench_position > 0 else 0

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

            # Mock datetime.now() 以匹配回测日期和时间
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

        # 最终平仓 (策略)
        if position > 0:
            last_close = float(df["close"].iloc[-1])
            final_equity = cash + position * last_close
        else:
            final_equity = cash

        # 最终平仓 (benchmark)
        if bench_position > 0:
            bench_final = bench_cash + bench_position * last_close
        else:
            bench_final = bench_cash

        # 计算指标
        equity_values = [e["value"] for e in equity_curve]
        metrics = self._metrics.calculate(equity_values, initial_capital, trades)

        # Benchmark 指标
        bench_values = [e["value"] for e in bench_equity_curve]
        bench_metrics = self._metrics.calculate(bench_values, initial_capital, [])

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
            "benchmark": {
                "final_value": round(bench_final, 2),
                "return_rate": bench_metrics["return_rate"],
                "annualized_return": bench_metrics["annualized_return"],
                "max_drawdown": bench_metrics["max_drawdown"],
                "sharpe_ratio": bench_metrics["sharpe_ratio"],
                "calmar_ratio": bench_metrics["calmar_ratio"],
                "equity_curve": bench_equity_curve,
            },
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
