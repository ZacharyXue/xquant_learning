"""
历史数据获取模块

优先使用 xtquant (QMT) 获取真实数据，无数据时使用模拟数据
"""

from datetime import datetime, timedelta
from typing import Optional
import random
import hashlib


def get_historical_kline(
    stock_code: str,
    start_time: str,
    end_time: str,
    fields: list[str] = None,
    period: str = "1d"
) -> dict:
    """
    获取历史K线数据

    Args:
        stock_code: 股票代码，如 "515650.SH"
        start_time: 开始时间，格式 YYYYMMDD
        end_time: 结束时间，格式 YYYYMMDD
        fields: 要获取的字段列表
        period: K线周期，默认 '1d'

    Returns:
        dict: {field: [values]} 格式的历史数据
    """
    if fields is None:
        fields = ["close", "open", "high", "low", "volume"]

    # 优先尝试 xtquant
    data = try_xtquant(stock_code, start_time, end_time, fields)
    if data and data.get("close"):
        return data

    # xtquant 无数据时使用模拟数据
    print(f"使用模拟数据: {stock_code}")
    return generate_mock_data(stock_code, start_time, end_time, fields)


def try_xtquant(stock_code: str, start_time: str, end_time: str, fields: list[str]) -> dict:
    """尝试使用 xtquant 获取数据"""
    result = {}
    dates = generate_date_range(start_time, end_time)
    result["time"] = dates

    try:
        import xtquant.xtdata as xtdata
        import pandas as pd

        data = xtdata.get_market_data(
            field_list=fields,
            stock_list=[stock_code],
            start_time=start_time,
            end_time=end_time,
            period=period
        )

        for field in fields:
            if field in data:
                df = data[field]
                if isinstance(df, pd.DataFrame) and stock_code in df.index:
                    series = df.loc[stock_code].dropna()
                    result[field] = series.tolist()
                else:
                    result[field] = []
            else:
                result[field] = []

        if result.get("close") and len(result["close"]) > 0:
            print(f"xtquant 获取 {stock_code} {len(result['close'])} 条数据")
            return result

    except Exception as e:
        pass

    return {}


def generate_date_range(start_time: str, end_time: str) -> list[str]:
    """生成日期范围 (工作日)"""
    start = datetime.strptime(start_time, "%Y%m%d")
    end = datetime.strptime(end_time, "%Y%m%d")
    days = []
    current = start
    while current <= end:
        if current.weekday() < 5:  # 工作日
            days.append(current.strftime("%Y%m%d"))
        current += timedelta(days=1)
    return days


def generate_mock_data(stock_code: str, start_time: str, end_time: str, fields: list[str]) -> dict:
    """
    生成模拟数据用于演示（当 QMT 无数据时）

    注意: 这是模拟数据，供参考
    """
    # 用股票代码和时间生成种子，保证每次运行数据相同
    seed_str = f"{stock_code}_{start_time}_{end_time}"
    seed = int(hashlib.md5(seed_str.encode()).hexdigest()[:8], 16) % 10000
    random.seed(seed)

    # 生成交易日
    dates = generate_date_range(start_time, end_time)
    if not dates:
        return {}

    # 基础价格和波动率
    base_price = 3.0 if ".SH" in stock_code or ".SZ" in stock_code else 10.0
    volatility = 0.02

    n = len(dates)
    result = {"time": dates}

    for field in fields:
        if field == "close":
            prices = []
            price = base_price
            for _ in range(n):
                change = random.uniform(-volatility, volatility)
                price = price * (1 + change)
                prices.append(round(price, 4))
            result["close"] = prices

        elif field == "open":
            result["open"] = [
                round(result["close"][i] * (1 + random.uniform(-0.005, 0.005)), 4
            ]
            for i in range(n)
        ]

        elif field == "high":
            result["high"] = [
                round(
                    max(result["open"][i], result["close"][i]) * (1 + random.uniform(0, 0.01)), 4
            )
            for i in range(n)
        ]

        elif field == "low":
            result["low"] = [
                round(
                    min(result["open"][i], result["close"][i]) * (1 - random.uniform(0, 0.01)), 4
            )
            for i in range(n)
        ]

        elif field == "volume":
            result["volume"] = [random.randint(10000, 100000) for _ in range(n)]

    return result


def get_stock_info(stock_code: str) -> Optional[dict]:
    """获取股票基本信息"""
    try:
        import xtquant.xtdata as xtdata

        info = xtdata.get_stock_info(stock_code)
        if info:
            return {
                "name": info.get("name", ""),
                "market": info.get("market", ""),
            }
        return None
    except Exception:
        return None


def calculate_date_range(duration: str) -> tuple[str, str]:
    """根据回测时长计算日期范围"""
    end_time = datetime.now()
    end_str = end_time.strftime("%Y%m%d")

    if duration.endswith("m"):
        months = int(duration[:-1])
        start_time = end_time - timedelta(days=months * 30)
    elif duration.endswith("y"):
        years = int(duration[:-1])
        start_time = end_time - timedelta(days=years * 365)
    else:
        start_time = end_time - timedelta(days=30)

    start_str = start_time.strftime("%Y%m%d")
    return start_str, end_str