"""
基准执行器

根据策略声明的 strategy_type 独立执行基准回测。
支持三种内置基准: DCA(固定金额定投)、BuyHold(买入持有)、Index(市场指数)。

所有基准均独立于策略参数运行，仅使用 baseline_config 中的配置。
"""

from datetime import datetime
from typing import Optional

import numpy as np
import pandas as pd

from backend.core.logging import get_logger
from backend.core.trading_calendar import _WEEKDAY_MAP
from backend.engine.indicators import round_to_lot

logger = get_logger("baseline")


class BaselineEngine:
    """基准执行器

    根据 strategy_type 选择对应的基准实现:
    - "dca": 固定金额定投同一标的
    - "buy_hold": 首日全仓买入, 期末卖出
    - "index": 买入持有市场指数 (需要 index_code)
    """

    def __init__(self, fee_calc):
        self._fee_calc = fee_calc

    def run(
        self,
        baseline_type: str,
        df: pd.DataFrame,
        baseline_config: dict,
        initial_capital: float,
    ) -> dict:
        """执行基准回测

        Args:
            baseline_type: 基准类型 ("dca" | "buy_hold" | "index")
            df: K线 DataFrame, columns=[time, close, open, high, low, volume]
            baseline_config: 基准配置, 含 baseline_amount/investment_days/lot_size/index_code
            initial_capital: 初始资金

        Returns:
            {
                equity_curve: [{date, value}],
                trades: [{date, side, price, volume, amount, fees...}],
                cash_flows: [{date, amount}]  用于 XIRR 计算
                final_value, return_rate,
                max_drawdown, sharpe_ratio, calmar_ratio,
                drawdown_curve: [{date, drawdown}],
                monthly_returns: [{year, month, return}],
            }
        """
        if baseline_type == "dca":
            return self._run_dca(df, baseline_config, initial_capital)
        elif baseline_type in ("buy_hold", "momentum"):
            return self._run_buy_hold(df, baseline_config, initial_capital)
        elif baseline_type == "index":
            return self._run_index(df, baseline_config, initial_capital)
        else:
            logger.warning(f"Unknown baseline_type '{baseline_type}', falling back to buy_hold")
            return self._run_buy_hold(df, baseline_config, initial_capital)

    def _run_dca(
        self,
        df: pd.DataFrame,
        config: dict,
        initial_capital: float,
    ) -> dict:
        """固定金额定投基准

        每个定投日以固定金额买入标的, 资金独立于策略。
        这不是固定股数 — 而是每次投入固定金额, 按当日收盘价折算股数。

        关键参数 (来自 baseline_config):
        - baseline_amount: 每次定投金额 (默认 1000)
        - investment_days: 定投日列表 (如 ["Wednesday"])
        - lot_size: 每手股数 (默认 100)
        """
        cash = initial_capital
        position = 0
        trades = []
        equity_curve = []
        cash_flows = []

        baseline_amount = config.get("baseline_amount", 1000)
        investment_days = config.get("investment_days", ["Wednesday"])
        lot_size = config.get("lot_size", 100)

        cash_flows.append({"date": str(df.iloc[0]["time"]), "amount": float(-initial_capital)})

        for i, row in df.iterrows():
            date_str = str(row["time"])
            close = float(row["close"])
            if close <= 0 or np.isnan(close):
                _append_equity(equity_curve, date_str, cash, position, close)
                continue

            equity = cash + position * close
            equity_curve.append({"date": date_str, "value": round(equity, 2)})

            dt = _parse_date(date_str)
            if dt is None:
                continue

            if not _is_investment_day(dt.weekday(), investment_days):
                continue

            vol = int(baseline_amount / close / lot_size) * lot_size
            if vol <= 0:
                continue

            cost = self._fee_calc.calc_trade_cost(close, vol, "buy")
            total_needed = close * vol + cost.total
            if cash < total_needed:
                continue

            cash -= total_needed
            position += vol
            trades.append({
                "date": date_str, "side": "buy", "price": close,
                "volume": vol, "amount": round(close * vol, 4),
                "commission": cost.commission, "stamp_tax": cost.stamp_tax,
                "transfer_fee": cost.transfer_fee, "slippage": cost.slippage_cost,
                "total_fee": cost.total,
            })
            cash_flows.append({"date": date_str, "amount": float(-total_needed)})

        last_close = float(df["close"].iloc[-1])
        if position > 0:
            sell_cost = self._fee_calc.calc_trade_cost(last_close, position, "sell")
            final_cash = cash + last_close * position - sell_cost.total
            trades.append({
                "date": str(df.iloc[-1]["time"]), "side": "sell", "price": last_close,
                "volume": position, "amount": round(last_close * position, 4),
                "commission": sell_cost.commission, "stamp_tax": sell_cost.stamp_tax,
                "transfer_fee": sell_cost.transfer_fee, "slippage": sell_cost.slippage_cost,
                "total_fee": sell_cost.total,
            })
        else:
            final_cash = cash
        cash_flows.append({"date": str(df.iloc[-1]["time"]), "amount": float(final_cash)})

        return _build_result(equity_curve, trades, initial_capital, final_cash, cash_flows)

    def _run_buy_hold(
        self,
        df: pd.DataFrame,
        config: dict,
        initial_capital: float,
    ) -> dict:
        """买入持有基准

        首日以开盘价全仓买入, 期末以收盘价卖出 (含卖出费用)。
        """
        first_close = float(df["close"].iloc[0])
        lot_size = config.get("lot_size", 100)
        cash_flows = []
        trades = []
        equity_curve = []

        cash_flows.append({"date": str(df.iloc[0]["time"]), "amount": float(-initial_capital)})

        buy_vol = int(initial_capital / first_close / lot_size) * lot_size
        buy_cost = self._fee_calc.calc_trade_cost(first_close, buy_vol, "buy")
        cash = initial_capital - (first_close * buy_vol + buy_cost.total)
        position = buy_vol

        trades.append({
            "date": str(df.iloc[0]["time"]), "side": "buy", "price": first_close,
            "volume": buy_vol, "amount": round(first_close * buy_vol, 4),
            "commission": buy_cost.commission, "stamp_tax": buy_cost.stamp_tax,
            "transfer_fee": buy_cost.transfer_fee, "slippage": buy_cost.slippage_cost,
            "total_fee": buy_cost.total,
        })

        for i, row in df.iterrows():
            date_str = str(row["time"])
            close = float(row["close"])
            if close <= 0 or np.isnan(close):
                _append_equity(equity_curve, date_str, cash, position, close)
                continue
            equity = cash + position * close
            equity_curve.append({"date": date_str, "value": round(equity, 2)})

        last_close = float(df["close"].iloc[-1])
        if position > 0:
            sell_cost = self._fee_calc.calc_trade_cost(last_close, position, "sell")
            final_cash = cash + last_close * position - sell_cost.total
            trades.append({
                "date": str(df.iloc[-1]["time"]), "side": "sell", "price": last_close,
                "volume": position, "amount": round(last_close * position, 4),
                "commission": sell_cost.commission, "stamp_tax": sell_cost.stamp_tax,
                "transfer_fee": sell_cost.transfer_fee, "slippage": sell_cost.slippage_cost,
                "total_fee": sell_cost.total,
            })
        else:
            final_cash = cash
        cash_flows.append({"date": str(df.iloc[-1]["time"]), "amount": float(final_cash)})

        return _build_result(equity_curve, trades, initial_capital, final_cash, cash_flows)

    def _run_index(
        self,
        df: pd.DataFrame,
        config: dict,
        initial_capital: float,
    ) -> dict:
        """市场指数基准

        使用 index_code 获取指数K线数据, 买入持有。
        如果 index_code 未配置或无数据, 回退到 buy_hold。
        """
        index_code = config.get("index_code", "")
        if not index_code:
            logger.info("No index_code configured, falling back to buy_hold")
            return self._run_buy_hold(df, config, initial_capital)

        from backend.backtest.data_provider import DataProvider
        dp = DataProvider(prefer="xtquant")
        start = str(df.iloc[0]["time"])
        end = str(df.iloc[-1]["time"])
        index_df = dp.get_kline(index_code, start, end, period="1d")
        if index_df is None or len(index_df) == 0:
            logger.info(f"No data for index {index_code}, falling back to buy_hold")
            return self._run_buy_hold(df, config, initial_capital)

        return self._run_buy_hold(index_df, config, initial_capital)


