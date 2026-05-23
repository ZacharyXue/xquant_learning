"""
历史数据提供器

优先使用 xtquant (QMT) 获取真实数据，跨平台时回退 akshare。
两者均不可用时使用合成数据 (随机游走) 保证回测功能可用。
"""

from datetime import datetime, timedelta
from typing import Optional

import numpy as np
import pandas as pd

from backend.core.logging import get_logger

logger = get_logger("data_provider")


class DataProvider:
    """历史数据提供器"""

    def __init__(self, prefer: str = "xtquant"):
        self._prefer = prefer

    def get_kline(
        self,
        stock_code: str,
        start_time: str,
        end_time: str,
        fields: list[str] = None,
        period: str = "1d",
    ) -> Optional[pd.DataFrame]:
        """获取历史K线数据

        Args:
            stock_code: 股票代码
            start_time: 开始日期 YYYYMMDD
            end_time: 结束日期 YYYYMMDD
            fields: 字段列表
            period: 周期

        Returns:
            DataFrame with columns: time, close, open, high, low, volume
        """
        if fields is None:
            fields = ["close", "open", "high", "low", "volume"]

        # 优先 xtquant
        if self._prefer == "xtquant":
            data = self._from_xtquant(stock_code, start_time, end_time, fields, period)
            if data is not None and len(data) > 0:
                return data

        # 回退 akshare
        logger.info(f"Falling back to akshare for {stock_code}")
        data = self._from_akshare(stock_code, start_time, end_time, period)
        if data is not None and len(data) > 0:
            return data

        # 最终回退: 合成数据
        logger.warning(f"Both xtquant and akshare unavailable, using synthetic data for {stock_code}")
        return self._synthetic(stock_code, start_time, end_time)

    def _from_xtquant(
        self, stock_code: str, start_time: str, end_time: str,
        fields: list[str], period: str,
    ) -> Optional[pd.DataFrame]:
        """从 xtquant 获取数据"""
        import sys as _sys
        import os as _os

        # 确保 QMT SDK 路径在 sys.path 中 (即使 XTQUANT_TESTING=1)
        _qmt_sp = r"D:\国金证券QMT交易端\bin.x64\Lib\site-packages"
        if _os.path.isdir(_qmt_sp) and _qmt_sp not in _sys.path:
            _sys.path.append(_qmt_sp)

        try:
            from xtquant import xtdata

            # 确保数据已下载到本地缓存
            try:
                xtdata.download_history_data(
                    stock_code=stock_code,
                    period=period,
                    start_time=start_time,
                    end_time=end_time,
                )
            except Exception:
                pass  # 下载失败不影响读取已有缓存

            data = xtdata.get_market_data(
                field_list=fields,
                stock_list=[stock_code],
                start_time=start_time,
                end_time=end_time,
                period=period,
            )

            if not data:
                return None

            # 构建 DataFrame
            result = {}
            for field in fields:
                if field in data:
                    df = data[field]
                    if isinstance(df, pd.DataFrame) and stock_code in df.index:
                        series = df.loc[stock_code].dropna()
                        result[field] = series.values

            if "close" not in result or len(result["close"]) == 0:
                return None

            # Build DataFrame
            dates = _generate_trading_dates(start_time, end_time)
            df_data = {"time": dates[:len(result["close"])]}
            for field in fields:
                df_data[field] = list(result.get(field, []))[:len(df_data["time"])]

            df = pd.DataFrame(df_data)
            logger.info(f"xtquant: {stock_code} {len(df)} rows ({start_time}-{end_time})")
            return df

        except ImportError:
            return None
        except Exception as e:
            logger.warning(f"xtquant data failed for {stock_code}: {e}")
            return None

    def _from_akshare(
        self, stock_code: str, start_time: str, end_time: str, period: str,
    ) -> Optional[pd.DataFrame]:
        """从 akshare 获取数据"""
        try:
            import akshare as ak

            # Convert stock code to akshare format
            code = stock_code.replace(".SH", "").replace(".SZ", "")
            market = "sh" if ".SH" in stock_code else "sz"

            start = f"{start_time[:4]}-{start_time[4:6]}-{start_time[6:8]}"
            end = f"{end_time[:4]}-{end_time[4:6]}-{end_time[6:8]}"

            if period == "1d":
                df = ak.stock_zh_a_hist(symbol=code, period="daily", start_date=start, end_date=end, adjust="qfq")
                if df is None or len(df) == 0:
                    return None

                df = df.rename(columns={
                    "日期": "time", "收盘": "close", "开盘": "open",
                    "最高": "high", "最低": "low", "成交量": "volume",
                })
                df["time"] = df["time"].astype(str).str.replace("-", "")
                return df[["time", "close", "open", "high", "low", "volume"]]

        except ImportError:
            logger.warning("akshare not installed")
        except Exception as e:
            logger.warning(f"akshare data failed for {stock_code}: {e}")

        return None

    def _synthetic(
        self, stock_code: str, start_time: str, end_time: str,
    ) -> pd.DataFrame:
        """生成合成K线数据 (随机游走)

        根据股票代码设置合理的起始价格和波动率。
        使用代码+日期作为种子，确保同代码同日期可复现。
        """
        dates = _generate_trading_dates(start_time, end_time)
        n = len(dates)
        if n == 0:
            return pd.DataFrame()

        # 根据代码类型估算初始价格
        code = stock_code.replace(".SH", "").replace(".SZ", "")
        if code.startswith("51") or code.startswith("15"):
            # ETF: 通常在 0.5-5 元范围
            base_price = float(code[-3:]) / 100.0 + 1.0
            base_price = max(0.8, min(6.0, base_price))
            daily_vol = 0.008
        elif code.startswith("00") or code.startswith("30"):
            base_price = 15.0
            daily_vol = 0.018
        elif code.startswith("60"):
            base_price = 25.0
            daily_vol = 0.016
        else:
            base_price = 10.0
            daily_vol = 0.015

        # 基于股票代码和日期范围的确定性种子
        seed_val = hash(stock_code + start_time + end_time) % (2 ** 31)
        rng = np.random.RandomState(seed_val)

        # 随机游走生成收盘价
        returns = rng.normal(0.0002, daily_vol, n)
        log_prices = np.log(base_price) + np.cumsum(returns)
        closes = np.exp(log_prices)

        # 根据收盘价生成 OHLC
        opens = closes * (1 + rng.normal(0, 0.005, n))
        highs = np.maximum(opens, closes) * (1 + np.abs(rng.normal(0, 0.008, n)))
        lows = np.minimum(opens, closes) * (1 - np.abs(rng.normal(0, 0.008, n)))
        volumes = rng.randint(500000, 5000000, n).astype(float)

        df = pd.DataFrame({
            "time": dates,
            "close": closes,
            "open": opens,
            "high": highs,
            "low": lows,
            "volume": volumes,
        })
        logger.info(f"Synthetic: {stock_code} {n} rows ({start_time}-{end_time}), base={base_price:.2f}")
        return df


def _generate_trading_dates(start: str, end: str) -> list[str]:
    """生成交易日列表"""
    start_dt = datetime.strptime(start, "%Y%m%d")
    end_dt = datetime.strptime(end, "%Y%m%d")
    dates = []
    current = start_dt
    while current <= end_dt:
        if current.weekday() < 5:
            dates.append(current.strftime("%Y%m%d"))
        current += timedelta(days=1)
    return dates


def calculate_date_range(duration: str) -> tuple[str, str]:
    """根据回测时长计算日期范围"""
    end = datetime.now()
    end_str = end.strftime("%Y%m%d")

    if duration.endswith("m"):
        months = int(duration[:-1])
        start = end - timedelta(days=months * 30)
    elif duration.endswith("y"):
        years = int(duration[:-1])
        start = end - timedelta(days=years * 365)
    else:
        start = end - timedelta(days=30)

    return start.strftime("%Y%m%d"), end_str
