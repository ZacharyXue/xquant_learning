"""Grid search parameter optimizer"""
from itertools import product
from backtest.engine import BacktestEngine

class GridOptimizer:
    def __init__(self, strategy_name, stock_code, start_date, end_date, initial_capital=100000.0):
        self._sn = strategy_name; self._sc = stock_code
        self._sd = start_date; self._ed = end_date; self._cap = initial_capital
        self._engine = BacktestEngine()

    def optimize(self, param_grid: dict[str, list], metric="sharpe_ratio", save_to_db=False) -> list[dict]:
        names = list(param_grid.keys()); vals = list(param_grid.values())
        combos = list(product(*vals))
        _strip = {"equity_curve", "trades", "run_id"}
        results = []
        for combo in combos:
            params = dict(zip(names, combo))
            r = self._engine.run(self._sn, self._sc, self._sd, self._ed, params=params, initial_capital=self._cap, save_to_db=save_to_db)
            if "error" in r: continue
            entry = {"params": params}
            entry.update({k: v for k, v in r.items() if k not in _strip})
            results.append(entry)
        results.sort(key=lambda r: r.get(metric, -float("inf")), reverse=True)
        return results

    def top_n(self, param_grid, n=10, metric="sharpe_ratio"):
        return self.optimize(param_grid, metric=metric)[:n]
