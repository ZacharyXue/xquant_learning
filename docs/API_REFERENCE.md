# API Reference

This document lists all available CLI commands and Python function interfaces.
Interface changes **MUST** be synchronized with this document.

---

## CLI Commands

### manage.py — Strategy Management

**Single point of strategy configuration.** Trade and backtest scripts do NOT configure strategy parameters directly.

| Command | Description |
|---------|-------------|
| `python scripts/manage.py --init` | First-time init: scan `strategies/` dir, register all strategies |
| `python scripts/manage.py --list` | List all strategies with enable/disable status |
| `python scripts/manage.py --enable <name>` | Enable strategy (allow it to participate in trading) |
| `python scripts/manage.py --disable <name>` | Disable strategy |
| `python scripts/manage.py --show <name>` | Show current strategy parameters |
| `python scripts/manage.py --set <name> --param key=value [--param k2=v2]` | Update strategy parameters |

### run_backtest.py — Backtest

| Command | Description |
|---------|-------------|
| `python scripts/run_backtest.py --strategy <name> --start YYYYMMDD --end YYYYMMDD` | Run backtest |
| `python scripts/run_backtest.py --strategy <name> ... --stock <code>` | Specify stock (default: strategy.watched_stocks[0]) |
| `python scripts/run_backtest.py --strategy <name> ... --initial-cash <amount>` | Set initial capital (default: 100000) |
| `python scripts/run_backtest.py --strategy <name> ... --optimize --target <metric>` | Grid search optimization. target: `sharpe_ratio` / `annualized_return` / `max_drawdown` |
| `python scripts/run_backtest.py --list` | List historical backtest runs |
| `python scripts/run_backtest.py --show <run_id>` | View backtest details |

### run_sim.py — Simulated Trading

| Command | Description |
|---------|-------------|
| `python scripts/run_sim.py` | All enabled strategies participate |
| `python scripts/run_sim.py --strategy <name>` | Only specified strategy |
| `python scripts/run_sim.py --initial-cash <amount>` | Set initial capital |

### run_real.py — Real Trading (requires QMT)

| Command | Description |
|---------|-------------|
| `python scripts/run_real.py` | All enabled strategies |
| `python scripts/run_real.py --strategy <name>` | Only specified strategy |

Requires: `QMT_PATH` and `ACCOUNT_ID` in `config.yaml` or environment variables `XTQUANT_QMT_PATH` / `XTQUANT_ACCOUNT_ID`.

### show_trades.py — Trade Records

| Command | Description |
|---------|-------------|
| `python scripts/show_trades.py` | Last 100 trades |
| `python scripts/show_trades.py --strategy <name>` | Filter by strategy |
| `python scripts/show_trades.py --mode sim` | Filter by mode (sim/real/backtest) |
| `python scripts/show_trades.py --start 2024-01-01` | Filter by start date |
| `python scripts/show_trades.py --today` | Today's trades |
| `python scripts/show_trades.py --limit 50` | Limit results |

---

## Python API

### Strategy Development

Developers create new strategies by subclassing `StrategyBase` and using the `@register` decorator.

**engine/strategy_base.py:**
- `Quote` — Market data dataclass (stock_code, last_price, open, high, low, last_close, volume, amount, time)
- `Signal` — Trading signal dataclass (stock_code, side="buy"|"sell"|"skip", volume, price, reason, indicators)
- `StrategyBase(ABC)` — Base class with `on_quote(quote) -> Optional[Signal]`, `get_config_schema()`, `get_tuning_space()`, `update_params()`

**engine/strategy_registry.py:**
- `register(cls)` — Decorator to register strategy class
- `create(name, config) -> StrategyBase` — Instantiate strategy
- `list_all() -> list[str]` — All registered strategy names
- `get(name) -> StrategyBase class` — Get strategy class

**engine/indicators.py:**
- `calc_rsi(prices, period=14) -> float` — RSI (0-100)
- `calc_ma(prices, period) -> float` — Simple moving average
- `calc_ema(prices, period) -> float` — Exponential MA
- `calc_bias(price, ma) -> float` — Bias rate
- `calc_open_change(open_price, last_close) -> float` — Open gap ratio
- `calc_macd(prices, fast=12, slow=26, signal=9) -> dict` — {dif, dea, macd}
- `round_to_lot(volume, lot_size=100) -> int` — Round down to lot

### Database (db/queries.py)

All functions return `list[dict]` or `dict`. Use `json.loads()` on config/params/indicators fields.

- `register_strategy(name, display_name, config)` — Register/update strategy
- `list_strategies() -> list[dict]`
- `get_strategy(name) -> dict | None`
- `enable_strategy(name, enabled)` — Toggle strategy on/off
- `update_strategy_config(name, config)`
- `insert_trade(strategy, mode, stock_code, side, volume, price, ...)` — Insert trade record
- `get_trades(strategy=None, mode=None, start=None, end=None, stock_code=None, limit=100) -> list[dict]`
- `insert_backtest_run(data) -> str` — Insert backtest result
- `get_backtest_runs(strategy=None, limit=20) -> list[dict]`
- `get_backtest_run(run_id) -> dict | None`

### Backtest Engine (backtest/engine.py)

- `BacktestEngine().run(strategy_name, stock_code, start_date, end_date, params, initial_capital, save_to_db=True) -> dict`
  - Returns: {total_trades, final_value, return_rate, annualized_return, max_drawdown, sharpe_ratio, calmar_ratio, win_rate, equity_curve, trades, run_id}

### Trades (trade/)

- `FeeCalculator(...).calc_trade_cost(price, volume, side) -> TradeCost`
- `SimExecutor(initial_capital).place_order(stock_code, side, volume, price) -> dict`
- `RealExecutor(qmt_path, account_id).initialize() / place_order() / get_account() / get_positions()`
- `Broker(executor, mode="sim").handle_signal(signal, strategy_name) -> dict`
- `QuotePump().subscribe(stock_codes) / on_quote(callback) / stop()`
