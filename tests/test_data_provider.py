from backtest.data_provider import DataProvider


class TestDataProvider:
    def test_synthetic_fallback(self):
        p = DataProvider(cache_dir="/tmp/test_bt_cache")
        df = p.get_kline("999999.SH", "20230101", "20231231")
        assert df is not None
        assert len(df) > 100
        assert "close" in df.columns
        assert "open" in df.columns
        assert "time" in df.columns
