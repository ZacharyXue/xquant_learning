# AGENTS.md

AI programming assistant (opencode) work guide. Contains local environment paths, common commands, and code conventions.

> Interface documentation: [docs/API_REFERENCE.md](docs/API_REFERENCE.md)
> Troubleshooting log: [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)

---

## CRITICAL

**AI MUST read `docs/API_REFERENCE.md` before executing any trade, backtest, or data query task.**
Interface changes **MUST** synchronize updates to `docs/API_REFERENCE.md`.

---

## Local Development Environment

### Python

| Item | Value |
|------|-------|
| Python version | 3.11.9 (64-bit) |
| Python path | `F:\Codes\Python311-64\python.exe` |
| Virtual env | `F:\Codes\xtquant_learning\.venv` |
| Virtual env Python | `.venv\Scripts\python.exe` |
| Activate command | `.venv\Scripts\Activate.ps1` |

### QMT / xtquant

| Item | Value |
|------|-------|
| QMT install path | `D:\国金证券QMT交易端` |
| xtquant SDK path | `D:\国金证券QMT交易端\bin.x64\Lib\site-packages\xtquant` |
| Broker | 国金证券 |
| Status | xtdata/xttrader available when QMT client is running |

### Database

| Item | Value |
|------|-------|
| Type | SQLite |
| Path | `data/xtquant.db` |
| Init | `python scripts/manage.py --init` |

---

## WSL2 Tips

| Windows | WSL2 |
|---------|------|
| `F:\Codes\xtquant_learning\` | `/mnt/f/Codes/xtquant_learning/` |
| `.venv\Scripts\python.exe` | `/mnt/f/Codes/xtquant_learning/.venv/Scripts/python.exe` |

---

## Common Commands

### Setup

```bash
# Install deps
.venv/Scripts/python.exe -m pip install -r requirements.txt

# Initialize database + register strategies
.venv/Scripts/python.exe scripts/manage.py --init
```

### Strategy Management

```bash
.venv/Scripts/python.exe scripts/manage.py --list
.venv/Scripts/python.exe scripts/manage.py --show bonus_stocks
.venv/Scripts/python.exe scripts/manage.py --enable bonus_stocks
.venv/Scripts/python.exe scripts/manage.py --set bonus_stocks --param base_volume=1000
```

### Backtest

```bash
.venv/Scripts/python.exe scripts/run_backtest.py --strategy bonus_stocks --start 20220101 --end 20241231
.venv/Scripts/python.exe scripts/run_backtest.py --strategy bonus_stocks --start 20220101 --end 20241231 --optimize --target max_sharpe
.venv/Scripts/python.exe scripts/run_backtest.py --list
.venv/Scripts/python.exe scripts/run_backtest.py --show <run_id>
```

### Simulated Trading

```bash
.venv/Scripts/python.exe scripts/run_sim.py
.venv/Scripts/python.exe scripts/run_sim.py --strategy bonus_stocks
```

### Real Trading (QMT required)

```bash
# Set env vars or config.yaml
$env:XTQUANT_QMT_PATH="D:\国金证券QMT交易端\userdata_mini"
$env:XTQUANT_ACCOUNT_ID="your_account_id"
.venv/Scripts/python.exe scripts/run_real.py
```

### Trade Records

```bash
.venv/Scripts/python.exe scripts/show_trades.py --today
.venv/Scripts/python.exe scripts/show_trades.py --strategy bonus_stocks --mode backtest
```

### Testing

```bash
# Full test suite
$env:XTQUANT_TESTING="1"; .venv/Scripts/python.exe -m pytest tests/ -v
```

---

## Code Conventions

- Commit: conventional commits, do NOT auto-push
- Python: snake_case / PascalCase / full type annotations
- Logging: use `import logging; logger = logging.getLogger(__name__)`, no `print`
- Config: from `config.yaml`, no hardcoding
- Sensitive data: qmt_path / account_id via environment variables

### Strategy Development

New strategies MUST:
1. Subclass `StrategyBase`
2. Use `@register` decorator
3. Define `name`, `display_name`, `watched_stocks` class attributes
4. Implement `on_quote(self, quote: Quote) -> Optional[Signal]`
5. Implement `get_config_schema()` returning JSON Schema
6. Implement `get_tuning_space()` for grid search support
7. Place file in `strategies/` directory

```python
from engine.strategy_base import StrategyBase, Quote, Signal
from engine.strategy_registry import register

@register
class MyStrategy(StrategyBase):
    name = "my_strategy"
    display_name = "My Strategy"
    watched_stocks = ["000001.SZ"]

    def on_quote(self, quote: Quote) -> Optional[Signal]:
        ...

    def get_config_schema(self) -> dict:
        return {"type": "object", "properties": {...}}

    def get_tuning_space(self) -> list[dict]:
        return [{"name": "param", "type": "int", "min": 1, "max": 100, "step": 1}]
```

---

## Tech Stack

| Layer | Tech |
|-------|------|
| Language | Python 3.11 |
| Data | numpy, pandas |
| Persistence | SQLite (stdlib sqlite3) |
| Config | pyyaml |
| Trading SDK | xtquant (QMT, Windows only) |
| Testing | pytest |
