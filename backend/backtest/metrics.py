"""
绩效指标计算

提供完整的回测绩效指标体系:
- 收益率 / 年化收益率
- 最大回撤 / 卡玛比率
- 波动率 / 夏普比率
- 胜率 / 盈亏比
- XIRR (资金加权收益率)
"""

from datetime import datetime
from typing import Optional

import numpy as np


class MetricsCalculator:
    """绩效指标计算器"""

    def calculate(
        self,
        equity_curve: list[float],
        initial_capital: float,
        trades: list[dict] = None,
        risk_free_rate: float = 0.03,  # 无风险利率 3%
    ) -> dict:
        """计算全套绩效指标

        Args:
            equity_curve: 权益曲线 (每日账户总值)
            initial_capital: 初始资金
            trades: 交易记录列表
            risk_free_rate: 无风险年利率

        Returns:
            指标字典
        """
        if not equity_curve or len(equity_curve) < 2:
            return self._empty_result()

        values = np.array(equity_curve, dtype=float)

        # 收益率
        final_value = values[-1]
        total_return = final_value - initial_capital
        return_rate = (final_value / initial_capital) - 1

        # 年化收益率
        days = len(values)
        years = days / 252.0
        try:
            annualized_return = (final_value / initial_capital) ** (1.0 / years) - 1 if years > 0 else 0.0
        except (OverflowError, ValueError, ZeroDivisionError):
            annualized_return = 0.0

        if np.isnan(annualized_return) or np.isinf(annualized_return):
            annualized_return = 0.0

        # 最大回撤
        peak = np.maximum.accumulate(values)
        drawdowns = (values - peak) / np.where(peak != 0, peak, 1.0)
        max_drawdown = float(np.min(drawdowns))
        if np.isnan(max_drawdown) or np.isinf(max_drawdown):
            max_drawdown = 0.0

        # 波动率
        daily_returns = np.diff(values) / values[:-1]
        volatility = float(np.std(daily_returns) * np.sqrt(252)) if len(daily_returns) > 0 else 0.0

        # 夏普比率
        sharpe_ratio = self._calc_sharpe(daily_returns, risk_free_rate) if len(daily_returns) > 0 else 0.0

        # 卡玛比率
        calmar_ratio = annualized_return / abs(max_drawdown) if max_drawdown != 0 else 0.0

        # 胜率
        win_rate = 0.0
        if trades and len(trades) > 0:
            profitable = sum(1 for t in trades if t.get("price", 0) > 0)
            win_rate = profitable / len(trades)

        return {
            "total_return": round(total_return, 2),
            "return_rate": round(return_rate, 6),
            "annualized_return": round(annualized_return, 6),
            "max_drawdown": round(max_drawdown, 6),
            "volatility": round(volatility, 6),
            "sharpe_ratio": round(sharpe_ratio, 4),
            "calmar_ratio": round(calmar_ratio, 4),
            "win_rate": round(win_rate, 4),
        }

    def _calc_sharpe(self, daily_returns: np.ndarray, risk_free_rate: float) -> float:
        """计算夏普比率"""
        rf_daily = risk_free_rate / 252.0
        excess = daily_returns - rf_daily
        if len(excess) < 2:
            return 0.0
        std = np.std(excess)
        if std == 0 or np.isnan(std):
            return 0.0
        sharpe = float(np.mean(excess) / std * np.sqrt(252))
        if np.isnan(sharpe) or np.isinf(sharpe):
            return 0.0
        # DB NUMERIC(10,4) 边界保护
        return max(-9999.9999, min(9999.9999, sharpe))

    @staticmethod
    def _empty_result() -> dict:
        return {
            "total_return": 0.0,
            "return_rate": 0.0,
            "annualized_return": 0.0,
            "max_drawdown": 0.0,
            "volatility": 0.0,
            "sharpe_ratio": 0.0,
            "calmar_ratio": 0.0,
            "win_rate": 0.0,
        }


def annualize_return(total_return: float, days: int) -> float:
    """年化收益率"""
    if days <= 0:
        return 0.0
    years = days / 252.0
    return (1 + total_return) ** (1.0 / years) - 1


def calc_xirr(cash_flows: list[dict], max_iter: int = 100, tol: float = 1e-8) -> float:
    """计算资金加权年化收益率 (XIRR)

    使用 Newton-Raphson 法求解 IRR, 再年化。

    Args:
        cash_flows: 现金流列表 [{date: "20240101", amount: -1000}, ...]
                   负值 = 资金流出(投入), 正值 = 资金流入(取出/终值)
        max_iter: 最大迭代次数
        tol: 收敛容差

    Returns:
        年化收益率 (小数), 计算失败返回 0.0
    """
    if not cash_flows or len(cash_flows) < 2:
        return 0.0

    # 解析日期并计算距首日天数
    ref_date = datetime.strptime(str(cash_flows[0]["date"])[:8], "%Y%m%d")
    times = []
    amounts = []
    for cf in cash_flows:
        t = datetime.strptime(str(cf["date"])[:8], "%Y%m%d")
        days = (t - ref_date).days
        times.append(days / 365.25)  # 年化时间
        amounts.append(float(cf["amount"]))

    amounts_arr = np.array(amounts, dtype=float)
    times_arr = np.array(times, dtype=float)

    if np.all(amounts_arr <= 0) or np.all(amounts_arr >= 0):
        return 0.0

    guess = 0.1
    for _ in range(max_iter):
        disc = (1.0 + guess) ** times_arr
        fval = np.sum(amounts_arr / disc)
        dfval = np.sum(-times_arr * amounts_arr / ((1.0 + guess) ** (times_arr + 1.0)))

        if abs(dfval) < 1e-12:
            break

        guess_new = guess - fval / dfval
        if abs(guess_new - guess) < tol:
            guess = guess_new
            break
        if guess_new <= -1.0:
            guess = guess / 2.0
        else:
            guess = guess_new

    if guess <= -1.0 or np.isnan(guess) or np.isinf(guess):
        return 0.0

    return round(guess, 6)
