# 架构精简 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将当前 ~100 文件的企业级框架精简为 15-20 个文件的纯 CLI 量化系统，覆盖回测、模拟交易、实盘交易三种模式。

**Architecture:** 同步策略基类 `StrategyBase.on_quote(Quote) -> Signal`，回测引擎逐日遍历 K 线调用策略，模拟/实盘通过 QuotePump 获取实时行情后调用同一套策略。SQLite 单文件持久化，5 个 CLI 脚本作为入口。

**Tech Stack:** Python 3.11 + numpy + pandas + pyyaml + tqdm + sqlite3(stdlib) + xtquant(仅 Windows 实盘)

**Spec:** `docs/superpowers/specs/2026-06-04-simplify-architecture-design.md`

**Implementation order:** Foundation -> Backtest -> Trading -> Strategies -> CLI -> Docs

---

## Phase 1: Foundation

### Task 1: Project skeleton + config.yaml + requirements.txt

**Files:** Create `config.yaml`, `requirements.txt`, `data/.gitkeep`, `__init__.py` files in `engine/`, `trade/`, `backtest/`, `db/`, `strategies/`, `scripts/`

- [ ] **Step 1: Create directory structure**

```bash
mkdir -p engine trade backtest db strategies scripts data
touch data/.gitkeep
touch engine/__init__.py trade/__init__.py backtest/__init__.py db/__init__.py strategies/__init__.py scripts/__init__.py
```

- [ ] **Step 2: Create config.yaml**

```yaml
# xtquant quant trading system config
database:
  path: "data/xtquant.db"

trade:
  mode: sim                       # sim | real
  qmt_path: ""
  account_id: ""
  max_position_per_stock: 10000
  sim_initial_capital: 100000.0

fee:
  commission_rate: 0.00025       # 0.025%
  stamp_tax_rate: 0.001          # 0.1% (sell only)
  transfer_fee_rate: 0.00002     # 0.002%
  min_commission: 5.0

slippage:
  rate: 0.001                    # 0.1%

trading_hours:
  start: "09:30"
  end: "14:55"

backtest:
  cache_dir: "data/cache/klines"
  cache_ttl: 86400
```

- [ ] **Step 3: Create requirements.txt**

```
numpy>=2.0.0
pandas>=2.2.0
pyyaml>=6.0.0
tqdm>=4.0.0
pytest>=9.0.0
```

- [ ] **Step 4: Commit**

```bash
git add config.yaml requirements.txt data/.gitkeep engine/__init__.py trade/__init__.py backtest/__init__.py db/__init__.py strategies/__init__.py scripts/__init__.py
git commit -m "feat: create project skeleton with config.yaml"
```

---

### Task 2: Core abstractions (Quote, Signal, StrategyBase)

**Files:** Create `engine/strategy_base.py`, Create `tests/test_strategy_base.py`

- [ ] **Step 1: Write test file `tests/test_strategy_base.py`**

```python
import pytest
from datetime import datetime
from engine.strategy_base import Quote, Signal, StrategyBase


class TestQuote:
    def test_create_quote(self):
        q = Quote(stock_code="510880.SH", last_price=3.45, open=3.40, high=3.50,
                  low=3.38, last_close=3.42, volume=1000000, amount=3450000.0,
                  time=datetime(2024, 1, 15, 10, 30))
        assert q.stock_code == "510880.SH"
        assert q.last_price == 3.45

    def test_defaults(self):
        q = Quote(stock_code="000001.SZ", last_price=10.0)
        assert q.open == 0.0
        assert q.volume == 0


class TestSignal:
    def test_buy_signal(self):
        s = Signal(stock_code="510880.SH", side="buy", volume=500, price=3.45,
                   reason="RSI oversold", indicators={"rsi": 25.5})
        assert s.side == "buy"
        assert s.indicators["rsi"] == 25.5

    def test_defaults(self):
        s = Signal(stock_code="510880.SH", side="skip", volume=0, price=0.0)
        assert s.reason == ""
        assert s.indicators == {}


class TestStrategyBase:
    def test_subclass_must_implement_on_quote(self):
        class Bad(StrategyBase):
            name = "bad"
        with pytest.raises(TypeError):
            Bad()

    def test_valid_subclass(self):
        class Good(StrategyBase):
            name = "good"
            display_name = "Good"
            def on_quote(self, quote):
                return None
        instance = Good()
        assert instance.name == "good"
        assert instance.watched_stocks == []

    def test_update_params(self):
        class MyStrat(StrategyBase):
            name = "test"
            rsi_period = 14
            def on_quote(self, quote):
                return None
        s = MyStrat()
        s.update_params({"rsi_period": 21})
        assert s.rsi_period == 21

    def test_get_config_schema_default(self):
        class MyStrat(StrategyBase):
            name = "test"
            def on_quote(self, quote):
                return None
        s = MyStrat()
        assert s.get_config_schema() == {"type": "object", "properties": {}}

    def test_get_tuning_space_default(self):
        class MyStrat(StrategyBase):
            name = "test"
            def on_quote(self, quote):
                return None
        s = MyStrat()
        assert s.get_tuning_space() == []
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /mnt/f/Codes/xtquant_learning && .venv/Scripts/python.exe -m pytest tests/test_strategy_base.py -v
# Expected: ModuleNotFoundError
```

- [ ] **Step 3: Implement `engine/strategy_base.py`**

```python
"""Strategy base classes: Quote, Signal, StrategyBase"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Quote:
    stock_code: str
    last_price: float
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    last_close: float = 0.0
    volume: int = 0
    amount: float = 0.0
    time: datetime = field(default_factory=datetime.now)


@dataclass
class Signal:
    stock_code: str
    side: str          # "buy" | "sell" | "skip"
    volume: int = 0
    price: float = 0.0
    reason: str = ""
    indicators: dict = field(default_factory=dict)


class StrategyBase(ABC):
    """Base strategy class.

    Subclasses must define `name` and implement `on_quote()`.
    Both backtest and live trading share the same on_quote method.
    """

    name: str = ""
    display_name: str = ""
    description: str = ""
    watched_stocks: list[str] = []

    def __init__(self, config: dict = None):
        self._config = config or {}
        for k, v in self._config.items():
            if hasattr(self, k):
                setattr(self, k, v)

    @abstractmethod
    def on_quote(self, quote: Quote) -> Optional[Signal]:
        """Receive market data, return a trading signal or None."""
        ...

    def get_config_schema(self) -> dict:
        return {"type": "object", "properties": {}}

    def get_tuning_space(self) -> list[dict]:
        return []

    def update_params(self, params: dict) -> None:
        for k, v in params.items():
            if hasattr(self, k):
                setattr(self, k, v)
```

- [ ] **Step 4: Run tests to verify pass**

```bash
cd /mnt/f/Codes/xtquant_learning && .venv/Scripts/python.exe -m pytest tests/test_strategy_base.py -v
# Expected: 6 passed
```

- [ ] **Step 5: Commit**

```bash
git add engine/strategy_base.py tests/test_strategy_base.py
git commit -m "feat: add Quote, Signal, StrategyBase core abstractions"
```

---

### Task 3: Strategy registry

**Files:** Create `engine/strategy_registry.py`, Create `tests/test_strategy_registry.py`

- [ ] **Step 1: Write test `tests/test_strategy_registry.py`**

