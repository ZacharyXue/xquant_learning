"""
Optuna 贝叶斯优化器

使用 TPE (Tree-structured Parzen Estimator) 采样器进行高效超参数搜索。
支持参数约束和早停。
"""

from backend.core.logging import get_logger
from backend.backtest.optimizer_base import BaseOptimizer, TrialResult

logger = get_logger("optuna_optimizer")


class OptunaOptimizer(BaseOptimizer):
    """基于 Optuna TPE 的贝叶斯优化器"""

    def __init__(self, *args, seed: int = 42, **kwargs):
        super().__init__(*args, **kwargs)
        self._seed = seed

    def optimize(self) -> list[TrialResult]:
        import optuna

        study = optuna.create_study(
            direction="maximize",
            sampler=optuna.samplers.TPESampler(seed=self._seed),
            pruner=optuna.pruners.MedianPruner(n_startup_trials=5),
        )

        study.optimize(
            self._objective,
            n_trials=self.n_trials,
            n_jobs=self.n_jobs,
            catch=(Exception,),
        )

        results = []
        for trial in study.trials:
            if trial.state == optuna.trial.TrialState.COMPLETE:
                results.append(TrialResult(
                    params=trial.params,
                    metric_value=trial.value or 0.0,
                    metrics=trial.user_attrs.get("metrics", {}),
                ))

        if not results:
            logger.warning("No completed trials from Optuna study")

        logger.info(
            f"Optuna complete: {len(results)}/{self.n_trials} trials, "
            f"best {self.metric}={study.best_value:.4f}"
        )
        return self._sort_results(results)

    def _objective(self, trial) -> float:
        params = {}
        for p in self.tuning_space:
            if p.type == "int":
                params[p.name] = trial.suggest_int(
                    p.name, int(p.low), int(p.high),
                    step=int(p.step) if p.step else None,
                )
            elif p.type == "float":
                params[p.name] = trial.suggest_float(
                    p.name, p.low, p.high,
                    log=p.log_scale,
                )
            elif p.type == "categorical":
                params[p.name] = trial.suggest_categorical(
                    p.name, p.choices,
                )

        if not self._check_constraints(params):
            raise optuna.TrialPruned()

        tr = self._run_single(params)
        trial.set_user_attr("metrics", tr.metrics)
        return tr.metric_value

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
