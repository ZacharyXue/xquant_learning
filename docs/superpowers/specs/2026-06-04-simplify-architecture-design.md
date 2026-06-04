# 架构精简设计

## 背景

当前代码库（~100 文件、FastAPI + gRPC + React + PostgreSQL + 3 种优化器 + WalkForward）在只有 1 个策略、未验证实盘时过早构建了企业级基础设施。核心链路 `QuotePump → Strategy → Signal → Executor` 是正确的，需要保留。其余外围设施删除，用最简单方式重建。

## 目标

- 回测、模拟交易、实盘交易三种模式共享同一套策略类
- 纯 CLI/脚本操作，无 Web UI
- SQLite 单文件持久化，查询接口简洁（返回 `list[dict]`）
- 回测支持网格搜索优化，输出夏普比/最大回撤/可选基准对比
- 5-10 个策略可管理
- AI 编程助手通过 `docs/API_REFERENCE.md` 了解所有可用接口

## 目录结构

```
xtquant_learning/
├── engine/
│   ├── strategy_base.py       # Quote, Signal, StrategyBase(ABC)
│   ├── strategy_registry.py   # @register 装饰器
│   ├── indicators.py          # MA / EMA / RSI / MACD / 布林带
│   └── risk.py                # RiskManager（仓位 / 现金 / 频次约束）
│
├── trade/
│   ├── quote_pump.py          # xtdata 订阅 → asyncio.Queue → Quote
│   ├── sim_executor.py        # 虚拟账户，当前价成交 + 完整费率
│   ├── real_executor.py       # 真实 QMT 下单（仅 Windows，封装 xtquant）
│   ├── fees.py                # FeeCalculator（佣金 / 印花税 / 过户费 / 滑点）
│   └── broker.py              # Signal → 风控 → 执行 → 入库
│
├── backtest/
│   ├── engine.py              # 事件驱动日线循环
│   ├── data_provider.py       # xtdata → akshare → 本地 parquet 缓存
│   ├── metrics.py             # 夏普比 / 最大回撤 / 年化收益 / 胜率 / 权益曲线
│   ├── optimizer.py           # 网格搜索（tqdm 进度条）
│   └── baseline.py            # 基准对比 DCA / Buy&Hold（可选）
│
├── db/
│   ├── database.py            # SQLite 连接管理
│   ├── schema.py              # 建表 DDL
│   └── queries.py             # 查询函数接口
│
├── strategies/                # 每个策略一个文件
│   ├── bonus_stocks.py
│   └── buy_on_dips.py
│
├── scripts/                   # CLI 入口脚本
│   ├── manage.py              # 策略开关 / 参数配置（唯一配置入口）
│   ├── run_backtest.py        # 回测 + 网格搜索
│   ├── run_sim.py             # 模拟交易
│   ├── run_real.py            # 实盘交易（需 QMT）
│   └── show_trades.py         # 交易记录查询
│
├── config.yaml                # 全局配置（费率 / 路径 / 风控参数 / QMT 路径）
├── data/                      # SQLite 文件 + kline 缓存
└── docs/
    ├── API_REFERENCE.md       # 所有 CLI 命令和 Python 函数接口文档
    └── ...
```

## 核心抽象（3 个数据类，1 个基类）

```python
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
from typing import Optional
from datetime import datetime

@dataclass
class Quote:
    stock_code: str
    last_price: float
    open: float
    high: float
    low: float
    last_close: float
    volume: int
    amount: float
    time: datetime

@dataclass
class Signal:
    stock_code: str
    side: str          # "buy" | "sell" | "skip"
    volume: int
    price: float
    reason: str
    indicators: dict   # {rsi: 45.2, ma_250: 3.15, ...}

class StrategyBase(ABC):
    """策略基类 — 回测和实盘共用同一套 on_quote 逻辑"""
    name: str = ""
    display_name: str = ""
    description: str = ""
    watched_stocks: list[str] = []

    @abstractmethod
    def on_quote(self, quote: Quote) -> Optional[Signal]:
        """接收行情，返回交易信号。回测和实盘都会调用这个方法。"""
        ...

    def get_config_schema(self) -> dict:
        """返回 JSON Schema，供 UI/CLI 展示和校验参数"""
        return {"type": "object", "properties": {}}

    def get_tuning_space(self) -> list[dict]:
        """返回网格搜索参数空间 [{name, type, min, max, step}, ...]"""
        return []

    def update_params(self, params: dict) -> None:
        """运行时更新参数"""
        for k, v in params.items():
            if hasattr(self, k):
                setattr(self, k, v)
```

## 数据库设计（4 张表，SQLite）

### strategies

```sql
CREATE TABLE strategies (
    name         TEXT PRIMARY KEY,
    display_name TEXT,
    enabled      INTEGER DEFAULT 1,
    config       TEXT,       -- JSON 参数
    created_at   TEXT DEFAULT (datetime('now','localtime'))
);
```