```python
import pytest
from engine.strategy_base import StrategyBase, Quote
from engine.strategy_registry import register, get, list_all, create, clear


@pytest.fixture(autouse=True)
def clean():
    clear()
    yield
    clear()


class TestRegister:
    def test_register_strategy(self):
        @register
        class MyStrat(StrategyBase):
            name = "my_test"
            display_name = "My Test"
            def on_quote(self, quote):
                return None
        assert get("my_test") is MyStrat
        assert "my_test" in list_all()

    def test_missing_name_raises(self):
        with pytest.raises(ValueError, match="must have a 'name'"):
            @register
            class Bad(StrategyBase):
                def on_quote(self, quote):
                    return None

    def test_create_strategy(self):
        @register
        class S(StrategyBase):
            name = "s1"
            def on_quote(self, q):
                return None
        instance = create("s1", {"display_name": "Override"})
        assert isinstance(instance, S)
        assert instance.name == "s1"

    def test_create_nonexistent(self):
        with pytest.raises(ValueError, match="not found"):
            create("nope", {})

    def test_list_all(self):
        @register
        class S1(StrategyBase):
            name = "a"
            def on_quote(self, q):
                return None
        @register
        class S2(StrategyBase):
            name = "b"
            def on_quote(self, q):
                return None
        assert set(list_all()) == {"a", "b"}
```

- [ ] **Step 2: Run test to verify fail**

```bash
cd /mnt/f/Codes/xtquant_learning && .venv/Scripts/python.exe -m pytest tests/test_strategy_registry.py -v
```

- [ ] **Step 3: Implement `engine/strategy_registry.py`**

```python
"""Strategy registry with @register decorator"""

from engine.strategy_base import StrategyBase

_registry: dict[str, type[StrategyBase]] = {}


def register(cls):
    if not cls.name:
        raise ValueError(f"Strategy class {cls.__name__} must have a 'name'")
    if cls.name in _registry:
        raise ValueError(f"Strategy '{cls.name}' already registered")
    _registry[cls.name] = cls
    return cls


def get(name: str) -> type[StrategyBase] | None:
    return _registry.get(name)


def list_all() -> list[str]:
    return list(_registry.keys())


def create(name: str, config: dict = None) -> StrategyBase:
    cls = get(name)
    if cls is None:
        raise ValueError(f"Strategy '{name}' not found. Available: {list_all()}")
    return cls(config=config)


def clear():
    _registry.clear()
```

- [ ] **Step 4: Run tests**

```bash
cd /mnt/f/Codes/xtquant_learning && .venv/Scripts/python.exe -m pytest tests/test_strategy_registry.py -v
# Expected: 5 passed
```

- [ ] **Step 5: Commit**

```bash
git add engine/strategy_registry.py tests/test_strategy_registry.py
git commit -m "feat: add strategy registry with @register decorator"
```

---

### Task 4: Technical indicators

**Files:** Create `engine/indicators.py`, Create `tests/test_indicators.py`

- [ ] **Step 1: Write test `tests/test_indicators.py`**

```python
from engine.indicators import calc_rsi, calc_ma, calc_ema, calc_bias, calc_open_change, round_to_lot


class TestRSI:
    def test_rsi_basic(self):
        prices = [10.0, 10.5, 10.3, 10.8, 10.6, 10.9, 11.0, 10.7,
                  11.2, 11.5, 11.3, 11.8, 12.0, 11.9, 12.2]
        rsi = calc_rsi(prices, period=14)
        assert 0 <= rsi <= 100

    def test_rsi_insufficient_data(self):
        assert calc_rsi([10.0, 10.5], period=14) == 50.0

    def test_rsi_all_up(self):
        prices = [float(i) for i in range(20)]
        assert calc_rsi(prices, 14) == 100.0

    def test_rsi_all_down(self):
        prices = [float(20 - i) for i in range(20)]
        assert calc_rsi(prices, 14) == 0.0


class TestMA:
    def test_ma_basic(self):
        assert calc_ma([10.0, 11.0, 12.0, 13.0, 14.0], 3) == 13.0

    def test_ma_insufficient(self):
        assert calc_ma([10.0, 11.0], 5) == 10.5


class TestBias:
    def test_bias_positive(self):
        assert calc_bias(11.0, 10.0) == 0.1

    def test_bias_negative(self):
        assert calc_bias(9.0, 10.0) == -0.1

    def test_bias_zero_ma(self):
        assert calc_bias(10.0, 0.0) == 0.0


class TestOpenChange:
    def test_positive(self):
        assert calc_open_change(10.1, 10.0) == 0.01
    def test_zero_close(self):
        assert calc_open_change(10.0, 0.0) == 0.0


class TestRoundToLot:
    def test_round(self):
        assert round_to_lot(550, 100) == 500
        assert round_to_lot(0, 100) == 0
        assert round_to_lot(99, 100) == 0
```

- [ ] **Step 2: Implement `engine/indicators.py`**

```python
"""Technical indicators — pure Python, no pandas dependency"""

from typing import Optional


def calc_rsi(prices: list[float], period: int = 14) -> float:
    if len(prices) < period + 1:
        return 50.0
    deltas = [prices[i] - prices[i - 1] for i in range(1, len(prices))]
    recent = deltas[-period:]
    gains = [d if d > 0 else 0 for d in recent]
    losses = [-d if d < 0 else 0 for d in recent]
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else 50.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def calc_ma(prices: list[float], period: int) -> float:
    if not prices:
        return 0.0
    window = prices[-period:]
    return sum(window) / len(window)


def calc_ema(prices: list[float], period: int) -> float:
    if not prices:
        return 0.0
    if len(prices) < 2:
        return prices[-1]
    multiplier = 2.0 / (period + 1)
    ema = sum(prices[:period]) / period
    for price in prices[period:]:
        ema = (price - ema) * multiplier + ema
    return ema


def calc_bias(price: float, ma: float) -> float:
    if ma <= 0:
        return 0.0
    return (price - ma) / ma


def calc_open_change(open_price: float, last_close: float) -> float:
    if last_close <= 0:
        return 0.0
    return (open_price - last_close) / last_close


def calc_macd(prices: list[float], fast: int = 12, slow: int = 26, signal: int = 9) -> dict:
    if len(prices) < slow + signal:
        return {"dif": 0.0, "dea": 0.0, "macd": 0.0}
    def _ema(data, p):
        m = 2.0 / (p + 1)
        result = [sum(data[:p]) / p]
        for v in data[p:]:
            result.append((v - result[-1]) * m + result[-1])
        return result
    ema_fast = _ema(prices, fast)
    ema_slow = _ema(prices, slow)
    start = slow - fast
    dif = [e_f - e_s for e_f, e_s in zip(ema_fast[start:], ema_slow)]
    dea_list = _ema(dif, signal)
    dea = dea_list[-1]
    macd_val = 2 * (dif[-1] - dea)
    return {"dif": round(dif[-1], 6), "dea": round(dea, 6), "macd": round(macd_val, 6)}


def round_to_lot(volume: int, lot_size: int = 100) -> int:
    if volume <= 0:
        return 0
    return (volume // lot_size) * lot_size
```

- [ ] **Step 3: Run tests**

```bash
cd /mnt/f/Codes/xtquant_learning && .venv/Scripts/python.exe -m pytest tests/test_indicators.py -v
```

- [ ] **Step 4: Commit**

```bash
git add engine/indicators.py tests/test_indicators.py
git commit -m "feat: add technical indicators (RSI, MA, EMA, MACD, bias)"
```

