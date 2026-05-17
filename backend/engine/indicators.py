"""
技术指标库

提供常用的技术指标计算函数。
"""

from typing import Optional

import pandas as pd
import numpy as np


def calc_rsi(prices: list[float], period: int = 14) -> float:
    """计算 RSI (相对强弱指标)

    Args:
        prices: 价格序列 (按时间升序)
        period: 计算周期

    Returns:
        RSI 值 (0-100)，数据不足返回 50 (中性)
    """
    if len(prices) < period + 1:
        return 50.0

    series = pd.Series(prices)
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)

    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()

    rs = avg_gain.iloc[-1] / avg_loss.iloc[-1] if avg_loss.iloc[-1] > 0 else 100.0
    rsi = 100.0 - (100.0 / (1.0 + rs))
    return round(rsi, 2)


def calc_ma(prices: list[float], period: int = 20) -> float:
    """计算简单移动平均线"""
    if len(prices) < period:
        return sum(prices) / len(prices) if prices else 0.0
    return round(sum(prices[-period:]) / period, 4)


def calc_ema(prices: list[float], period: int = 20) -> float:
    """计算指数移动平均线"""
    if len(prices) < 2:
        return prices[-1] if prices else 0.0
    series = pd.Series(prices)
    return round(series.ewm(span=period, adjust=False).mean().iloc[-1], 4)


def calc_bias(price: float, ma: float) -> float:
    """计算乖离率

    Returns:
        乖离率 (如 0.05 表示 5% 正乖离)
    """
    if ma <= 0:
        return 0.0
    return round((price - ma) / ma, 6)


def calc_open_change(open_price: float, last_close: float) -> float:
    """计算开盘变化率"""
    if last_close <= 0:
        return 0.0
    return round((open_price - last_close) / last_close, 6)


def calc_macd(
    prices: list[float],
    fast: int = 12, slow: int = 26, signal: int = 9,
) -> dict:
    """计算 MACD"""
    if len(prices) < slow + signal:
        return {"dif": 0.0, "dea": 0.0, "macd": 0.0}
    series = pd.Series(prices)
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    dif = ema_fast - ema_slow
    dea = dif.ewm(span=signal, adjust=False).mean()
    macd = 2 * (dif - dea)
    return {
        "dif": round(dif.iloc[-1], 6),
        "dea": round(dea.iloc[-1], 6),
        "macd": round(macd.iloc[-1], 6),
    }


def calc_volatility(prices: list[float], period: int = 20) -> float:
    """计算历史波动率 (年化)"""
    if len(prices) < period + 1:
        return 0.0
    returns = np.diff(np.log(prices[-period - 1:]))
    daily_vol = np.std(returns)
    annual_vol = daily_vol * np.sqrt(252)
    return round(annual_vol, 6)


def round_to_lot(volume: int, lot_size: int = 100) -> int:
    """向下取整到手数"""
    return (volume // lot_size) * lot_size