def _is_investment_day(weekday: int, days: list[str]) -> bool:
    for d in days:
        if _WEEKDAY_MAP.get(d.strip().lower(), -1) == weekday:
            return True
    return False


def _parse_date(date_str: str) -> Optional[datetime]:
    try:
        return datetime.strptime(str(date_str)[:8], "%Y%m%d")
    except ValueError:
        return None


def _append_equity(equity_curve, date_str, cash, position, close):
    if position > 0 and close > 0:
        equity_curve.append({"date": date_str, "value": round(cash + position * close, 2)})
    else:
        equity_curve.append({"date": date_str, "value": round(cash, 2)})


def _build_result(
    equity_curve: list,
    trades: list,
    initial_capital: float,
    final_cash: float,
    cash_flows: list,
) -> dict:
    from backend.backtest.metrics import MetricsCalculator, calc_xirr

    equity_values = [e["value"] for e in equity_curve]
    metrics_calc = MetricsCalculator()
    metrics = metrics_calc.calculate(equity_values, initial_capital, trades)

    xirr = calc_xirr(cash_flows)

    drawdown_curve = _calc_drawdown_curve(equity_curve)
    monthly_returns = _calc_monthly_returns(equity_curve, initial_capital)

    return {
        "equity_curve": equity_curve,
        "trades": trades,
        "cash_flows": cash_flows,
        "final_value": round(final_cash, 2),
        "total_return": round(final_cash - initial_capital, 2),
        "return_rate": metrics["return_rate"],
        "annualized_return": metrics["annualized_return"],
        "max_drawdown": metrics["max_drawdown"],
        "volatility": metrics["volatility"],
        "sharpe_ratio": metrics["sharpe_ratio"],
        "calmar_ratio": metrics["calmar_ratio"],
        "win_rate": metrics.get("win_rate", 0),
        "xirr": xirr,
        "return_on_deployed": _calc_return_on_deployed(trades, final_cash),
        "drawdown_curve": drawdown_curve,
        "monthly_returns": monthly_returns,
        "total_investment": sum(t["amount"] for t in trades if t.get("side") == "buy"),
    }


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
        if i == 0 or ym != sorted_months[0]:
            prev_value = curr_value
    return result


def _calc_return_on_deployed(trades: list, final_cash: float) -> float:
    total_invested = sum(t["amount"] + t.get("total_fee", 0)
                         for t in trades if t.get("side") == "buy")
    if total_invested <= 0:
        return 0.0
    return round((final_cash - total_invested) / total_invested, 6)