---

### Task 5: Database layer (SQLite schema + connection + queries)

**Files:** Create `db/database.py`, `db/schema.py`, `db/queries.py`, `tests/test_queries.py`

- [ ] **Step 1: Implement `db/database.py`**

```python
"""SQLite connection management"""

import sqlite3
import os
from contextlib import contextmanager

DB_PATH = "data/xtquant.db"


def set_db_path(path: str):
    global DB_PATH
    DB_PATH = path


def get_conn() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def transaction():
    conn = get_conn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
```

- [ ] **Step 2: Implement `db/schema.py`**

```python
"""Database schema DDL"""

from db.database import get_conn

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS strategies (
    name         TEXT PRIMARY KEY,
    display_name TEXT,
    enabled      INTEGER DEFAULT 1,
    config       TEXT DEFAULT '{}',
    created_at   TEXT DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS trade_records (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    strategy     TEXT NOT NULL,
    mode         TEXT NOT NULL,
    stock_code   TEXT NOT NULL,
    side         TEXT NOT NULL,
    volume       INTEGER NOT NULL,
    price        REAL NOT NULL,
    commission   REAL DEFAULT 0,
    stamp_tax    REAL DEFAULT 0,
    transfer_fee REAL DEFAULT 0,
    slippage     REAL DEFAULT 0,
    total_cost   REAL DEFAULT 0,
    reason       TEXT DEFAULT '',
    indicators   TEXT DEFAULT '{}',
    trade_time   TEXT NOT NULL,
    created_at   TEXT DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS idx_trade_strategy ON trade_records(strategy, mode);
CREATE INDEX IF NOT EXISTS idx_trade_time ON trade_records(trade_time);

CREATE TABLE IF NOT EXISTS backtest_runs (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id         TEXT UNIQUE NOT NULL,
    strategy       TEXT NOT NULL,
    start_date     TEXT NOT NULL,
    end_date       TEXT NOT NULL,
    params         TEXT DEFAULT '{}',
    initial_cash   REAL DEFAULT 0,
    final_equity   REAL DEFAULT 0,
    total_return   REAL DEFAULT 0,
    annual_return  REAL DEFAULT 0,
    max_drawdown   REAL DEFAULT 0,
    sharpe_ratio   REAL DEFAULT 0,
    win_rate       REAL DEFAULT 0,
    total_trades   INTEGER DEFAULT 0,
    equity_curve   TEXT DEFAULT '[]',
    baseline_curve TEXT DEFAULT '[]',
    created_at     TEXT DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS positions (
    stock_code   TEXT NOT NULL,
    mode         TEXT NOT NULL DEFAULT 'sim',
    volume       INTEGER DEFAULT 0,
    avg_cost     REAL DEFAULT 0,
    market_value REAL DEFAULT 0,
    profit_loss  REAL DEFAULT 0,
    updated_at   TEXT DEFAULT (datetime('now','localtime')),
    PRIMARY KEY (stock_code, mode)
);

CREATE TABLE IF NOT EXISTS account_snapshots (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    mode           TEXT NOT NULL,
    total_asset    REAL DEFAULT 0,
    available_cash REAL DEFAULT 0,
    market_value   REAL DEFAULT 0,
    frozen_cash    REAL DEFAULT 0,
    snapshot_time  TEXT NOT NULL
);
"""


def init_db():
    conn = get_conn()
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    conn.close()
```

- [ ] **Step 3: Implement `db/queries.py`**

```python
"""Database query interface — all functions return list[dict]"""

import json
from typing import Optional
from db.database import get_conn, transaction


def _row_to_dict(row) -> Optional[dict]:
    return dict(row) if row else None


def _rows_to_dicts(rows) -> list[dict]:
    return [dict(r) for r in rows]


# ── Strategy ──

def register_strategy(name: str, display_name: str, config: dict = None):
    with transaction() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO strategies (name, display_name, config) VALUES (?, ?, ?)",
            (name, display_name, json.dumps(config or {}, ensure_ascii=False)),
        )


def list_strategies() -> list[dict]:
    conn = get_conn()
    rows = conn.execute("SELECT * FROM strategies ORDER BY name").fetchall()
    conn.close()
    return _rows_to_dicts(rows)


def get_strategy(name: str) -> Optional[dict]:
    conn = get_conn()
    row = conn.execute("SELECT * FROM strategies WHERE name = ?", (name,)).fetchone()
    conn.close()
    return _row_to_dict(row)


def enable_strategy(name: str, enabled: bool):
    with transaction() as conn:
        conn.execute("UPDATE strategies SET enabled = ? WHERE name = ?",
                     (1 if enabled else 0, name))


def update_strategy_config(name: str, config: dict):
    with transaction() as conn:
        conn.execute("UPDATE strategies SET config = ? WHERE name = ?",
                     (json.dumps(config, ensure_ascii=False), name))


# ── Trade Records ──

def insert_trade(strategy: str, mode: str, stock_code: str, side: str,
                 volume: int, price: float, reason: str = "",
                 commission: float = 0, stamp_tax: float = 0,
                 transfer_fee: float = 0, slippage: float = 0,
                 total_cost: float = 0, indicators: dict = None,
                 trade_time: str = "") -> int:
    with transaction() as conn:
        cur = conn.execute(
            """INSERT INTO trade_records
               (strategy, mode, stock_code, side, volume, price, commission,
                stamp_tax, transfer_fee, slippage, total_cost, reason, indicators, trade_time)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (strategy, mode, stock_code, side, volume, price, commission,
             stamp_tax, transfer_fee, slippage, total_cost, reason,
             json.dumps(indicators or {}, ensure_ascii=False), trade_time),
        )
        return cur.lastrowid


def get_trades(strategy: str = None, mode: str = None, start: str = None,
               end: str = None, stock_code: str = None, limit: int = 100) -> list[dict]:
    query = "SELECT * FROM trade_records WHERE 1=1"
    params = []
    if strategy:
        query += " AND strategy = ?"; params.append(strategy)
    if mode:
        query += " AND mode = ?"; params.append(mode)
    if stock_code:
        query += " AND stock_code = ?"; params.append(stock_code)
    if start:
        query += " AND trade_time >= ?"; params.append(start)
    if end:
        query += " AND trade_time <= ?"; params.append(end)
    query += " ORDER BY trade_time DESC LIMIT ?"; params.append(limit)
    conn = get_conn()
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return _rows_to_dicts(rows)


# ── Backtest Runs ──

def insert_backtest_run(data: dict) -> str:
    run_id = data["run_id"]
    with transaction() as conn:
        conn.execute(
            """INSERT INTO backtest_runs
               (run_id, strategy, start_date, end_date, params, initial_cash,
                final_equity, total_return, annual_return, max_drawdown,
                sharpe_ratio, win_rate, total_trades, equity_curve, baseline_curve)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (run_id, data["strategy"], data["start_date"], data["end_date"],
             json.dumps(data.get("params", {}), ensure_ascii=False),
             data.get("initial_cash", 0), data.get("final_equity", 0),
             data.get("total_return", 0), data.get("annual_return", 0),
             data.get("max_drawdown", 0), data.get("sharpe_ratio", 0),
             data.get("win_rate", 0), data.get("total_trades", 0),
             json.dumps(data.get("equity_curve", []), ensure_ascii=False),
             json.dumps(data.get("baseline_curve", []), ensure_ascii=False)),
        )
    return run_id


def get_backtest_runs(strategy: str = None, limit: int = 20) -> list[dict]:
    conn = get_conn()
    if strategy:
        rows = conn.execute(
            "SELECT * FROM backtest_runs WHERE strategy = ? ORDER BY created_at DESC LIMIT ?",
            (strategy, limit)).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM backtest_runs ORDER BY created_at DESC LIMIT ?",
            (limit,)).fetchall()
    conn.close()
    return _rows_to_dicts(rows)


def get_backtest_run(run_id: str) -> Optional[dict]:
    conn = get_conn()
    row = conn.execute("SELECT * FROM backtest_runs WHERE run_id = ?", (run_id,)).fetchone()
    conn.close()
    return _row_to_dict(row)
```

