"""
随机搜索优化器

在高维参数空间中随机采样，比网格搜索更适合高维场景。
"""

import random
from concurrent.futures import ThreadPoolExecutor, as_completed

from backend.core.logging import get_logger
from backend.backtest.optimizer_base import BaseOptimizer, TrialResult

logger = get_logger("random_optimizer")


class RandomOptimizer(BaseOptimizer):
    """随机搜索优化器"""

    def __init__(self, *args, seed: int = 42, **kwargs):
        super().__init__(*args, **kwargs)
        self._seed = seed

    def optimize(self) -> list[TrialResult]:
        rng = random.Random(self._seed)

        logger.info(
            f"Random search: {self.strategy_name} on {self.stock_code}, "
            f"{self.n_trials} trials, {self.n_jobs} workers"
        )

        param_sets = []
        for _ in range(self.n_trials):
            params = {}
            for p in self.tuning_space:
                params[p.name] = self._sample(p, rng)
            if self._check_constraints(params):
                param_sets.append(params)

        logger.info(f"Generated {len(param_sets)} valid param sets from {self.n_trials} attempts")

        results = []
        if self.n_jobs <= 1:
            for i, params in enumerate(param_sets):
                tr = self._run_single(params)
                results.append(tr)
                if (i + 1) % 20 == 0:
                    logger.info(f"Random progress: {i + 1}/{len(param_sets)}")
        else:
            with ThreadPoolExecutor(max_workers=self.n_jobs) as pool:
                futures = {pool.submit(self._run_single, p): p for p in param_sets}
                for i, future in enumerate(as_completed(futures)):
                    try:
                        tr = future.result()
                        results.append(tr)
                    except Exception as e:
                        logger.error(f"Random worker failed: {e}")
                    if (i + 1) % 50 == 0:
                        logger.info(f"Random parallel progress: {i + 1}/{len(futures)}")

        logger.info(f"Random complete: {len(results)} results")
        return self._sort_results(results)

    def _sample(self, p, rng) -> float:
        if p.type == "int":
            low = int(p.low)
            high = int(p.high)
            val = rng.randint(low, high)
            if p.step and p.step > 0:
                step = int(p.step)
                val = low + ((val - low) // step) * step
            return val
        elif p.type == "float":
            if p.log_scale:
                return rng.uniform(p.low, p.high)
            return rng.uniform(p.low, p.high)
        elif p.type == "categorical":
            return rng.choice(p.choices)
        return 0

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
