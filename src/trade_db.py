"""
策略交易数据库模块

记录所有策略的买入操作，支持回溯查询
"""

import json
import os
import sqlite3
import logging
from datetime import datetime
from typing import Optional, Any
from contextlib import contextmanager

# 获取日志器
logger = logging.getLogger("trade_db")


# 获取项目根目录
def get_project_root() -> str:
    """获取项目根目录"""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# 数据库路径：项目根目录下的 data/trades.db
DB_PATH = os.path.join(get_project_root(), "data", "trades.db")


def get_db_path() -> str:
    """获取数据库路径"""
    db_dir = os.path.dirname(DB_PATH)
    os.makedirs(db_dir, exist_ok=True)
    return DB_PATH


@contextmanager
def get_connection():
    """获取数据库连接"""
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    """初始化数据库表"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trade_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                strategy TEXT NOT NULL,
                stock_code TEXT NOT NULL,
                stock_name TEXT,
                trade_time TEXT NOT NULL,
                trade_type TEXT NOT NULL,
                volume INTEGER NOT NULL,
                price REAL NOT NULL,
                amount REAL NOT NULL,
                status TEXT DEFAULT 'pending',
                extra_json TEXT,
                created_at TEXT NOT NULL,
                UNIQUE(strategy, stock_code, trade_time)
            )
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_strategy_time
            ON trade_records(strategy, trade_time)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_stock_code
            ON trade_records(stock_code)
        """)


def record_trade(
    strategy: str,
    stock_code: str,
    trade_time: datetime,
    trade_type: str,
    volume: int,
    price: float,
    stock_name: str = "",
    status: str = "pending",
    extra: dict = None,
) -> int:
    """
    记录交易

    Args:
        strategy: 策略名称
        stock_code: 股票代码
        trade_time: 交易时间
        trade_type: 交易类型 (buy/sell)
        volume: 数量
        price: 价格
        stock_name: 股票名称
        status: 状态 (pending/filled/cancelled)
        extra: 额外信息 dict

    Returns:
        记录ID，失败返回 -1
    """
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO trade_records
                (strategy, stock_code, stock_name, trade_time, trade_type, volume, price,
                 amount, status, extra_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                strategy,
                stock_code,
                stock_name,
                trade_time.strftime("%Y-%m-%d %H:%M:%S"),
                trade_type,
                volume,
                price,
                volume * price,
                status,
                json.dumps(extra, ensure_ascii=False) if extra else None,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            ))
            record_id = cursor.lastrowid

            # 成功日志
            logger.info(
                f"记录交易成功: strategy={strategy}, stock={stock_code}, "
                f"type={trade_type}, volume={volume}, price={price}, "
                f"record_id={record_id}"
            )
            return record_id

    except Exception as e:
        logger.error(
            f"记录交易失败: strategy={strategy}, stock={stock_code}, "
            f"type={trade_type}, volume={volume}, price={price}, "
            f"error={str(e)}"
        )
        return -1


def update_trade_status(
    record_id: int,
    status: str,
    filled_price: float = None,
) -> bool:
    """
    更新交易状态

    Args:
        record_id: 记录ID
        status: 新状态
        filled_price: 成交价格

    Returns:
        是否成功
    """
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            if filled_price is not None:
                cursor.execute("""
                    UPDATE trade_records
                    SET status = ?, price = ?, amount = volume * ?
                    WHERE id = ?
                """, (status, filled_price, filled_price, record_id))
            else:
                cursor.execute("""
                    UPDATE trade_records
                    SET status = ?
                    WHERE id = ?
                """, (status, record_id))

            logger.info(f"更新交易状态成功: record_id={record_id}, status={status}")
            return True

    except Exception as e:
        logger.error(f"更新交易状态失败: record_id={record_id}, error={str(e)}")
        return False