- [ ] **Step 4: Write test `tests/test_queries.py`**

```python
import json
import pytest
from db.database import set_db_path
from db.schema import init_db
from db.queries import (
    register_strategy, list_strategies, get_strategy,
    enable_strategy, update_strategy_config,
    insert_trade, get_trades,
    insert_backtest_run, get_backtest_runs, get_backtest_run,
)


@pytest.fixture(autouse=True)
def setup_db(tmp_path):
    db_path = str(tmp_path / "test.db")
    set_db_path(db_path)
    init_db()
    yield
    import os
    if os.path.exists(db_path):
        os.remove(db_path)


class TestStrategyQueries:
    def test_register_and_list(self):
        register_strategy("test_strat", "Test Strategy")
        assert len(list_strategies()) == 1
        assert list_strategies()[0]["name"] == "test_strat"

    def test_get_strategy(self):
        register_strategy("s1", "S1")
        assert get_strategy("s1")["name"] == "s1"
        assert get_strategy("nope") is None

    def test_enable_disable(self):
        register_strategy("s1", "S1")
        enable_strategy("s1", False)
        assert get_strategy("s1")["enabled"] == 0
        enable_strategy("s1", True)
        assert get_strategy("s1")["enabled"] == 1

    def test_update_config(self):
        register_strategy("s1", "S1", {"k": "v"})
        update_strategy_config("s1", {"new": "val"})
        s = get_strategy("s1")
        config = json.loads(s["config"]) if isinstance(s["config"], str) else s["config"]
        assert config["new"] == "val"


class TestTradeQueries:
    def _make_trade(self, strategy="test", mode="sim", stock="000001.SZ", **kw):
        return insert_trade(strategy=strategy, mode=mode, stock_code=stock,
                           side="buy", volume=100, price=10.0, reason="",
                           trade_time="2024-01-15 10:30:00", **kw)

    def test_insert_and_get(self):
        self._make_trade()
        trades = get_trades()
        assert len(trades) == 1
        assert trades[0]["stock_code"] == "000001.SZ"

    def test_filter_by_strategy(self):
        self._make_trade(strategy="s1", stock="A.SZ")
        self._make_trade(strategy="s2", stock="B.SZ")
        assert len(get_trades(strategy="s1")) == 1
        assert len(get_trades(strategy="s2")) == 1

    def test_filter_by_mode(self):
        self._make_trade(mode="sim", stock="A.SZ")
        self._make_trade(mode="backtest", stock="B.SZ")
        assert len(get_trades(mode="sim")) == 1
        assert len(get_trades(mode="backtest")) == 1

    def test_limit(self):
        for i in range(10):
            self._make_trade(stock=f"{i:06d}.SZ")
        assert len(get_trades(limit=5)) == 5


class TestBacktestQueries:
    def _make_run(self, **kw):
        base = {"run_id": "test-001", "strategy": "s1",
                "start_date": "2024", "end_date": "2024",
                "params": {}, "initial_cash": 100000, "final_equity": 110000,
                "total_return": 0.1, "annual_return": 0.1,
                "max_drawdown": -0.05, "sharpe_ratio": 1.5,
                "win_rate": 0.6, "total_trades": 50, "equity_curve": []}
        base.update(kw)
        return insert_backtest_run(base)

    def test_insert_and_list(self):
        self._make_run()
        assert len(get_backtest_runs()) == 1

    def test_get_by_run_id(self):
        self._make_run(run_id="test-002")
        r = get_backtest_run("test-002")
        assert r is not None
        assert r["strategy"] == "s1"
```

- [ ] **Step 5: Run tests**

```bash
cd /mnt/f/Codes/xtquant_learning && .venv/Scripts/python.exe -m pytest tests/test_queries.py -v
```

- [ ] **Step 6: Verify DB init**

```bash
cd /mnt/f/Codes/xtquant_learning && .venv/Scripts/python.exe -c "
from db.schema import init_db; init_db()
import sqlite3; conn = sqlite3.connect('data/xtquant.db')
tables = conn.execute(\"SELECT name FROM sqlite_master WHERE type='table'\").fetchall()
print('Tables:', [t[0] for t in tables]); conn.close()
"
# Expected: strategies, trade_records, backtest_runs, positions, account_snapshots
```

- [ ] **Step 7: Commit**

```bash
git add db/database.py db/schema.py db/queries.py tests/test_queries.py
git commit -m "feat: add SQLite database layer with schema and query interface"
```

---

### Task 6: Fee calculator

**Files:** Create `trade/fees.py`, Create `tests/test_fees.py`

- [ ] **Step 1: Write test `tests/test_fees.py`**

```python
from trade.fees import FeeCalculator


class TestFeeCalculator:
    def _calc(self, **kw):
        defaults = dict(commission_rate=0.00025, stamp_tax_rate=0.001,
                        transfer_fee_rate=0.00002, min_commission=5.0, slippage_rate=0.001)
        defaults.update(kw)
        return FeeCalculator(**defaults)

    def test_buy_cost(self):
        calc = self._calc()
        c = calc.calc_trade_cost(price=10.0, volume=1000, side="buy")
        # amount=10000; commission=max(2.5,5)=5; stamp=0; transfer=0.2; slippage=10
        assert c.commission == 5.0
        assert c.stamp_tax == 0.0
        assert c.transfer_fee == 0.2
        assert c.slippage_cost == 10.0
        assert c.total == 15.2
        assert c.net_amount == 10015.2  # buy pays more

    def test_sell_cost(self):
        calc = self._calc()
        c = calc.calc_trade_cost(price=10.0, volume=1000, side="sell")
        assert c.stamp_tax == 10.0
        assert c.total == 25.2
        assert c.net_amount == 9974.8  # sell receives less

    def test_large_commission(self):
        calc = self._calc(slippage_rate=0.0)
        c = calc.calc_trade_cost(price=10.0, volume=50000, side="buy")
        assert c.commission == 125.0  # 500000 * 0.00025

    def test_slippage_price(self):
        calc = self._calc()
        assert calc.calc_slippage_price(10.0, "buy") == 10.01
        assert calc.calc_slippage_price(10.0, "sell") == 9.99
```

- [ ] **Step 2: Implement `trade/fees.py`**

