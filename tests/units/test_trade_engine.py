"""
Trade Engine 组件测试

测试 QuotePump、OrderTracker、OrderBroker、StateSync、TradeEngine。
不依赖 QMT/xtquant 实际运行，通过 mock 隔离。
"""

import asyncio
import time
from datetime import datetime
from unittest.mock import Mock, AsyncMock, MagicMock, patch

import pytest

from backend.core.config import settings
from backend.engine.strategy_base import Quote, Signal
from backend.engine.signal_bus import SignalBus, SignalMerger
from backend.engine.risk_manager import RiskManager

from backend.trade.quote_pump import QuotePump
from backend.trade.order_tracker import (
    OrderTracker, OrderRecord, order_status_name,
)
from backend.trade.order_broker import OrderBroker
from backend.trade.state_sync import StateSync
from backend.api.websocket import ConnectionManager


# ============================================================
# QuotePump
# ============================================================

class TestQuotePump:
    def test_creation(self):
        pump = QuotePump(stock_codes=["510880.SH"])
        assert pump._stock_codes == ["510880.SH"]
        assert pump._min_interval == 0.1

    def test_creation_with_callback(self):
        quotes = []
        def handler(q):
            quotes.append(q)

        pump = QuotePump(
            stock_codes=["510880.SH"],
            on_quote=handler,
        )
        assert pump._on_quote is handler

    @pytest.mark.asyncio
    async def test_pump_stop(self):
        pump = QuotePump(stock_codes=["510880.SH"])
        pump._running = True
        # Start run in background, stop quickly
        task = asyncio.ensure_future(pump.run())
        await asyncio.sleep(0.1)
        await pump.stop()
        assert not pump._running


# ============================================================
# OrderTracker
# ============================================================

class TestOrderTracker:
    def test_order_status_mapping(self):
        assert order_status_name(48) == "pending"
        assert order_status_name(50) == "reported"
        assert order_status_name(52) == "partial"
        assert order_status_name(53) == "filled"
        assert order_status_name(54) == "rejected"
        assert order_status_name(56) == "cancelled"
        assert order_status_name(99) == "unknown"

    def test_register_order(self):
        tracker = OrderTracker()
        record = OrderRecord(
            order_id="123",
            stock_code="510880.SH",
            side="buy",
            volume=1000,
            price=3.50,
            strategy_name="bonus_stocks",
        )
        tracker.register("123", record)
        pending = tracker.get_pending()
        assert len(pending) == 1
        assert pending[0].stock_code == "510880.SH"
        assert pending[0].side == "buy"

    def test_register_order_with_seq(self):
        tracker = OrderTracker()
        record = OrderRecord("456", "159905.SZ", "sell", 500, 1.80)
        tracker.register("456", record)
        assert tracker._pending["456"].stock_code == "159905.SZ"

    @pytest.mark.asyncio
    async def test_handle_order_update_filled(self):
        tracker = OrderTracker()
        record = OrderRecord("789", "510880.SH", "buy", 1000, 3.50)
        tracker.register("789", record)

        on_update_called = []
        async def on_update(order, status):
            on_update_called.append(status)

        tracker.set_on_update(on_update)

        mock_order = MagicMock()
        mock_order.order_id = 789
        mock_order.order_status = 53  # filled
        mock_order.traded_volume = 1000
        mock_order.traded_price = 3.55

        await tracker._handle_order_update(mock_order)
        assert "789" not in tracker._pending
        assert "filled" in on_update_called

    @pytest.mark.asyncio
    async def test_handle_order_update_partial(self):
        tracker = OrderTracker()
        record = OrderRecord("abc", "510300.SH", "buy", 1000, 4.00)
        tracker.register("abc", record)

        mock_order = MagicMock()
        mock_order.order_id = "abc"
        mock_order.order_status = 52  # partial
        mock_order.traded_volume = 500
        mock_order.traded_price = 4.02

        await tracker._handle_order_update(mock_order)
        assert "abc" in tracker._pending
        assert tracker._pending["abc"].status == "partial"
        assert tracker._pending["abc"].filled_volume == 500

    @pytest.mark.asyncio
    async def test_stop_tracker(self):
        tracker = OrderTracker()
        tracker._running = True
        task = asyncio.ensure_future(tracker.run())
        await asyncio.sleep(0.1)
        await tracker.stop()
        assert not tracker._running


# ============================================================
# OrderBroker
# ============================================================

class TestOrderBroker:
    @pytest.fixture
    def signal_bus(self):
        return SignalBus()

    @pytest.fixture
    def order_tracker(self):
        return OrderTracker()

    @pytest.fixture
    def broker(self, signal_bus, order_tracker):
        return OrderBroker(
            signal_bus=signal_bus,
            order_tracker=order_tracker,
        )

    def test_creation(self, broker):
        assert broker._executor is None
        assert broker._risk_manager is not None

    def test_set_executor(self, broker):
        mock_exec = Mock()
        broker.set_executor(mock_exec)
        assert broker._executor is mock_exec

    @pytest.mark.asyncio
    async def test_handle_signal_no_executor(self, broker):
        signal = Signal(
            stock_code="510880.SH",
            side="buy",
            volume=1000,
            price=3.50,
            reason="test",
        )
        await broker.handle_signal(signal)
        # Should log error but not crash

    @pytest.mark.asyncio
    async def test_handle_signal_rejected_by_risk(self, broker):
        from backend.grpc import trade_pb2

        mock_exec = AsyncMock()
        # Account response: insufficient cash
        acc = trade_pb2.AccountResponse(
            success=True,
            total_asset=10000,
            available_cash=100,
            frozen_cash=0,
            market_value=0,
        )
        mock_exec.get_account.return_value = acc
        # Position response: empty
        pos = trade_pb2.PositionsResponse(success=True, positions=[])
        mock_exec.get_positions.return_value = pos

        broker.set_executor(mock_exec)

        signal = Signal(
            stock_code="510880.SH",
            side="buy",
            volume=10000,
            price=3.50,
            reason="test",
        )

        await broker.handle_signal(signal)
        # Should be rejected by risk (insufficient cash), not place_order
        mock_exec.place_order.assert_not_called()

    @pytest.mark.asyncio
    async def test_stop_broker(self, broker):
        task = asyncio.ensure_future(broker.run())
        await asyncio.sleep(0.1)
        await broker.stop()
        assert not broker._running


