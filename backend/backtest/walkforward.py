"""
Walk-Forward 滚动验证

通过滚动窗口验证策略在样本外 (out-of-sample) 的表现，
检测参数过拟合并评估策略稳定性。
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

import numpy as np

from backend.core.logging import get_logger

logger = get_logger("walkforward")


@dataclass
class WalkForwardWindow:
    train_start: str
    train_end: str
    test_start: str
    test_end: str


class WalkForwardValidator:
    """Walk-Forward 滚动验证器

    将数据按滚动窗口分割为训练期和验证期:
    - 在训练期内优化策略参数
    - 在验证期 (样本外) 评估参数表现
    - 汇总所有窗口的验证结果，评估稳定性
    """

    def __init__(
        self,
        start_date: str,
        end_date: str,
        train_years: int = 3,
        test_years: int = 1,
    ):
        self.windows = self._generate_windows(start_date, end_date, train_years, test_years)

    def _generate_windows(
        self, start: str, end: str, train_y: int, test_y: int,
    ) -> list[WalkForwardWindow]:
        start_dt = datetime.strptime(start, "%Y%m%d")
        end_dt = datetime.strptime(end, "%Y%m%d")

        windows = []
        current = start_dt

        while True:
            train_start = current
            train_end = min(
                train_start + timedelta(days=train_y * 365),
                end_dt,
            )
            test_start = train_end + timedelta(days=1)
            test_end = min(
                test_start + timedelta(days=test_y * 365) - timedelta(days=1),
                end_dt,
            )

            if test_start >= end_dt:
                break
            if (test_end - test_start).days < 30:
                break

            windows.append(WalkForwardWindow(
                train_start=train_start.strftime("%Y%m%d"),
                train_end=train_end.strftime("%Y%m%d"),
                test_start=test_start.strftime("%Y%m%d"),
                test_end=test_end.strftime("%Y%m%d"),
            ))
            current = current + timedelta(days=test_y * 365)

        return windows

    def validate(
        self,
        strategy_name: str,
        stock_code: str,
        optimizer_class,
        tuning_space: list,
        metric: str = "sharpe_ratio",
        n_trials: int = 100,
        n_jobs: int = 1,
        initial_capital: float = 100000.0,
    ) -> dict:
        """执行 Walk-Forward 验证

        Args:
            strategy_name: 策略名称
            stock_code: 股票代码
            optimizer_class: 优化器类 (如 OptunaOptimizer)
            tuning_space: 参数搜索空间
            metric: 优化目标指标
            n_trials: 每次优化的 trial 数
            n_jobs: 并行度
            initial_capital: 初始资金

        Returns:
            {
                windows: [{train_start, train_end, test_start, test_end,
                          best_params, train_metrics, test_metrics}],
                summary: {avg_test_sharpe, test_sharpe_std, stability_score,
                          overfit_ratio, best_params_overall}
            }
        """
        from backend.backtest.engine import BacktestEngine

        logger.info(
            f"Walk-Forward: {len(self.windows)} windows, "
            f"{strategy_name} on {stock_code}"
        )

        window_results = []
        for wi, w in enumerate(self.windows):
            logger.info(f"Window {wi + 1}/{len(self.windows)}: train={w.train_start}-{w.train_end}, test={w.test_start}-{w.test_end}")

            opt = optimizer_class(
                strategy_name=strategy_name,
                stock_code=stock_code,
                start_date=w.train_start,
                end_date=w.train_end,
                tuning_space=tuning_space,
                metric=metric,
                n_trials=n_trials,
                n_jobs=n_jobs,
                initial_capital=initial_capital,
            )

            train_results = opt.optimize()
            best_params = train_results[0].params if train_results else {}
            train_metrics = self._extract_metrics(train_results[0]) if train_results else {}

            engine = BacktestEngine()
            test_result = engine.run(
                strategy_name, stock_code,
                w.test_start, w.test_end,
                params=best_params,
                initial_capital=initial_capital,
            )

            wr = {
                "train_start": w.train_start,
                "train_end": w.train_end,
                "test_start": w.test_start,
                "test_end": w.test_end,
                "best_params": best_params,
                "train_metrics": train_metrics,
                "test_metrics": self._extract_metrics(test_result),
            }
            window_results.append(wr)

        summary = self._summarize(window_results, metric)
        return {"windows": window_results, "summary": summary}

    def _extract_metrics(self, result) -> dict:
        if isinstance(result, dict):
            return {
                "sharpe_ratio": result.get("sharpe_ratio", 0),
                "calmar_ratio": result.get("calmar_ratio", 0),
                "return_rate": result.get("return_rate", 0),
                "xirr": result.get("xirr", 0),
                "return_on_deployed": result.get("return_on_deployed", 0),
                "max_drawdown": result.get("max_drawdown", 0),
                "annualized_return": result.get("annualized_return", 0),
            }
        if hasattr(result, "metrics"):
            return self._extract_metrics(result.metrics)
        return {}

    def _summarize(self, window_results: list[dict], metric: str) -> dict:
        if not window_results:
            return {
                "avg_test_sharpe": 0, "test_sharpe_std": 0,
                "stability_score": 0, "overfit_ratio": 0,
                "best_params_overall": {},
            }

        test_values = [w["test_metrics"].get(metric, 0) for w in window_results]
        train_values = [w["train_metrics"].get(metric, 0) for w in window_results]

        avg_test = float(np.mean(test_values)) if test_values else 0.0
        std_test = float(np.std(test_values)) if len(test_values) > 1 else 0.0

        avg_train = float(np.mean(train_values)) if train_values else 0.0
        overfit_ratio = avg_train / avg_test if abs(avg_test) > 0.0001 else 0.0

        stability_score = avg_test / std_test if std_test > 0.0001 else 0.0

        best_idx = int(np.argmax(test_values)) if test_values else 0
        best_params = window_results[best_idx]["best_params"] if window_results else {}

        return {
            "avg_test_sharpe": round(avg_test, 4),
            "test_sharpe_std": round(std_test, 4),
            "stability_score": round(stability_score, 4),
            "overfit_ratio": round(overfit_ratio, 4),
            "best_params_overall": best_params,
        }