```python
"""Fee calculation (commission, stamp tax, transfer fee, slippage)"""

from dataclasses import dataclass


@dataclass
class TradeCost:
    commission: float = 0.0
    stamp_tax: float = 0.0
    transfer_fee: float = 0.0
    slippage_cost: float = 0.0
    total: float = 0.0
    net_amount: float = 0.0


class FeeCalculator:
    def __init__(self, commission_rate: float = 0.00025, stamp_tax_rate: float = 0.001,
                 transfer_fee_rate: float = 0.00002, min_commission: float = 5.0,
                 slippage_rate: float = 0.001):
        self.commission_rate = commission_rate
        self.stamp_tax_rate = stamp_tax_rate
        self.transfer_fee_rate = transfer_fee_rate
        self.min_commission = min_commission
        self.slippage_rate = slippage_rate

    def calc_trade_cost(self, price: float, volume: int, side: str) -> TradeCost:
        amount = price * volume
        commission = max(amount * self.commission_rate, self.min_commission)
        stamp_tax = amount * self.stamp_tax_rate if side == "sell" else 0.0
        transfer_fee = amount * self.transfer_fee_rate
        slippage = amount * self.slippage_rate
        total = commission + stamp_tax + transfer_fee + slippage
        net = amount + total if side == "buy" else amount - total
        return TradeCost(
            commission=round(commission, 4), stamp_tax=round(stamp_tax, 4),
            transfer_fee=round(transfer_fee, 4), slippage_cost=round(slippage, 4),
            total=round(total, 4), net_amount=round(net, 4),
        )

    def calc_slippage_price(self, price: float, side: str) -> float:
        if side == "buy":
            return round(price * (1 + self.slippage_rate), 4)
        else:
            return round(price * (1 - self.slippage_rate), 4)
```

- [ ] **Step 3: Run tests**

```bash
cd /mnt/f/Codes/xtquant_learning && .venv/Scripts/python.exe -m pytest tests/test_fees.py -v
```

- [ ] **Step 4: Commit**

```bash
git add trade/fees.py tests/test_fees.py
git commit -m "feat: add fee calculator with commission/stamp/transfer/slippage"
```

---

### Task 7: Data provider (backtest data source)

**Files:** Create `backtest/data_provider.py`, Create `tests/test_data_provider.py`

- [ ] **Step 1: Implement `backtest/data_provider.py`**

```python
"""Historical data provider — xtquant > akshare > parquet cache > synthetic"""

import os, time
from datetime import datetime, timedelta
from typing import Optional
import numpy as np
import pandas as pd

CACHE_DIR = "data/cache/klines"
CACHE_TTL = 86400


class DataProvider:
    def __init__(self, cache_dir: str = CACHE_DIR, cache_ttl: int = CACHE_TTL):
        self._cdir = cache_dir; self._cttl = cache_ttl
        os.makedirs(cache_dir, exist_ok=True)

    def get_kline(self, stock_code: str, start_date: str, end_date: str,
                  fields: list[str] = None) -> Optional[pd.DataFrame]:
        if fields is None:
            fields = ["close", "open", "high", "low", "volume"]
        df = self._cache_get(stock_code, start_date, end_date)
        if df is not None:
            return self._filter(df, fields)
        df = self._try_xtquant(stock_code, start_date, end_date)
        if df is not None and len(df) > 0:
            self._cache_set(stock_code, start_date, end_date, df)
            return self._filter(df, fields)
        df = self._try_akshare(stock_code, start_date, end_date)
        if df is not None and len(df) > 0:
            self._cache_set(stock_code, start_date, end_date, df)
            return self._filter(df, fields)
        df = self._synthetic(stock_code, start_date, end_date)
        return self._filter(df, fields)

    def _ckey(self, code, s, e): return f"{code.replace('.','_')}_{s}_{e}.parquet"

    def _cache_get(self, c, s, e):
        p = os.path.join(self._cdir, self._ckey(c, s, e))
        if not os.path.exists(p): return None
        if time.time() - os.path.getmtime(p) > self._cttl:
            os.remove(p); return None
        try: return pd.read_parquet(p)
        except: return None

    def _cache_set(self, c, s, e, df):
        try: df.to_parquet(os.path.join(self._cdir, self._ckey(c, s, e)), index=False)
        except: pass

    def _try_xtquant(self, code, start, end):
        try:
            import xtquant.xtdata as xtdata
        except ImportError:
            return None
        try:
            xtdata.download_history_data(code, period='1d', start_time=start, end_time=end)
            data = xtdata.get_market_data(
                field_list=['close','open','high','low','volume'],
                stock_list=[code], start_time=start, end_time=end, period='1d')
            if data and 'close' in data and code in data['close'].index:
                close_s = data['close'].loc[code]
                df = pd.DataFrame({"close": close_s})
                for f in ['open','high','low','volume']:
                    if f in data and code in data[f].index:
                        df[f] = data[f].loc[code]
                df = df.dropna(subset=["close"]).reset_index()
                df = df.rename(columns={"index": "time"})
                df["time"] = df["time"].astype(str)
                return df
        except:
            return None
        return None

    def _try_akshare(self, code, start, end):
        try: import akshare as ak
        except ImportError: return None
        try:
            sym = code.split(".")[0]
            df = ak.stock_zh_a_hist(symbol=sym, period="daily",
                                    start_date=start.replace("-","")[:8],
                                    end_date=end.replace("-","")[:8], adjust="qfq")
            if df is None or len(df) == 0: return None
            df = df.rename(columns={"日期":"time","开盘":"open","收盘":"close",
                                     "最高":"high","最低":"low","成交量":"volume"})
            df["time"] = df["time"].astype(str)
            for c in ["open","high","low","close"]:
                df[c] = pd.to_numeric(df[c], errors="coerce")
            df = df.dropna(subset=["close"])
            return df[["time","open","high","low","close","volume"]]
        except: return None

    def _synthetic(self, code, start, end):
        sd = datetime.strptime(start[:8], "%Y%m%d")
        ed = datetime.strptime(end[:8], "%Y%m%d")
        days = min((ed - sd).days, 1500)
        np.random.seed(hash(code) % 2**31)
        ret = np.random.normal(0.0003, 0.015, days)
        close = 10.0 * np.exp(np.cumsum(ret))
        dates = []; cur = sd
        while len(dates) < days:
            if cur.weekday() < 5: dates.append(cur.strftime("%Y%m%d"))
            cur += timedelta(days=1)
        return pd.DataFrame({
            "time": dates[:days], "close": close,
            "open": close * np.random.uniform(0.99, 1.01, days),
            "high": close * np.random.uniform(1.00, 1.02, days),
            "low": close * np.random.uniform(0.98, 1.00, days),
            "volume": np.random.randint(10**5, 10**7, days).astype(int),
        })

    def _filter(self, df, fields):
        avail = [f for f in fields if f in df.columns]
        return df[avail]
```

- [ ] **Step 2: Write test `tests/test_data_provider.py`**

```python
from backtest.data_provider import DataProvider


class TestDataProvider:
    def test_synthetic_fallback(self):
        p = DataProvider(cache_dir="/tmp/test_bt_cache")
        df = p.get_kline("999999.SH", "20230101", "20231231")
        assert df is not None
        assert len(df) > 100
        assert "close" in df.columns
        assert "open" in df.columns
        assert "time" in df.columns
```

- [ ] **Step 3: Run tests**

```bash
cd /mnt/f/Codes/xtquant_learning && .venv/Scripts/python.exe -m pytest tests/test_data_provider.py -v
```

- [ ] **Step 4: Commit**

```bash
git add backtest/data_provider.py tests/test_data_provider.py
git commit -m "feat: add data provider with xtquant/akshare/synthetic fallback"
```

---

### Task 8: Performance metrics