### trade_records

```sql
CREATE TABLE trade_records (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    strategy     TEXT NOT NULL,
    mode         TEXT NOT NULL,      -- "backtest" | "sim" | "real"
    stock_code   TEXT NOT NULL,
    side         TEXT NOT NULL,      -- "buy" | "sell"
    volume       INTEGER NOT NULL,
    price        REAL NOT NULL,
    commission   REAL DEFAULT 0,
    stamp_tax    REAL DEFAULT 0,
    transfer_fee REAL DEFAULT 0,
    slippage     REAL DEFAULT 0,
    total_cost   REAL DEFAULT 0,
    reason       TEXT,
    indicators   TEXT,               -- JSON
    trade_time   TEXT NOT NULL,
    created_at   TEXT DEFAULT (datetime('now','localtime'))
);
CREATE INDEX idx_trade_strategy ON trade_records(strategy, mode);
CREATE INDEX idx_trade_time ON trade_records(trade_time);
```

### backtest_runs

```sql
CREATE TABLE backtest_runs (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id         TEXT UNIQUE NOT NULL,
    strategy       TEXT NOT NULL,
    start_date     TEXT NOT NULL,
    end_date       TEXT NOT NULL,
    params         TEXT,             -- JSON
    initial_cash   REAL,
    final_equity   REAL,
    total_return   REAL,
    annual_return  REAL,
    max_drawdown   REAL,
    sharpe_ratio   REAL,
    win_rate       REAL,
    total_trades   INTEGER,
    equity_curve   TEXT,             -- JSON: [[date_str, equity], ...]
    baseline_curve TEXT,             -- JSON (optional, 仅当启用基准对比时)
    created_at     TEXT DEFAULT (datetime('now','localtime'))
);
```

### account_snapshots / positions（模拟和实盘用）

```sql
CREATE TABLE account_snapshots (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    mode          TEXT NOT NULL,      -- "sim" | "real"
    total_asset   REAL,
    available_cash REAL,
    market_value  REAL,
    frozen_cash   REAL,
    snapshot_time TEXT NOT NULL
);

CREATE TABLE positions (
    stock_code   TEXT NOT NULL,
    mode         TEXT NOT NULL,
    volume       INTEGER,
    avg_cost     REAL,
    market_value REAL,
    profit_loss  REAL,
    updated_at   TEXT
);
```

## 数据流

```
watched_stocks = union(所有启用策略.watched_stocks)
        │
        ├─── 回测模式 ────────────────────────┐
        │   DataProvider.iter(daily klines)    │
        │   → 逐日构造 Quote                   │
        │   → strategy.on_quote(quote)         │
        │   → 记录 TradeRecord + 更新持仓      │
        │   → 计算 metrics                     │
        │                                      │
        ├─── 模拟/实盘模式 ────────────────────┤
        │   QuotePump.subscribe(watched)       │
        │   → tick callback → Quote            │
        │   → strategy.on_quote(quote)         │
        │   → Signal → RiskManager.check()     │
        │   → Executor.place_order()           │
        │   → 记录到 SQLite                    │
        │                                      │
        ▼                                      ▼
              SQLite (trade_records / backtest_runs)
```

## CLI 命令设计

### `manage.py` — 策略管理（唯一配置入口）

```
python scripts/manage.py --list                     列出所有策略及启用状态
python scripts/manage.py --init                     首次使用：扫描 strategies/ 自动注册
python scripts/manage.py --enable bonus_stocks       启用策略
python scripts/manage.py --disable buy_on_dips      停用策略
python scripts/manage.py --show bonus_stocks         查看策略参数
python scripts/manage.py --set bonus_stocks --param rsi_period=14 --param amount=5000  设置参数
```

### `run_backtest.py` — 回测

```
python scripts/run_backtest.py --strategy bonus_stocks --start 2020-01-01 --end 2024-12-31 --initial-cash 100000
python scripts/run_backtest.py --strategy bonus_stocks --start 2020-01-01 --end 2024-12-31 --optimize --target max_sharpe
    --target 可选: max_sharpe | min_drawdown | max_return
python scripts/run_backtest.py --list               历史回测列表
python scripts/run_backtest.py --show <run_id>      某次回测详情（含权益曲线）
```

**输出示例：**
```
══════════════════════════════════════════════
  回测报告: 红利ETF定投 (bonus_stocks)
══════════════════════════════════════════════
  区间: 2020-01-01 → 2024-12-31 (1826 个交易日)
  初始资金: ¥100,000
  最终权益: ¥135,420 (+35.42%)
  年化收益: +6.27%
  最大回撤: -15.3%
  夏普比率: 0.82
  胜率: 68.5% (146/213 笔)
  总交易次数: 213
  费用合计: ¥1,234 (佣金 ¥890 + 印花税 ¥210 + 过户费 ¥34 + 滑点 ¥100)
══════════════════════════════════════════════
```

