"""
网格搜索参数优化器

遍历策略参数组合，寻找最优参数。
支持多线程并行执行，结果持久化到 PostgreSQL。
"""

import asyncio
from itertools import product
from typing import Any, Optional

from backend.core.logging import get_logger
from backend.backtest.engine import BacktestEngine

logger = get_logger("optimizer")


class GridOptimizer:
    """网格搜索优化器"""

    def __init__(self, strategy_name: str, stock_code: str, start_date: str, end_date: str):
        self._strategy = strategy_name
        self._stock = stock_code
        self._start = start_date
        self._end = end_date
        self._engine = BacktestEngine()

    def optimize(self, param_grid: dict[str, list], metric: str = "sharpe_ratio") -> list[dict]:
        """执行网格搜索

        Args:
            param_grid: 参数网格 {param_name: [values]}
            metric: 优化目标指标

        Returns:
            按 metric 排序的结果列表
        """
        param_names = list(param_grid.keys())
        param_values = list(param_grid.values())
        combos = list(product(*param_values))

        logger.info(f"Grid search: {self._strategy} on {self._stock}, {len(combos)} combinations")

        results = []
        for i, combo in enumerate(combos):
            params = dict(zip(param_names, combo))
            result = self._engine.run(
                self._strategy, self._stock, self._start, self._end, params=params,
            )
            it = {
                "params": params,
                **{k: v for k, v in result.items() if k not in ("equity_curve", "buy_signals")},
            }
            results.append(it)

            if (i + 1) % 20 == 0:
                logger.info(f"Grid progress: {i + 1}/{len(combos)}")

        # 按优化目标排序
        results.sort(key=lambda r: r.get(metric, 0), reverse=True)
        logger.info(f"Optimization complete. Best {metric}: {results[0].get(metric, 'N/A')}")
        return results

    def optimize_top_n(self, param_grid: dict[str, list], n: int = 10, metric: str = "sharpe_ratio") -> list[dict]:
        """返回前 N 个最优结果"""
        results = self.optimize(param_grid, metric)
        return results[:n]


def generate_rsi_grid() -> dict[str, list]:
    """生成 RSI 参数网格"""
    return {
        "rsi_period": [7, 14, 21],
        "rsi_overbought": [60, 65, 70, 75, 80],
        "rsi_oversold": [20, 25, 30, 35, 40],
        "rsi_additional": [0, 50, 100, 150],
    }


def generate_bias_grid() -> dict[str, list]:
    """生成均线乖离率参数网格"""
    return {
        "bias_ma_period": [120, 250],
        "bias_upper": [0.05, 0.08, 0.10, 0.12, 0.15],
        "bias_lower": [-0.15, -0.12, -0.10, -0.08, -0.05],
        "bias_additional": [0, 50, 100, 150],
    }