**Files:** Create `backtest/metrics.py`, Create `tests/test_metrics.py`

- [ ] **Step 1: Implement `backtest/metrics.py`**

```python
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
            profitable = sum(1 for t in trades if t.get("side") == "sell" and t.get("price", 0) > 0)
            if profitable > 0:
                win_rate = profitable / len([t for t in trades if t.get("side") == "sell"])
            if win_rate == 0:
                # for buy-only strategies, count all as wins
                win_rate = 1.0 if all(t.get("side") == "buy" for t in trades) else 0.0

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
        if len(excess) < 2: return 0.0
        std = np.std(excess)
        if std == 0: return 0.0
        return float(np.mean(excess) / std * np.sqrt(252))

    @staticmethod
    def _empty() -> dict:
        return {k: 0.0 for k in ["total_return", "return_rate",
                "annualized_return", "max_drawdown", "volatility",
                "sharpe_ratio", "calmar_ratio", "win_rate"]}
```

- [ ] **Step 2: Write test `tests/test_metrics.py`**

```python
import numpy as np
from backtest.metrics import MetricsCalculator


def test_profitable():
    calc = MetricsCalculator()
    equity = list(np.linspace(100000, 110000, 252))
    r = calc.calculate(equity, 100000)
    assert r["return_rate"] == pytest.approx(0.1, abs=0.02)
    assert r["max_drawdown"] == 0.0
    assert r["sharpe_ratio"] > 0


def test_empty():
    r = MetricsCalculator().calculate([], 100000)
    assert r["return_rate"] == 0.0
```

- [ ] **Step 3: Run tests**

```bash
cd /mnt/f/Codes/xtquant_learning && .venv/Scripts/python.exe -m pytest tests/test_metrics.py -v
```

- [ ] **Step 4: Commit**

```bash
git add backtest/metrics.py tests/test_metrics.py
git commit -m "feat: add performance metrics (Sharpe, CAGR, max drawdown)"
```
## Phase 2: Backtest Engine

### Task 9: Backtest engine (core daily loop)

**Files:** Create `backtest/engine.py`, Create `tests/test_backtest_engine.py`

- [ ] **Step 1: Implement `backtest/engine.py`**

Abbreviated for space — the engine implements:
- `BacktestEngine.run(strategy_name, stock_code, start, end, params, initial_capital, save_to_db)` -> dict
- Daily loop: iterate over K-line DataFrame, construct Quote, accumulate daily closes into `strategy._price_history`, call `strategy.on_quote(quote)`, process buy/sell signals, record trades with fees, track equity curve
- Signal processing: buy -> round_to_lot -> check cash -> subtract fee-adjusted cost -> update position/avg_cost. sell -> round_to_lot -> check position -> add fee-adjusted income
- Final liquidation on last day
- Metrics calculation via `MetricsCalculator`
- DB persistence via `insert_trade` and `insert_backtest_run`
- Helper: `_weekday_from_name(day_name) -> int` for Chinese/English weekday parsing

See the spec document for the full data flow. The engine is ~140 lines.

- [ ] **Step 2: Write test `tests/test_backtest_engine.py`**

```python
from backtest.engine import _weekday_from_name


class TestWeekday:
    def test_chinese(self):
        assert _weekday_from_name("周三") == 2
    def test_english(self):
        assert _weekday_from_name("wednesday") == 2
    def test_short(self):
        assert _weekday_from_name("Wed") == 2
    def test_unknown(self):
        assert _weekday_from_name("foo") == -1


# Integration test added in Task 10 after strategy is implemented
```

- [ ] **Step 3: Run tests**

```bash
cd /mnt/f/Codes/xtquant_learning && .venv/Scripts/python.exe -m pytest tests/test_backtest_engine.py -v
```

- [ ] **Step 4: Commit**

```bash
git add backtest/engine.py tests/test_backtest_engine.py
git commit -m "feat: add backtest engine with daily event loop"
```

---

### Task 10: Grid optimizer + baseline

**Files:** Create `backtest/optimizer.py`, Create `backtest/baseline.py`

- [ ] **Step 1: Implement `backtest/optimizer.py`**

```python
"""Grid search parameter optimizer"""

from itertools import product
from backtest.engine import BacktestEngine


class GridOptimizer:
    def __init__(self, strategy_name, stock_code, start_date, end_date,
                 initial_capital=100000.0):
        self._sn = strategy_name
        self._sc = stock_code
        self._sd = start_date
        self._ed = end_date
        self._cap = initial_capital
        self._engine = BacktestEngine()

    def optimize(self, param_grid: dict[str, list], metric: str = "sharpe_ratio",
                 save_to_db: bool = False) -> list[dict]:
        names = list(param_grid.keys())
        vals = list(param_grid.values())
        combos = list(product(*vals))
        _strip = {"equity_curve", "trades", "run_id"}
        results = []
        for combo in combos:
            params = dict(zip(names, combo))
            r = self._engine.run(self._sn, self._sc, self._sd, self._ed,
                                 params=params, initial_capital=self._cap,
                                 save_to_db=save_to_db)
            if "error" in r:
                continue
            entry = {"params": params}
            entry.update({k: v for k, v in r.items() if k not in _strip})
            results.append(entry)
        results.sort(key=lambda r: r.get(metric, -float("inf")), reverse=True)
        return results

    def top_n(self, param_grid, n=10, metric="sharpe_ratio"):
        return self.optimize(param_grid, metric=metric)[:n]
```

- [ ] **Step 2: Implement `backtest/baseline.py`**

Provides `run_dca_baseline(df, stock_code, initial_capital, investment_days, base_volume, lot_size)` and `run_buyhold_baseline(df, stock_code, initial_capital, lot_size)`. DCA baseline invests same amount on same days without timing. Buy&Hold buys all on day 1, sells on last day. Both return {baseline_type, final_value, total_return, total_trades, equity_curve}.

- [ ] **Step 3: Commit**

```bash
git add backtest/optimizer.py backtest/baseline.py
git commit -m "feat: add grid optimizer and baseline comparison"
```

---

## Phase 3: Trading Execution

### Task 11: Quote pump + Sim executor + Real executor

**Files:** Create `trade/quote_pump.py`, `trade/sim_executor.py`, `trade/real_executor.py`

- [ ] **Step 1: Implement `trade/quote_pump.py`**

```python
"""Quote pump — bridges xtquant callbacks to Quote objects"""

import asyncio
from datetime import datetime
from typing import Callable
from engine.strategy_base import Quote


class QuotePump:
    def __init__(self):
        self._callbacks: list[Callable] = []
        self._last_prices: dict[str, float] = {}
        self._running = False

    def on_quote(self, callback: Callable[[Quote], None]):
        self._callbacks.append(callback)

    async def subscribe(self, stock_codes: list[str]):
        self._running = True
        import xtquant.xtdata as xtdata
        for code in stock_codes:
            xtdata.subscribe_quote(code, period='1d', start_time='',
                                   end_time='', count=1, callback=self._on_tick)

    def _on_tick(self, data: dict):
        code = data.get("stockCode", "")
        if not code: return
        lp = data.get("lastPrice", 0)
        if code in self._last_prices and self._last_prices[code] == lp:
            return
        self._last_prices[code] = lp
        quote = Quote(stock_code=code, last_price=lp,
                      open=data.get("open", 0), high=data.get("high", 0),
                      low=data.get("low", 0), last_close=data.get("lastClose", 0),
                      volume=data.get("volume", 0), amount=data.get("amount", 0),
                      time=datetime.now())
        for cb in self._callbacks:
            try: cb(quote)
            except: pass

    async def stop(self):
        self._running = False
```

