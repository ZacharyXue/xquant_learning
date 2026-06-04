import json
import pytest
from db.database import set_db_path
from db.schema import init_db
from db.queries import (
    register_strategy, list_strategies, get_strategy,
    enable_strategy, update_strategy_config,
    insert_trade, get_trades,
    insert_backtest_run, get_backtest_runs, get_backtest_run,
)


@pytest.fixture(autouse=True)
def setup_db(tmp_path):
    db_path = str(tmp_path / "test.db")
    set_db_path(db_path)
    init_db()
    yield
    import os
    if os.path.exists(db_path):
        os.remove(db_path)


class TestStrategyQueries:
    def test_register_and_list(self):
        register_strategy("test_strat", "Test Strategy")
        assert len(list_strategies()) == 1
        assert list_strategies()[0]["name"] == "test_strat"

    def test_get_strategy(self):
        register_strategy("s1", "S1")
        assert get_strategy("s1")["name"] == "s1"
        assert get_strategy("nope") is None

    def test_enable_disable(self):
        register_strategy("s1", "S1")
        enable_strategy("s1", False)
        assert get_strategy("s1")["enabled"] == 0
        enable_strategy("s1", True)
        assert get_strategy("s1")["enabled"] == 1

    def test_update_config(self):
        register_strategy("s1", "S1", {"k": "v"})
        update_strategy_config("s1", {"new": "val"})
        s = get_strategy("s1")
        config = json.loads(s["config"]) if isinstance(s["config"], str) else s["config"]
        assert config["new"] == "val"


class TestTradeQueries:
    def _make_trade(self, strategy="test", mode="sim", stock="000001.SZ", **kw):
        return insert_trade(strategy=strategy, mode=mode, stock_code=stock,
                           side="buy", volume=100, price=10.0, reason="",
                           trade_time="2024-01-15 10:30:00", **kw)

    def test_insert_and_get(self):
        self._make_trade()
        trades = get_trades()
        assert len(trades) == 1
        assert trades[0]["stock_code"] == "000001.SZ"

    def test_filter_by_strategy(self):
        self._make_trade(strategy="s1", stock="A.SZ")
        self._make_trade(strategy="s2", stock="B.SZ")
        assert len(get_trades(strategy="s1")) == 1
        assert len(get_trades(strategy="s2")) == 1

    def test_filter_by_mode(self):
        self._make_trade(mode="sim", stock="A.SZ")
        self._make_trade(mode="backtest", stock="B.SZ")
        assert len(get_trades(mode="sim")) == 1
        assert len(get_trades(mode="backtest")) == 1

    def test_limit(self):
        for i in range(10):
            self._make_trade(stock=f"{i:06d}.SZ")
        assert len(get_trades(limit=5)) == 5


class TestBacktestQueries:
    def _make_run(self, **kw):
        base = {"run_id": "test-001", "strategy": "s1",
                "start_date": "2024", "end_date": "2024",
                "params": {}, "initial_cash": 100000, "final_equity": 110000,
                "total_return": 0.1, "annual_return": 0.1,
                "max_drawdown": -0.05, "sharpe_ratio": 1.5,
                "win_rate": 0.6, "total_trades": 50, "equity_curve": []}
        base.update(kw)
        return insert_backtest_run(base)

    def test_insert_and_list(self):
        self._make_run()
        assert len(get_backtest_runs()) == 1

    def test_get_by_run_id(self):
        self._make_run(run_id="test-002")
        r = get_backtest_run("test-002")
        assert r is not None
        assert r["strategy"] == "s1"
