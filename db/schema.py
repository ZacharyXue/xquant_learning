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
