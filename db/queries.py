"""Database query interface"""

import json
from typing import Optional

from db.database import get_conn, transaction


def _row_to_dict(row) -> Optional[dict]:
    if row is None:
        return None
    return dict(row)


def _rows_to_dicts(rows) -> list[dict]:
    return [dict(row) for row in rows]


# ── Strategy CRUD ──────────────────────────────────────────────────────────

def register_strategy(name: str, display_name: str = "", config: dict = None):
    with transaction() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO strategies (name, display_name, config) VALUES (?, ?, ?)",
            (name, display_name, json.dumps(config or {}, ensure_ascii=False)),
        )


def list_strategies() -> list[dict]:
    conn = get_conn()
    try:
        rows = conn.execute("SELECT * FROM strategies ORDER BY name").fetchall()
        return _rows_to_dicts(rows)
    finally:
        conn.close()


def get_strategy(name: str) -> Optional[dict]:
    conn = get_conn()
    try:
        row = conn.execute("SELECT * FROM strategies WHERE name = ?", (name,)).fetchone()
        return _row_to_dict(row)
    finally:
        conn.close()


def enable_strategy(name: str, enabled: bool):
    with transaction() as conn:
        conn.execute(
            "UPDATE strategies SET enabled = ? WHERE name = ?",
            (int(enabled), name),
        )


def update_strategy_config(name: str, config: dict):
    with transaction() as conn:
        conn.execute(
            "UPDATE strategies SET config = ? WHERE name = ?",
            (json.dumps(config, ensure_ascii=False), name),
        )


# ── Trade Records ──────────────────────────────────────────────────────────

def insert_trade(
    strategy: str,
    mode: str,
    stock_code: str,
    side: str,
    volume: int,
    price: float,
    commission: float = 0,
    stamp_tax: float = 0,
    transfer_fee: float = 0,
    slippage: float = 0,
    total_cost: float = 0,
    reason: str = "",
    indicators: dict = None,
    trade_time: str = "",
):
    with transaction() as conn:
        conn.execute(
            """INSERT INTO trade_records
               (strategy, mode, stock_code, side, volume, price,
                commission, stamp_tax, transfer_fee, slippage, total_cost,
                reason, indicators, trade_time)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                strategy, mode, stock_code, side, volume, price,
                commission, stamp_tax, transfer_fee, slippage, total_cost,
                reason, json.dumps(indicators or {}, ensure_ascii=False), trade_time,
            ),
        )


def get_trades(
    strategy: str = None,
    mode: str = None,
    start: str = None,
    end: str = None,
    stock_code: str = None,
    limit: int = 100,
) -> list[dict]:
    conn = get_conn()
    try:
        query = "SELECT * FROM trade_records WHERE 1=1"
        params = []

        if strategy is not None:
            query += " AND strategy = ?"
            params.append(strategy)
        if mode is not None:
            query += " AND mode = ?"
            params.append(mode)
        if stock_code is not None:
            query += " AND stock_code = ?"
            params.append(stock_code)
        if start is not None:
            query += " AND trade_time >= ?"
            params.append(start)
        if end is not None:
            query += " AND trade_time <= ?"
            params.append(end)

        query += " ORDER BY trade_time DESC LIMIT ?"
        params.append(limit)

        rows = conn.execute(query, params).fetchall()
        return _rows_to_dicts(rows)
    finally:
        conn.close()


# ── Backtest Runs ──────────────────────────────────────────────────────────

def insert_backtest_run(data: dict):
    with transaction() as conn:
        conn.execute(
            """INSERT INTO backtest_runs
               (run_id, strategy, start_date, end_date, params,
                initial_cash, final_equity, total_return, annual_return,
                max_drawdown, sharpe_ratio, win_rate, total_trades,
                equity_curve, baseline_curve)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                data["run_id"],
                data["strategy"],
                data["start_date"],
                data["end_date"],
                json.dumps(data.get("params", {}), ensure_ascii=False),
                data.get("initial_cash", 0),
                data.get("final_equity", 0),
                data.get("total_return", 0),
                data.get("annual_return", 0),
                data.get("max_drawdown", 0),
                data.get("sharpe_ratio", 0),
                data.get("win_rate", 0),
                data.get("total_trades", 0),
                json.dumps(data.get("equity_curve", []), ensure_ascii=False),
                json.dumps(data.get("baseline_curve", []), ensure_ascii=False),
            ),
        )


def get_backtest_runs(strategy: str = None, limit: int = 20) -> list[dict]:
    conn = get_conn()
    try:
        if strategy is not None:
            rows = conn.execute(
                "SELECT * FROM backtest_runs WHERE strategy = ? ORDER BY created_at DESC LIMIT ?",
                (strategy, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM backtest_runs ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return _rows_to_dicts(rows)
    finally:
        conn.close()


def get_backtest_run(run_id: str) -> Optional[dict]:
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM backtest_runs WHERE run_id = ?", (run_id,)
        ).fetchone()
        return _row_to_dict(row)
    finally:
        conn.close()
