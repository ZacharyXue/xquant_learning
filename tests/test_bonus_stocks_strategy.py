from datetime import datetime
from engine.strategy_base import Quote
from strategies.bonus_stocks import BonusStocksStrategy


def test_watched_stocks():
    s = BonusStocksStrategy()
    assert "510880.SH" in s.watched_stocks

def test_non_investment_day_returns_none():
    s = BonusStocksStrategy()
    s._price_history = {}
    q = Quote(stock_code="510880.SH", last_price=3.45, open=3.40,
              last_close=3.42, time=datetime(2024, 1, 8, 10, 30))
    assert s.on_quote(q) is None

def test_config_schema():
    s = BonusStocksStrategy()
    schema = s.get_config_schema()
    assert "rsi_period" in schema["properties"]

def test_tuning_space():
    s = BonusStocksStrategy()
    space = s.get_tuning_space()
    param_names = [p["name"] for p in space]
    assert "rsi_period" in param_names

def test_update_params():
    s = BonusStocksStrategy()
    s.update_params({"rsi_period": 21, "base_volume": 1000})
    assert s.rsi_period == 21
    assert s.base_volume == 1000
