"""
策略工具函数模块

提供可复用的技术指标计算和辅助函数
"""

from datetime import datetime
from typing import Optional


def is_trading_time(now: datetime) -> bool:
    """
    检查当前是否在正常交易时间

    Args:
        now: 当前时间

    Returns:
        bool: 是否在交易时间内 (9:30-14:55)
    """
    if now.hour < 9 or (now.hour == 9 and now.minute < 30):
        return False
    if now.hour > 14 or (now.hour == 14 and now.minute >= 55):
        return False
    return True


def is_investment_day(now: datetime, investment_days: list[str]) -> bool:
    """
    检查当前是否为定投日

    Args:
        now: 当前时间
        investment_days: 定投日列表，支持中英文，如 ["周三", "Wednesday", "周五"]

    Returns:
        bool: 是否为定投日
    """
    # 中文和英文映射
    chinese_names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    english_short = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    english_full = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    weekday = now.weekday()

    today_variants = {
        chinese_names[weekday],
        english_short[weekday],
        english_full[weekday],
    }

    for day in investment_days:
        if day in today_variants:
            return True
        if day.lower() == english_full[weekday].lower():
            return True
    return False


def should_skip_log(now: datetime, investment_days: list[str] = None) -> bool:
    """
    检查是否应该跳过非买入时段的日志记录（避免日志过多）

    Args:
        now: 当前时间
        investment_days: 定投日列表（可选）

    Returns:
        bool: 是否应该跳过日志
    """
    # 非交易时间跳过
    if not is_trading_time(now):
        return True
    # 如果指定了定投日，非定投日跳过详细日志
    if investment_days and not is_investment_day(now, investment_days):
        return True
    return False


def calculate_rsi(prices: list[float], period: int = 14) -> Optional[float]:
    """
    计算相对强弱指数 (RSI)

    RSI = 100 - (100 / (1 + RS))
    RS = 平均涨幅 / 平均跌幅

    Args:
        prices: 价格序列（应该包含足够的历史数据）
        period: 计算周期，默认14

    Returns:
        float: RSI值 (0-100)，如果数据不足返回None
    """
    if len(prices) < period + 1:
        return None

    # 计算价格变化
    deltas = []
    for i in range(1, len(prices)):
        deltas.append(prices[i] - prices[i - 1])

    # 分离涨跌
    gains = [d if d > 0 else 0 for d in deltas[-period:]]
    losses = [-d if d < 0 else 0 for d in deltas[-period:]]

    # 计算平均涨跌幅
    avg_gain = sum(gains) / period if gains else 0
    avg_loss = sum(losses) / period if losses else 0

    # 避免除零
    if avg_loss == 0:
        if avg_gain == 0:
            return 50.0  # 完全中性
        return 100.0  # 持续上涨

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))

    return rsi


def calculate_ma(prices: list[float], period: int) -> Optional[float]:
    """
    计算简单移动平均线 (SMA)

    Args:
        prices: 价格序列
        period: 周期

    Returns:
        float: 移动平均值，如果数据不足返回None
    """
    if len(prices) < period:
        return None
    return sum(prices[-period:]) / period


def calculate_bias_rate(
    current_price: float,
    ma_price: float
) -> float:
    """
    计算乖离率

    乖离率 = (现价 - 均线) / 均线

    Args:
        current_price: 当前价格
        ma_price: 均线价格

    Returns:
        float: 乖离率
    """
    if ma_price <= 0:
        return 0.0
    return (current_price - ma_price) / ma_price


def calculate_open_change_ratio(
    open_price: float,
    last_close: float
) -> float:
    """
    计算开盘价相比前收盘的涨幅

    Args:
        open_price: 开盘价
        last_close: 前一日收盘价

    Returns:
        float: 涨幅比例 (如 0.01 表示上涨1%)
    """
    if last_close <= 0:
        return 0.0
    return (open_price - last_close) / last_close


def round_to_lot_size(volume: int, lot_size: int = 100) -> int:
    """
    将数量调整为交易单位的整数倍

    Args:
        volume: 原始数量
        lot_size: 交易单位，默认100（A股）

    Returns:
        int: 调整后的数量
    """
    if volume <= 0:
        return 0
    return (volume // lot_size) * lot_size
