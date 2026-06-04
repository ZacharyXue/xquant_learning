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