# ============================================================
# SignalMerger
# ============================================================

class TestSignalMerger:
    def test_empty_signals(self):
        assert SignalMerger.merge([]) == []

    def test_single_signal(self):
        sig = Signal(stock_code="510880.SH", side="buy", volume=500, reason="test")
        merged = SignalMerger.merge([sig])
        assert len(merged) == 1
        assert merged[0].stock_code == "510880.SH"
        assert merged[0].volume == 500

    def test_same_direction_merge(self):
        sigs = [
            Signal(stock_code="510880.SH", side="buy", volume=500, reason="s1"),
            Signal(stock_code="510880.SH", side="buy", volume=300, reason="s2"),
        ]
        merged = SignalMerger.merge(sigs)
        assert len(merged) == 1
        assert merged[0].side == "buy"
        assert merged[0].volume == 800
        assert "s1" in merged[0].reason
        assert "s2" in merged[0].reason

    def test_opposite_direction_net(self):
        sigs = [
            Signal(stock_code="510880.SH", side="buy", volume=1000, reason="buy"),
            Signal(stock_code="510880.SH", side="sell", volume=300, reason="sell"),
        ]
        merged = SignalMerger.merge(sigs)
        assert len(merged) == 1
        assert merged[0].side == "buy"
        assert merged[0].volume == 700

    def test_opposite_direction_full_net(self):
        sigs = [
            Signal(stock_code="510880.SH", side="buy", volume=1000, reason="buy"),
            Signal(stock_code="510880.SH", side="sell", volume=1000, reason="sell"),
        ]
        merged = SignalMerger.merge(sigs)
        assert len(merged) == 0

    def test_multi_stock_merge(self):
        sigs = [
            Signal(stock_code="510880.SH", side="buy", volume=500, reason="a"),
            Signal(stock_code="159905.SZ", side="buy", volume=300, reason="b"),
        ]
        merged = SignalMerger.merge(sigs)
        assert len(merged) == 2
        codes = {s.stock_code for s in merged}
        assert codes == {"510880.SH", "159905.SZ"}


# ============================================================
# StateSync
# ============================================================

class TestStateSync:
    @pytest.fixture
    def sync(self):
        return StateSync(interval=1.0)

    def test_creation(self, sync):
        assert sync._interval == 1.0
        assert sync._executor is None

    def test_set_executor(self, sync):
        mock = Mock()
        sync.set_executor(mock)
        assert sync._executor is mock

    @pytest.mark.asyncio
    async def test_sync_no_executor(self, sync):
        await sync.sync()

    @pytest.mark.asyncio
    async def test_sync_with_mock(self, sync):
        from backend.grpc import trade_pb2

        mock_exec = AsyncMock()
        acc = trade_pb2.AccountResponse(
            success=True,
            total_asset=100000,
            available_cash=50000,
            frozen_cash=0,
            market_value=50000,
            total_profit_loss=5000,
        )
        mock_exec.get_account.return_value = acc

        pos = trade_pb2.PositionsResponse(
            success=True,
            positions=[
                trade_pb2.Position(
                    stock_code="510880.SH",
                    stock_name="红利ETF",
                    volume=10000,
                    avg_cost=3.50,
                    market_value=35000,
                    profit_loss=2000,
                ),
            ],
        )
        mock_exec.get_positions.return_value = pos

        sync.set_executor(mock_exec)
        ws = ConnectionManager()
        sync.set_ws_manager(ws)

        await sync.sync()
        mock_exec.get_account.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_sync(self, sync):
        sync._running = True
        task = asyncio.ensure_future(sync.run())
        await asyncio.sleep(0.1)
        await sync.stop()
        assert not sync._running


# ============================================================
# ShutdownManager
# ============================================================

class TestShutdownManager:
    def test_creation(self):
        from backend.core.shutdown import ShutdownManager
        mgr = ShutdownManager()
        assert not mgr.is_set

    @pytest.mark.asyncio
    async def test_trigger(self):
        from backend.core.shutdown import ShutdownManager
        mgr = ShutdownManager()

        callbacks = []
        async def cb():
            callbacks.append(1)

        mgr.register_callback(cb)
        await mgr.trigger()
        assert mgr.is_set
        assert len(callbacks) == 1

    @pytest.mark.asyncio
    async def test_trigger_with_error_callback(self):
        from backend.core.shutdown import ShutdownManager
        mgr = ShutdownManager()

        results = []
        async def cb_ok():
            results.append("ok")

        async def cb_err():
            raise RuntimeError("test error")

        mgr.register_callback(cb_err)
        mgr.register_callback(cb_ok)
        await mgr.trigger()
        assert "ok" in results


# ============================================================
# TradeEngine State Machine
# ============================================================

class TestTradeEngine:
    def test_session_state_values(self):
        from backend.trade.engine import SessionState
        assert SessionState.INITIALIZING.value == "initializing"
        assert SessionState.PRE_MARKET.value == "pre_market"
        assert SessionState.TRADING.value == "trading"
        assert SessionState.PAUSED.value == "paused"
        assert SessionState.CLOSED.value == "closed"