### `run_sim.py` — 模拟交易

```
python scripts/run_sim.py                          默认：所有启用策略
python scripts/run_sim.py --strategy bonus_stocks   仅指定策略
python scripts/run_sim.py --initial-cash 100000 --duration 30
```

### `run_real.py` — 实盘交易（需 QMT 运行中）

```
python scripts/run_real.py                          默认：所有启用策略
python scripts/run_real.py --strategy bonus_stocks   仅指定策略
```

### `show_trades.py` — 交易记录查询

```
python scripts/show_trades.py                                      最近 100 笔
python scripts/show_trades.py --strategy bonus_stocks               按策略筛选
python scripts/show_trades.py --mode sim                            按模式筛选
python scripts/show_trades.py --start 2024-01-01                    按日期筛选
python scripts/show_trades.py --today                               今日交易
python scripts/show_trades.py --strategy bonus_stocks --mode sim --limit 50  组合筛选
```

## 查询接口（db/queries.py）

所有函数返回 `list[dict]`，可直接喂给 `pandas.DataFrame` 或直接打印。

```python
# 策略
list_strategies() -> list[dict]
get_strategy(name: str) -> dict | None
enable_strategy(name: str, enabled: bool) -> None
update_strategy_config(name: str, config: dict) -> None
register_strategy(name: str, display_name: str, config: dict = {}) -> None

# 交易记录
get_trades(
    strategy: str = None, mode: str = None,
    start: str = None, end: str = None,
    stock_code: str = None, limit: int = 100
) -> list[dict]

get_today_trades() -> list[dict]

insert_trade(
    strategy: str, mode: str, stock_code: str, side: str,
    volume: int, price: float, reason: str,
    commission: float = 0, stamp_tax: float = 0,
    transfer_fee: float = 0, slippage: float = 0,
    total_cost: float = 0, indicators: dict = None,
    trade_time: str = None
) -> int

# 回测
get_backtest_runs(strategy: str = None, limit: int = 20) -> list[dict]
get_backtest_run(run_id: str) -> dict | None
insert_backtest_run(data: dict) -> str   # 返回 run_id
```

## 回测引擎

- **事件驱动日线循环**：逐日从 `DataProvider` 获取 K 线 DataFrame，按日遍历，构造 `Quote` 对象，调用 `strategy.on_quote(quote)`，处理 `Signal`，记录交易，更新持仓和现金
- **网格搜索**：读取 `strategy.get_tuning_space()`，生成参数组合（笛卡尔积），对每组参数执行回测，按 `--target` 排序输出 Top 10
- **基准对比**（可选）：当策略定义了 `get_baseline_config()` 时，同时运行 DCA/Buy&Hold 基准并输出对比
- **时间区间**：通过 `--start` / `--end` 指定

## 费率模型

与当前保持一致：

| 费用项 | 费率 | 说明 |
|--------|------|------|
| 佣金 | 0.025%（万 2.5） | 最低 5 元 |
| 印花税 | 0.1%（千 1） | 仅卖出 |
| 过户费 | 0.002%（万 0.2） | |
| 滑点 | 0.1%（千 1） | 买入上浮、卖出下浮 |

通过 `config.yaml` 全局配置，`FeeCalculator` 统一计算。

## 策略注册流程

1. 开发者在 `strategies/` 下创建新文件，继承 `StrategyBase`，加 `@register` 装饰器
2. 运行 `python scripts/manage.py --init` 或首次启动时自动扫描 `strategies/` 目录，将策略注册到 SQLite
3. 通过 `manage.py --enable/--disable` 控制策略是否参与交易
4. 回测、模拟、实盘都从 `enabled` 策略中读取 `watched_stocks` 构建标的池

## Python 依赖

```
numpy
pandas
pyyaml
xtquant           # QMT 本地安装
akshare           # 回退数据源（跨平台时）
tqdm              # 网格搜索进度条
```

（SQLite 为 Python 标准库，无需额外安装）

## AI 编程助手规范

`AGENTS.md` 中新增：

> **接口文档**：AI 在执行交易、回测、数据查询时，**必须先阅读** `docs/API_REFERENCE.md`。禁止臆造不存在的命令或函数。
> 接口变更后**必须同步更新** `docs/API_REFERENCE.md`。

`docs/API_REFERENCE.md` 包含：
- 所有 CLI 命令的完整参数说明和示例
- 所有 `db/queries.py` 函数的签名和返回格式
- 策略开发指南（`StrategyBase` / `@register` / `get_config_schema` / `get_tuning_space`）
- 回测引擎、交易执行模块的 Python API

## 与旧代码的关系

旧代码（`backend/`、`src/`、`frontend/`、`docker/`）在迁移完成后删除。迁移期间，新代码单独跑通后再切换到新结构。
