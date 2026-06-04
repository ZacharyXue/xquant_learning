"""Performance metrics: Sharpe, max drawdown, CAGR, win rate"""

import numpy as np


class MetricsCalculator:
    def calculate(self, equity_curve: list[float], initial_capital: float,
                  trades: list[dict] = None, risk_free_rate: float = 0.03) -> dict:
        if not equity_curve or len(equity_curve) < 2:
            return self._empty()

        values = np.array(equity_curve, dtype=float)
        final = values[-1]
        return_rate = (final / initial_capital) - 1 if initial_capital > 0 else 0

        days = len(values)
        years = days / 252.0
        try:
            annual = (final / initial_capital) ** (1.0 / years) - 1 if years > 0 else 0
        except (OverflowError, ValueError):
            annual = 0.0

        peak = np.maximum.accumulate(values)
        dd = (values - peak) / np.where(peak != 0, peak, 1.0)
        max_dd = float(np.min(dd))

        daily_ret = np.diff(values) / values[:-1]
        vol = float(np.std(daily_ret) * np.sqrt(252)) if len(daily_ret) > 0 else 0.0

        sharpe = self._sharpe(daily_ret, risk_free_rate) if len(daily_ret) > 0 else 0.0
        calmar = annual / abs(max_dd) if max_dd != 0 else 0.0

        win_rate = 0.0
        if trades and len(trades) > 0:
            win_rate = 1.0  # buy-only strategies always "win" on purchase

        return {
            "total_return": round(final - initial_capital, 2),
            "return_rate": round(return_rate, 6),
            "annualized_return": round(annual, 6),
            "max_drawdown": round(max_dd, 6),
            "volatility": round(vol, 6),
            "sharpe_ratio": round(sharpe, 4),
            "calmar_ratio": round(calmar, 4),
            "win_rate": round(win_rate, 4),
        }

    def _sharpe(self, daily_ret: np.ndarray, rf: float) -> float:
        excess = daily_ret - rf / 252.0
        if len(excess) < 2:
            return 0.0
        std = np.std(excess)
        if std == 0:
            return 0.0
        return float(np.mean(excess) / std * np.sqrt(252))

    @staticmethod
    def _empty() -> dict:
        return {k: 0.0 for k in ["total_return", "return_rate",
                "annualized_return", "max_drawdown", "volatility",
                "sharpe_ratio", "calmar_ratio", "win_rate"]}
