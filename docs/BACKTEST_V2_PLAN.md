# 回测引擎 V2 开发计划

> 基于 [Qbot 差距分析](./QBOT_GAP_ANALYSIS.md) 和 2026-05-25 讨论确认的设计决策。

---

## 设计决策确认

| # | 问题 | 决策 |
|---|------|------|
| A | 基准行为由谁定义 | **A3**: 策略声明 `strategy_type`，引擎按类型执行内置基线 |
| B | DCA 基准买什么 | 同一标的（策略买 510880，基准也定投 510880） |
| C | DCA 收益率计算 | **双报告**: XIRR（资金加权）+ simple_return（简单收益） |
| D | 优化参数空间定义 | **D3 混合**: schema 定义 UI 用 min/max，新增 `get_tuning_space()` 定义优化器用搜索空间 |
| E | 优化方法优先级 | Optuna/TPE → 网格搜索 → 随机搜索 → 遗传算法 |
| F | 验证策略 | Walk-Forward 滚动验证 |
| G | 文件缓存目录 | `data/cache/klines/` |

---

## 总体架构变更

```
变更前 (V1):
  BacktestEngine.run()
    ├── 基准逻辑硬编码在引擎中 (固定股数, 读策略参数)
    ├── 仅日线支持
    ├── 简单收益率 (final_value / initial_capital - 1)
    ├── 串行网格搜索
    └── 数据内存缓存

变更后 (V2):
  BacktestEngine.run()
    ├── 基准行为由 strategy_type 声明, BaselineEngine 独立实现
    ├── 双收益率 (XIRR + simple + return_on_deployed)
    └── 数据文件缓存 (data/cache/klines/)

  TuningOrchestrator                       ← 新增
    ├── OptunaOptimizer (TPE)
    ├── GridOptimizer (并行化)
    ├── RandomOptimizer
    └── GeneticOptimizer (后期)

  WalkForwardValidator                     ← 新增
    └── 滚动窗口训练/验证/评估
```

---

## Phase 1: 基准/基线系统重构 (6-8h)

### 1.1 StrategyBase 改造

**文件**: `backend/engine/strategy_base.py`

新增类属性 `strategy_type` 和方法 `get_baseline_config()`、`get_tuning_space()`：

```python
class StrategyBase(ABC):
    name: str = "base"
    display_name: str = "基础策略"
    strategy_type: str = "dca"          # "dca" | "buy_hold" | "momentum" | "custom"

    def get_baseline_config(self) -> dict:
        """返回基准行为配置 (策略可覆盖)

        不同 strategy_type 有不同的默认实现。
        """
        return {
            "type": "self_benchmark",
            "index_code": "",
        }
```

`strategy_type` 枚举:

| 值 | 策略性质 | 基准行为 |
|----|---------|---------|
| `dca` | 定投类 | 固定金额同标的定投 |
| `buy_hold` | 买入持有 | 同期买入持有(一次全仓) |
| `momentum` | 动量轮动 | 等权买入持有组合 |
| `custom` | 自定义 | 策略实现 `get_baseline()` |

### 1.2 BonusStocksStrategy 适配

**文件**: `src/strategies/bonus_stocks.py`

- 设置 `strategy_type = "dca"`
- 新增 `get_baseline_config()` 返回定投基准参数
- 新增 `get_tuning_space()` 返回参数优化空间

### 1.3 BaselineEngine 实现

**文件**: `backend/backtest/baseline.py` (新建)

三种内置基准:

| 方法 | 行为 |
|------|------|
| `_run_dca()` | 每个定投日买入固定**金额**（修复当前固定股数 bug），记录现金流用于 XIRR |
| `_run_buy_hold()` | 首日全仓买入，期末卖出（含卖出费用） |
| `_run_index()` | 买入持有目标市场指数 |

DCA 基准关键修复: 当前 `engine.py:178` 是 `round_to_lot(bench_base_volume)` (固定**股数**)，应改为 `int(base_amount / close / lot_size) * lot_size` (固定**金额**)。

### 1.4 BacktestEngine 适配

**文件**: `backend/backtest/engine.py`

- 移除内嵌的 `bench_cash` / `bench_position` 逻辑
- `run()` 中读取 `strategy.strategy_type` → 调用 `BaselineEngine.run()`

### 1.5 XIRR 计算与指标修正

**文件**: `backend/backtest/metrics.py`

- 新增 `calc_xirr(cash_flows)` — Newton-Raphson 法计算资金加权年化收益率
- 新增 `return_on_deployed` — 仅计算已投入资金的收益
- DCA 模式 Sharpe 使用已投资部分日收益（而非含现金的 portfolio 收益）

