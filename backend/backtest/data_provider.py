"""
历史数据提供器

优先使用 xtquant (QMT) 获取真实数据，跨平台时回退 akshare。
彻底移除 mock 随机数据。
"""

from datetime import datetime, timedelta
from typing import Optional

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
        return self._from_akshare(stock_code, start_time, end_time, period)

    def _from_xtquant(
        self, stock_code: str, start_time: str, end_time: str,
        fields: list[str], period: str,
    ) -> Optional[pd.DataFrame]:
        """从 xtquant 获取数据"""
        try:
            from xtquant import xtdata

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