- [ ] **Step 2: Implement `trade/sim_executor.py`**

```python
"""Simulated trade executor with virtual account and full fee calculation"""

from datetime import datetime
from trade.fees import FeeCalculator


class SimAccount:
    def __init__(self, cash: float = 100000.0):
        self.cash = cash
        self.positions: dict[str, dict] = {}

    def get_position(self, code): return self.positions.get(code, {"volume": 0, "avg_cost": 0.0})

    def can_buy(self, price, volume, fee_calc):
        cost = fee_calc.calc_trade_cost(price, volume, "buy")
        return self.cash >= price * volume + cost.total

    def can_sell(self, code, volume):
        return self.get_position(code)["volume"] >= volume

    def execute_buy(self, code, price, volume, fee_calc):
        cost = fee_calc.calc_trade_cost(price, volume, "buy")
        total = price * volume + cost.total
        self.cash -= total
        pos = self.positions.setdefault(code, {"volume": 0, "avg_cost": 0.0})
        old = pos["avg_cost"] * pos["volume"]
        pos["volume"] += volume
        pos["avg_cost"] = (old + price * volume) / pos["volume"]
        return {"executed": True, "side": "buy", "price": price, "volume": volume,
                "commission": cost.commission, "stamp_tax": cost.stamp_tax,
                "transfer_fee": cost.transfer_fee, "slippage": cost.slippage_cost,
                "total_cost": cost.total, "cash_after": round(self.cash, 4)}

    def execute_sell(self, code, price, volume, fee_calc):
        pos = self.positions.get(code, {"volume": 0, "avg_cost": 0.0})
        vol = min(volume, pos["volume"])
        if vol <= 0: return {"executed": False, "reason": "no position"}
        cost = fee_calc.calc_trade_cost(price, vol, "sell")
        self.cash += price * vol - cost.total
        pos["volume"] -= vol
        if pos["volume"] <= 0: self.positions.pop(code, None)
        return {"executed": True, "side": "sell", "price": price, "volume": vol,
                "commission": cost.commission, "stamp_tax": cost.stamp_tax,
                "transfer_fee": cost.transfer_fee, "slippage": cost.slippage_cost,
                "total_cost": cost.total, "cash_after": round(self.cash, 4)}

    def total_value(self, prices: dict[str, float]) -> float:
        mv = sum(pos["volume"] * prices.get(code, 0) for code, pos in self.positions.items())
        return self.cash + mv


class SimExecutor:
    def __init__(self, initial_capital: float = 100000.0):
        self.account = SimAccount(cash=initial_capital)
        self.fee_calc = FeeCalculator()

    async def place_order(self, stock_code, side, volume, price):
        if side == "buy":
            if not self.account.can_buy(price, volume, self.fee_calc):
                return {"executed": False, "reason": "insufficient cash"}
            return self.account.execute_buy(stock_code, price, volume, self.fee_calc)
        elif side == "sell":
            if not self.account.can_sell(stock_code, volume):
                return {"executed": False, "reason": "insufficient position"}
            return self.account.execute_sell(stock_code, price, volume, self.fee_calc)
        return {"executed": False, "reason": f"unknown side: {side}"}

    def get_account(self):
        return {"mode": "sim", "available_cash": self.account.cash,
                "total_asset": self.account.cash}

    def get_positions(self):
        return [{"stock_code": c, "volume": p["volume"], "avg_cost": p["avg_cost"]}
                for c, p in self.account.positions.items() if p["volume"] > 0]
```

- [ ] **Step 3: Implement `trade/real_executor.py`** (stub that wraps xtquant.XtQuantTrader only when available)

- [ ] **Step 4: Commit**

```bash
git add trade/quote_pump.py trade/sim_executor.py trade/real_executor.py
git commit -m "feat: add quote pump, sim executor, and real executor"
```

---

### Task 12: Order broker

**Files:** Create `trade/broker.py`

- [ ] **Step 1: Implement `trade/broker.py`**

```python
"""Trade broker — receives Signal, executes, persists to DB"""

from datetime import datetime
from engine.strategy_base import Signal
from db.queries import insert_trade


class Broker:
    def __init__(self, executor, mode: str = "sim"):
        self._executor = executor
        self._mode = mode

    async def handle_signal(self, signal: Signal, strategy_name: str) -> dict:
        if signal.side not in ("buy", "sell"):
            return {"executed": False, "reason": f"invalid side: {signal.side}"}

        result = await self._executor.place_order(
            stock_code=signal.stock_code, side=signal.side,
            volume=signal.volume, price=signal.price)

        if result.get("executed"):
            insert_trade(
                strategy=strategy_name, mode=self._mode,
                stock_code=signal.stock_code, side=signal.side,
                volume=result.get("volume", signal.volume),
                price=result.get("price", signal.price),
                commission=result.get("commission", 0),
                stamp_tax=result.get("stamp_tax", 0),
                transfer_fee=result.get("transfer_fee", 0),
                slippage=result.get("slippage", 0),
                total_cost=result.get("total_cost", 0),
                reason=signal.reason, indicators=signal.indicators,
                trade_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            )
        return result
```

- [ ] **Step 2: Commit**

```bash
git add trade/broker.py
git commit -m "feat: add trade broker (signal -> execute -> persist)"
```

---

## Phase 4: Strategies

### Task 13: Bonus stocks DCA strategy

**Files:** Create `strategies/bonus_stocks.py`, Create `tests/test_bonus_stocks_strategy.py`

- [ ] **Step 1: Implement `strategies/bonus_stocks.py`**

The strategy class (~160 lines):
- `@register` decorator, `name = "bonus_stocks"`, `watched_stocks = ["510880.SH", "159905.SZ"]`
- `on_quote(quote)` -> accumulates daily close to `self._price_history`, checks if Wednesday via `_is_investment_day()`, calculates RSI/MA/bias/open_change, decides buy/skip based on thresholds, returns `Signal(side="buy", volume, ...)` with indicator snapshot
- 12 configurable parameters with defaults from `DEFAULTS` dict
- `get_config_schema()`, `get_tuning_space()` methods
- Full implementation matches the design spec

- [ ] **Step 2: Write test `tests/test_bonus_stocks_strategy.py`**

```python
from datetime import datetime
from engine.strategy_base import Quote
from strategies.bonus_stocks import BonusStocksStrategy


def test_watched_stocks():
    s = BonusStocksStrategy()
    assert "510880.SH" in s.watched_stocks

def test_no_history_returns_none():
    s = BonusStocksStrategy()
    s._price_history = {}
    q = Quote(stock_code="510880.SH", last_price=3.45, open=3.40,
              last_close=3.42, time=datetime(2024, 1, 10, 10, 30))
    assert s.on_quote(q) is None

def test_config_schema():
    s = BonusStocksStrategy()
    schema = s.get_config_schema()
    assert "rsi_period" in schema["properties"]

def test_tuning_space():
    s = BonusStocksStrategy()
    space = s.get_tuning_space()
    param_names = [p["name"] for p in space]
    assert "rsi_period" in param_names

def test_update_params():
    s = BonusStocksStrategy()
    s.update_params({"rsi_period": 21, "base_volume": 1000})
    assert s.rsi_period == 21
    assert s.base_volume == 1000
```

