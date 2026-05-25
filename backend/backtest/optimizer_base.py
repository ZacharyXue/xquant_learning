"""
优化器抽象基类

提供统一的优化器接口和公共逻辑。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

from backend.core.logging import get_logger

logger = get_logger("optimizer")


@dataclass
class TrialResult:
    """单次优化试验结果"""
    params: dict[str, any]
    metric_value: float
    metrics: dict = field(default_factory=dict)
    run_id: Optional[int] = None


class BaseOptimizer(ABC):
    """优化器抽象基类"""

    def __init__(
        self,
        strategy_name: str,
        stock_code: str,
        start_date: str,
        end_date: str,
        tuning_space: list,
        metric: str = "sharpe_ratio",
        n_trials: int = 100,
        n_jobs: int = 1,
        initial_capital: float = 100000.0,
    ):
        self.strategy_name = strategy_name
        self.stock_code = stock_code
        self.start_date = start_date
        self.end_date = end_date
        self.tuning_space = tuning_space
        self.metric = metric
        self.n_trials = n_trials
        self.n_jobs = n_jobs
        self.initial_capital = initial_capital

    @abstractmethod
    def optimize(self) -> list[TrialResult]:
        """运行优化, 返回按 metric 排序的结果列表"""

    def _run_single(self, params: dict) -> TrialResult:
        from backend.backtest.engine import BacktestEngine
        engine = BacktestEngine()
        result = engine.run(
            self.strategy_name, self.stock_code,
            self.start_date, self.end_date,
            params=params,
            initial_capital=self.initial_capital,
        )
        mv = result.get(self.metric, 0)
        return TrialResult(
            params=params,
            metric_value=mv,
            metrics={k: v for k, v in result.items()
                     if k not in ("equity_curve", "buy_signals", "trades",
                                  "drawdown_curve", "monthly_returns", "baseline")},
        )

    def _sort_results(self, results: list[TrialResult]) -> list[TrialResult]:
        results.sort(key=lambda r: r.metric_value, reverse=True)
        return results
