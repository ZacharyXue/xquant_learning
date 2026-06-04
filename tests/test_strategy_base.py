import pytest
from datetime import datetime
from engine.strategy_base import Quote, Signal, StrategyBase


class TestQuote:
    def test_create_quote(self):
        q = Quote(stock_code="510880.SH", last_price=3.45, open=3.40, high=3.50,
                  low=3.38, last_close=3.42, volume=1000000, amount=3450000.0,
                  time=datetime(2024, 1, 15, 10, 30))
        assert q.stock_code == "510880.SH"
        assert q.last_price == 3.45

    def test_defaults(self):
        q = Quote(stock_code="000001.SZ", last_price=10.0)
        assert q.open == 0.0
        assert q.volume == 0


class TestSignal:
    def test_buy_signal(self):
        s = Signal(stock_code="510880.SH", side="buy", volume=500, price=3.45,
                   reason="RSI oversold", indicators={"rsi": 25.5})
        assert s.side == "buy"
        assert s.indicators["rsi"] == 25.5

    def test_defaults(self):
        s = Signal(stock_code="510880.SH", side="skip", volume=0, price=0.0)
        assert s.reason == ""
        assert s.indicators == {}


class TestStrategyBase:
    def test_subclass_must_implement_on_quote(self):
        class Bad(StrategyBase):
            name = "bad"
        with pytest.raises(TypeError):
            Bad()

    def test_valid_subclass(self):
        class Good(StrategyBase):
            name = "good"
            display_name = "Good"
            def on_quote(self, quote):
                return None
        instance = Good()
        assert instance.name == "good"
        assert instance.watched_stocks == []

    def test_update_params(self):
        class MyStrat(StrategyBase):
            name = "test"
            rsi_period = 14
            def on_quote(self, quote):
                return None
        s = MyStrat()
        s.update_params({"rsi_period": 21})
        assert s.rsi_period == 21

    def test_get_config_schema_default(self):
        class MyStrat(StrategyBase):
            name = "test"
            def on_quote(self, quote):
                return None
        s = MyStrat()
        assert s.get_config_schema() == {"type": "object", "properties": {}}

    def test_get_tuning_space_default(self):
        class MyStrat(StrategyBase):
            name = "test"
            def on_quote(self, quote):
                return None
        s = MyStrat()
        assert s.get_tuning_space() == []