- [ ] **Step 3: Run strategy tests**

```bash
cd /mnt/f/Codes/xtquant_learning && .venv/Scripts/python.exe -m pytest tests/test_bonus_stocks_strategy.py -v
```

- [ ] **Step 4: Add backtest integration test to `tests/test_backtest_engine.py`**

```python
from strategies.bonus_stocks import BonusStocksStrategy

class TestBacktestIntegration:
    def test_backtest_bonus_stocks(self):
        from backtest.engine import BacktestEngine
        engine = BacktestEngine()
        result = engine.run(
            strategy_name="bonus_stocks", stock_code="510880.SH",
            start_date="20220101", end_date="20221231",
            params={"base_volume": 500, "investment_days": ["Wednesday"]},
            initial_capital=100000, save_to_db=False)
        assert "error" not in result, result.get("error")
        assert result["total_trades"] >= 0
```

- [ ] **Step 5: Run integration test**

```bash
cd /mnt/f/Codes/xtquant_learning && .venv/Scripts/python.exe -m pytest tests/test_backtest_engine.py::TestBacktestIntegration -v
```

- [ ] **Step 6: Commit**

```bash
git add strategies/bonus_stocks.py tests/test_bonus_stocks_strategy.py
git commit -m "feat: add bonus stocks DCA strategy with backtest integration"
```

---

## Phase 5: CLI Scripts

### Task 14: manage.py (strategy management)

**Files:** Create `scripts/manage.py`

- [ ] **Step 1: Implement `scripts/manage.py`**

The script supports: `--init` (scan strategies/ dir, register to DB), `--list` (show all), `--enable/--disable <name>`, `--show <name>` (display params), `--set <name> --param k=v` (update params). It calls `db/queries.py` functions and scans `strategies/` directory to discover `@register`-decorated classes.

- [ ] **Step 2: Test**

```bash
cd /mnt/f/Codes/xtquant_learning && .venv/Scripts/python.exe scripts/manage.py --init
.venv/Scripts/python.exe scripts/manage.py --list
.venv/Scripts/python.exe scripts/manage.py --show bonus_stocks
```

- [ ] **Step 3: Commit**

```bash
git add scripts/manage.py
git commit -m "feat: add strategy management CLI (manage.py)"
```

---

### Task 15: run_backtest.py

**Files:** Create `scripts/run_backtest.py`

- [ ] **Step 1: Implement `scripts/run_backtest.py`**

Supports: `--strategy --start --end --stock --initial-cash` for running backtest, `--optimize --target` for grid search, `--list` for history, `--show <run_id>` for details. Prints formatted report with equity curve summary.

- [ ] **Step 2: Test**

```bash
cd /mnt/f/Codes/xtquant_learning && .venv/Scripts/python.exe scripts/run_backtest.py --strategy bonus_stocks --stock 510880.SH --start 20220101 --end 20221231
```

- [ ] **Step 3: Commit**

```bash
git add scripts/run_backtest.py
git commit -m "feat: add backtest CLI with grid search support"
```

---

### Task 16: run_sim.py

**Files:** Create `scripts/run_sim.py`

- [ ] **Step 1: Implement `scripts/run_sim.py`**

Loads enabled strategies, creates `SimExecutor` + `Broker`, subscribes to xtquant quotes or uses synthetic data, runs signal loop. `--strategy` flag overrides which strategies to trade.

- [ ] **Step 2: Commit**

```bash
git add scripts/run_sim.py
git commit -m "feat: add simulated trading CLI"
```

---

### Task 17: run_real.py

**Files:** Create `scripts/run_real.py`

- [ ] **Step 1: Implement `scripts/run_real.py`**

Loads config.yaml for QMT path/account_id, creates `RealExecutor` + `Broker`, subscribes to xtquant `QuotePump`. Requires QMT client running on Windows.

- [ ] **Step 2: Commit**

```bash
git add scripts/run_real.py
git commit -m "feat: add real trading CLI (requires QMT)"
```

---

### Task 18: show_trades.py

**Files:** Create `scripts/show_trades.py`

- [ ] **Step 1: Implement `scripts/show_trades.py`**

Queries `get_trades()` with filters: `--strategy`, `--mode`, `--start`, `--end`, `--stock`, `--today`, `--limit`. Prints formatted table with fee totals.

- [ ] **Step 2: Commit**

```bash
git add scripts/show_trades.py
git commit -m "feat: add trade record query CLI"
```

---

## Phase 6: Documentation & Cleanup

### Task 19: API_REFERENCE.md

**Files:** Create `docs/API_REFERENCE.md`

- [ ] **Step 1: Create comprehensive API reference**

Document all CLI commands with full argument descriptions and examples. Document all `db/queries.py` function signatures and return formats. Document `StrategyBase`, `@register`, `get_config_schema()`, `get_tuning_space()`. Document `BacktestEngine`, `GridOptimizer`, `FeeCalculator`, `SimExecutor`, `RealExecutor`.

- [ ] **Step 2: Commit**

```bash
git add docs/API_REFERENCE.md
git commit -m "docs: add comprehensive API reference"
```

---

### Task 20: Update AGENTS.md

**Files:** Modify `AGENTS.md`

- [ ] **Step 1: Replace the AGENTS.md content**

Update to reflect new project structure:
- Replace PostgreSQL section with SQLite
- Remove gRPC, Frontend, FastAPI, Docker sections
- Remove alembic commands
- Add new CLI commands reference
- Add critical instruction: "**AI MUST read `docs/API_REFERENCE.md` before executing any trade, backtest, or data query task.** Interface changes MUST sync to API_REFERENCE.md."

- [ ] **Step 2: Commit**

```bash
git add AGENTS.md
git commit -m "docs: update AGENTS.md for simplified architecture"
```

---

### Task 21: Cleanup old code

**Files:** Remove old `backend/`, `src/`, `frontend/`, `docker/`, old config files

- [ ] **Step 1: Remove old directories**

```bash
git rm -r backend/ src/ frontend/ docker/ config/ alembic.ini conftest.py demo_xtquant_test.py docs/ARCHITECTURE.md docs/DEVELOPMENT.md docs/trade_engine.md 2>/dev/null || true
# Keep: tests/ directory, data/, .venv/, .gitignore
```

- [ ] **Step 2: Run full test suite**

```bash
cd /mnt/f/Codes/xtquant_learning && XTQUANT_TESTING=1 .venv/Scripts/python.exe -m pytest tests/ -v --ignore=tests/conftest.py
```

- [ ] **Step 3: Verify all CLI scripts work**

```bash
.venv/Scripts/python.exe scripts/manage.py --init && .venv/Scripts/python.exe scripts/manage.py --list
.venv/Scripts/python.exe scripts/run_backtest.py --strategy bonus_stocks --stock 510880.SH --start 20220101 --end 20220630
```

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "chore: remove old backend/frontend/docker code, verify test suite passes"
```

---

## Completed State

After all tasks:
- **15-20 Python files** across engine/trade/backtest/db/strategies/scripts
- **5 CLI scripts** for all operations
- **SQLite database** for persistence
- **Full test suite** covering core abstractions, DB queries, fees, indicators, and strategy
- **API_REFERENCE.md** as single source of truth for all interfaces
- **AGENTS.md** guides AI to read API_REFERENCE.md before any task