### 1.6 API 模型更新

**文件**: `backend/api/models.py`

`BacktestResultOut` 新增字段:
- `total_return: float` (DB已有, API从未暴露)
- `volatility: float` (DB已有, API从未暴露)
- `xirr: float`
- `return_on_deployed: float`

---

## Phase 2: 超参数优化框架 (8-10h)

### 2.1 TuneParam 与 get_tuning_space()

**文件**: `backend/engine/strategy_base.py`

```python
@dataclass
class TuneParam:
    name: str
    type: str          # "int" | "float" | "categorical"
    low: float = 0.0
    high: float = 1.0
    step: float = None
    choices: list = None
    log_scale: bool = False
    constraints: str = ""
```

默认从 `get_config_schema()` 的 `minimum`/`maximum`/`type` 自动推导。策略可覆盖定制。

### 2.2 优化器基类

**文件**: `backend/backtest/optimizer_base.py` (新建)

```python
@dataclass
class TrialResult:
    params: dict
    metric_value: float
    metrics: dict

class BaseOptimizer(ABC):
    def __init__(self, strategy_name, stock_code, start_date, end_date,
                 tuning_space, metric="sharpe_ratio", n_trials=100, n_jobs=1): ...
    @abstractmethod
    def optimize(self) -> list[TrialResult]: ...
```

### 2.3 具体优化器

| 优化器 | 文件 |
|--------|------|
| `OptunaOptimizer` (TPE) | `backend/backtest/optimizers/optuna_optimizer.py` |
| `GridOptimizer` (并行化重构) | `backend/backtest/optimizers/grid_optimizer.py` |
| `RandomOptimizer` | `backend/backtest/optimizers/random_optimizer.py` |
| `GeneticOptimizer` | `backend/backtest/optimizers/genetic_optimizer.py` |

### 2.4 Walk-Forward 验证

**文件**: `backend/backtest/walkforward.py` (新建)

- 滚动窗口: train=3y, test=1y
- 输出: 每窗口 train/test 指标, `stability_score`, `overfit_ratio`

### 2.5 API

```
POST /api/backtest/optimize/advanced
{
    "strategy_name": "bonus_stocks", "stock_code": "510880.SH",
    "start_date": "20190101", "end_date": "20241231",
    "method": "optuna",          // optuna | grid | random
    "metric": "sharpe_ratio", "n_trials": 100,
    "validation": "walkforward", // none | walkforward
    "walkforward_train_years": 3,
    "walkforward_test_years": 1
}
```

---

## Phase 3: 数据文件缓存 (2-3h)

### 3.1 KLineCache

**文件**: `backend/backtest/data_provider.py` (修改)

- 缓存路径: `data/cache/klines/{code}_{start}_{end}_{period}.parquet`
- TTL: 1 天 (可配置)
- 清理: 自动删 7 天以上文件

### 3.2 DataProvider 获取流水

```
内存缓存 → 文件缓存(.parquet) → xtquant → akshare → synthetic
```

---

## Phase 4: 回测报告数据增强 (4-5h)

### 4.1 引擎输出新增

| 数据 | 用途 |
|------|------|
| `trades: [...]` | 交易明细(日期/价格/量/费用/现金流/持仓变化) |
| `drawdown_curve: [{date, drawdown}]` | 水下曲线图 |
| `monthly_returns: [{year, month, return}]` | 月度收益热力图 |

### 4.2 DB 模型

- `backtest_trades` 表: 交易明细(归一化)
- `BacktestResult` 新增列: `xirr`, `return_on_deployed`, `drawdown_curve`, `monthly_returns`

### 4.3 新增依赖

```txt
optuna>=3.5
```

---

## 验收标准

| Phase | 验收方式 |
|-------|---------|
| Phase 1 | 回测返回 xirr/return_on_deployed/total_return; 基准为固定**金额**定投 |
| Phase 2 | optimize/advanced 支持 optuna+walkforward; 返回 stability_score |
| Phase 3 | 二次回测 "file cache hit"; data/cache/klines/ 有 parquet |
| Phase 4 | 结果含 trades/drawdown_curve/monthly_returns; 前端展示回撤图 |

| Phase | 工时 | 风险 |
|-------|------|------|
| 1 | 6-8h | 低 |
| 2 | 8-10h | 中 (Optuna 依赖, Walk-Forward 窗口) |
| 3 | 2-3h | 低 |
| 4 | 4-5h | 低 |
| **合计** | **20-26h** | |
