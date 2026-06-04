"""Historical data provider — xtquant > akshare > parquet cache > synthetic"""

import os
import time
from datetime import datetime, timedelta
from typing import Optional

import numpy as np
import pandas as pd

CACHE_DIR = "data/cache/klines"
CACHE_TTL = 86400


class DataProvider:
    def __init__(self, cache_dir: str = CACHE_DIR, cache_ttl: int = CACHE_TTL):
        self._cdir = cache_dir
        self._cttl = cache_ttl
        os.makedirs(cache_dir, exist_ok=True)

    def get_kline(
        self, stock_code: str, start_date: str, end_date: str, fields: list[str] = None
    ) -> Optional[pd.DataFrame]:
        if fields is None:
            fields = ["close", "open", "high", "low", "volume"]
        df = self._cache_get(stock_code, start_date, end_date)
        if df is not None:
            return self._filter(df, fields)
        df = self._try_xtquant(stock_code, start_date, end_date)
        if df is not None and len(df) > 0:
            self._cache_set(stock_code, start_date, end_date, df)
            return self._filter(df, fields)
        df = self._try_akshare(stock_code, start_date, end_date)
        if df is not None and len(df) > 0:
            self._cache_set(stock_code, start_date, end_date, df)
            return self._filter(df, fields)
        df = self._synthetic(stock_code, start_date, end_date)
        return self._filter(df, fields)

    def _ckey(self, code, s, e):
        return f"{code.replace('.', '_')}_{s}_{e}.parquet"

    def _cache_get(self, c, s, e):
        p = os.path.join(self._cdir, self._ckey(c, s, e))
        if not os.path.exists(p):
            return None
        if time.time() - os.path.getmtime(p) > self._cttl:
            os.remove(p)
            return None
        try:
            return pd.read_parquet(p)
        except Exception:
            return None

    def _cache_set(self, c, s, e, df):
        try:
            df.to_parquet(os.path.join(self._cdir, self._ckey(c, s, e)), index=False)
        except Exception:
            pass

    def _try_xtquant(self, code, start, end):
        try:
            import xtquant.xtdata as xtdata
        except ImportError:
            return None
        try:
            xtdata.download_history_data(code, period="1d", start_time=start, end_time=end)
            data = xtdata.get_market_data(
                field_list=["close", "open", "high", "low", "volume"],
                stock_list=[code],
                start_time=start,
                end_time=end,
                period="1d",
            )
            if data and "close" in data and code in data["close"].index:
                close_s = data["close"].loc[code]
                df = pd.DataFrame({"close": close_s})
                for f in ["open", "high", "low", "volume"]:
                    if f in data and code in data[f].index:
                        df[f] = data[f].loc[code]
                df = df.dropna(subset=["close"]).reset_index()
                df = df.rename(columns={"index": "time"})
                df["time"] = df["time"].astype(str)
                return df
        except Exception:
            return None
        return None

    def _try_akshare(self, code, start, end):
        try:
            import akshare as ak
        except ImportError:
            return None
        try:
            sym = code.split(".")[0]
            df = ak.stock_zh_a_hist(
                symbol=sym,
                period="daily",
                start_date=start.replace("-", "")[:8],
                end_date=end.replace("-", "")[:8],
                adjust="qfq",
            )
            if df is None or len(df) == 0:
                return None
            df = df.rename(
                columns={
                    "日期": "time",
                    "开盘": "open",
                    "收盘": "close",
                    "最高": "high",
                    "最低": "low",
                    "成交量": "volume",
                }
            )
            df["time"] = df["time"].astype(str)
            for c in ["open", "high", "low", "close"]:
                df[c] = pd.to_numeric(df[c], errors="coerce")
            df = df.dropna(subset=["close"])
            return df[["time", "open", "high", "low", "close", "volume"]]
        except Exception:
            return None

    def _synthetic(self, code, start, end):
        sd = datetime.strptime(start[:8], "%Y%m%d")
        ed = datetime.strptime(end[:8], "%Y%m%d")
        days = min((ed - sd).days, 1500)
        cl = hash(code) % 2**31
        if cl < 0:
            cl += 2**31
        np.random.seed(cl)
        ret = np.random.normal(0.0003, 0.015, days)
        close = 10.0 * np.exp(np.cumsum(ret))
        dates = []
        cur = sd
        while len(dates) < days:
            if cur.weekday() < 5:
                dates.append(cur.strftime("%Y%m%d"))
            cur += timedelta(days=1)
        return pd.DataFrame(
            {
                "time": dates[:days],
                "close": close,
                "open": close * np.random.uniform(0.99, 1.01, days),
                "high": close * np.random.uniform(1.00, 1.02, days),
                "low": close * np.random.uniform(0.98, 1.00, days),
                "volume": np.random.randint(10**5, 10**7, days).astype(int),
            }
        )

    def _filter(self, df, fields):
        avail = [f for f in fields if f in df.columns]
        if "time" in df.columns and "time" not in avail:
            avail = ["time"] + avail
        return df[avail]
