"""
网格搜索优化器 (并行版)

遍历策略参数的笛卡尔积，支持多线程并行执行。
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from itertools import product

from backend.core.logging import get_logger
from backend.backtest.optimizer_base import BaseOptimizer, TrialResult

logger = get_logger("grid_optimizer")


class GridOptimizer(BaseOptimizer):
    """网格搜索优化器 (并行)"""

    def optimize(self) -> list[TrialResult]:
        param_names = [p.name for p in self.tuning_space]
        param_values = [self._expand_values(p) for p in self.tuning_space]
        combos = list(product(*param_values))

        if len(combos) > self.n_trials * 2 and self.n_trials > 0:
            import random
            rng = random.Random(42)
            combos = rng.sample(combos, self.n_trials)
            logger.info(
                f"Grid capped: {len(combos)}/{len(param_values[0]) ** len(param_names) if param_values else 0} "
                f"combinations (n_trials={self.n_trials})"
            )

        logger.info(
            f"Grid search: {self.strategy_name} on {self.stock_code}, "
            f"{len(combos)} combinations, {self.n_jobs} workers"
        )

        results = []
        if self.n_jobs <= 1:
            for i, combo in enumerate(combos):
                params = dict(zip(param_names, combo))
                if not self._check_constraints(params):
                    continue
                tr = self._run_single(params)
                results.append(tr)
                if (i + 1) % 20 == 0:
                    logger.info(f"Grid progress: {i + 1}/{len(combos)}")
        else:
            results = self._run_parallel(combos, param_names)

        logger.info(f"Grid complete: {len(results)} results")
        return self._sort_results(results)

    def _expand_values(self, p) -> list:
        if p.type == "int":
            vals = []
            v = int(p.low)
            step = int(p.step) if p.step else 1
            while v <= int(p.high):
                vals.append(v)
                v += step
            return vals
        elif p.type == "float":
            vals = []
            v = p.low
            step = p.step if p.step else (p.high - p.low) / 10
            while v <= p.high + 1e-9:
                vals.append(v)
                v += step
            return vals
        elif p.type == "categorical":
            return list(p.choices)
        return []

    def _run_parallel(self, combos, param_names) -> list[TrialResult]:
        results = []
        with ThreadPoolExecutor(max_workers=self.n_jobs) as pool:
            futures = {}
            for combo in combos:
                params = dict(zip(param_names, combo))
                if not self._check_constraints(params):
                    continue
                future = pool.submit(self._run_single, params)
                futures[future] = params

            for i, future in enumerate(as_completed(futures)):
                try:
                    tr = future.result()
                    results.append(tr)
                except Exception as e:
                    logger.error(f"Grid worker failed: {futures[future]}: {e}")
                if (i + 1) % 50 == 0:
                    logger.info(f"Grid parallel progress: {i + 1}/{len(futures)}")
        return results

    def _check_constraints(self, params: dict) -> bool:
        for p in self.tuning_space:
            if p.constraints:
                try:
                    val = eval(p.constraints, {"__builtins__": {}}, params)
                    if not val:
                        return False
                except Exception:
                    pass
        return True