def query_trades(
    strategy: str = None,
    stock_code: str = None,
    start_time: datetime = None,
    end_time: datetime = None,
    trade_type: str = None,
    status: str = None,
) -> list[dict]:
    """
    查询交易记录

    Args:
        strategy: 策略名称
        stock_code: 股票代码
        start_time: 开始时间
        end_time: 结束时间
        trade_type: 交易类型
        status: 状态

    Returns:
        记录列表
    """
    with get_connection() as conn:
        cursor = conn.cursor()

        query = "SELECT * FROM trade_records WHERE 1=1"
        params = []

        if strategy:
            query += " AND strategy = ?"
            params.append(strategy)

        if stock_code:
            query += " AND stock_code = ?"
            params.append(stock_code)

        if start_time:
            query += " AND trade_time >= ?"
            params.append(start_time.strftime("%Y-%m-%d %H:%M:%S"))

        if end_time:
            query += " AND trade_time <= ?"
            params.append(end_time.strftime("%Y-%m-%d %H:%M:%S"))

        if trade_type:
            query += " AND trade_type = ?"
            params.append(trade_type)

        if status:
            query += " AND status = ?"
            params.append(status)

        query += " ORDER BY trade_time DESC"

        cursor.execute(query, params)
        rows = cursor.fetchall()

        results = []
        for row in rows:
            result = dict(row)
            if result.get("extra_json"):
                result["extra"] = json.loads(result["extra_json"])
            else:
                result["extra"] = None
            del result["extra_json"]
            results.append(result)

        return results


def get_trade_summary(
    strategy: str = None,
    stock_code: str = None,
    start_time: datetime = None,
    end_time: datetime = None,
) -> dict:
    """
    获取交易汇总

    Args:
        strategy: 策略名称
        stock_code: 股票代码
        start_time: 开始时间
        end_time: 结束时间

    Returns:
        汇总数据
    """
    with get_connection() as conn:
        cursor = conn.cursor()

        query = """
            SELECT
                COUNT(*) as total_trades,
                SUM(CASE WHEN trade_type = 'buy' THEN volume ELSE 0 END) as total_buy_volume,
                SUM(CASE WHEN trade_type = 'sell' THEN volume ELSE 0 END) as total_sell_volume,
                SUM(CASE WHEN trade_type = 'buy' THEN amount ELSE 0 END) as total_investment,
                SUM(CASE WHEN trade_type = 'sell' THEN amount ELSE 0 END) as total_proceeds
            FROM trade_records
            WHERE trade_type IN ('buy', 'sell')
        """
        params = []

        if strategy:
            query += " AND strategy = ?"
            params.append(strategy)

        if stock_code:
            query += " AND stock_code = ?"
            params.append(stock_code)

        if start_time:
            query += " AND trade_time >= ?"
            params.append(start_time.strftime("%Y-%m-%d %H:%M:%S"))

        if end_time:
            query += " AND trade_time <= ?"
            params.append(end_time.strftime("%Y-%m-%d %H:%M:%S"))

        cursor.execute(query, params)
        row = cursor.fetchone()

        return dict(row) if row else {
            "total_trades": 0,
            "total_buy_volume": 0,
            "total_sell_volume": 0,
            "total_investment": 0,
            "total_proceeds": 0,
        }


def delete_trade(record_id: int):
    """删除交易记录"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM trade_records WHERE id = ?", (record_id,))


# === 便捷函数 ===

def record_buy(
    strategy: str,
    stock_code: str,
    volume: int,
    price: float,
    trade_time: datetime = None,
    stock_name: str = "",
    extra: dict = None,
) -> int:
    """
    记录买入 (便捷函数)

    Args:
        strategy: 策略名称
        stock_code: 股票代码
        volume: 数量
        price: 价格
        trade_time: 交易时间
        stock_name: 股票名称
        extra: 额外信息

    Returns:
        记录ID
    """
    return record_trade(
        strategy=strategy,
        stock_code=stock_code,
        trade_time=trade_time or datetime.now(),
        trade_type="buy",
        volume=volume,
        price=price,
        stock_name=stock_name,
        extra=extra,
    )


def record_sell(
    strategy: str,
    stock_code: str,
    volume: int,
    price: float,
    trade_time: datetime = None,
    stock_name: str = "",
    extra: dict = None,
) -> int:
    """
    记录卖出 (便捷函数)

    Args:
        strategy: 策略名称
        stock_code: 股票代码
        volume: 数量
        price: 价格
        trade_time: 交易时间
        stock_name: 股票名称
        extra: 额外信息

    Returns:
        记录ID
    """
    return record_trade(
        strategy=strategy,
        stock_code=stock_code,
        trade_time=trade_time or datetime.now(),
        trade_type="sell",
        volume=volume,
        price=price,
        stock_name=stock_name,
        extra=extra,
    )


def get_strategy_trades(strategy: str, days: int = 30) -> list[dict]:
    """获取策略近期交易"""
    start_time = datetime.now() - datetime.timedelta(days=days)
    return query_trades(strategy=strategy, start_time=start_time)


if __name__ == "__main__":
    # 初始化数据库
    init_db()
    print(f"数据库已初始化: {get_db_path()}")