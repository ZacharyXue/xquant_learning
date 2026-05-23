"""
A股交易日历

提供交易日判断、交易时间判断等工具函数。
"""

from datetime import date, datetime, time
from typing import Optional

import pandas as pd

# 常用交易时段
TRADING_AM_START = time(9, 30)
TRADING_AM_END = time(11, 30)
TRADING_PM_START = time(13, 0)
TRADING_PM_END = time(15, 0)

CALL_AUCTION_END = time(9, 25)
CLOSE_CANCEL_TIME = time(14, 50)

# 中国工作日名称映射
_WEEKDAY_MAP = {
    "monday": 0, "mon": 0,
    "tuesday": 1, "tue": 1,
    "wednesday": 2, "wed": 2,
    "thursday": 3, "thu": 3,
    "friday": 4, "fri": 4,
    "saturday": 5, "sat": 5,
    "sunday": 6, "sun": 6,
    "周一": 0, "星期一": 0,
    "周二": 1, "星期二": 1,
    "周三": 2, "星期三": 2,
    "周四": 3, "星期四": 3,
    "周五": 4, "星期五": 4,
    "周六": 5, "星期六": 5,
    "周日": 6, "星期日": 6,
}


def is_weekday(dt: Optional[datetime] = None) -> bool:
    """判断是否为工作日 (周一到周五)"""
    if dt is None:
        dt = datetime.now()
    return dt.weekday() < 5


def is_trading_time(dt: Optional[datetime] = None) -> bool:
    """判断是否在连续竞价交易时段"""
    if dt is None:
        dt = datetime.now()
    if not is_weekday(dt):
        return False
    t = dt.time()
    return (TRADING_AM_START <= t <= TRADING_AM_END) or (
        TRADING_PM_START <= t <= TRADING_PM_END
    )


def is_cancel_time(dt: Optional[datetime] = None) -> bool:
    """判断是否到收盘撤单时间"""
    if dt is None:
        dt = datetime.now()
    t = dt.time()
    return t >= CLOSE_CANCEL_TIME


def is_investment_day(dt: Optional[datetime] = None, days: list[str] = None) -> bool:
    """判断是否为定投日"""
    if dt is None:
        dt = datetime.now()
    if days is None:
        return False
    weekday = dt.weekday()
    for day in days:
        day_lower = day.strip().lower()
        if day_lower in _WEEKDAY_MAP and _WEEKDAY_MAP[day_lower] == weekday:
            return True
    return False


def next_trading_day(dt: Optional[date] = None) -> date:
    """获取下一个交易日"""
    if dt is None:
        dt = date.today()
    while True:
        dt = dt + pd.Timedelta(days=1)
        if dt.weekday() < 5:
            return dt
