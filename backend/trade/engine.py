"""
交易引擎 (TradeEngine)

核心编排器，负责：
1. 连接 QMT 并初始化执行器
2. 加载策略 + 创建行情池
3. 协调整行情 → 策略 → 风控 → 下单 → 回执 → 持久化全链路
4. 管理交易日时段状态机
5. 优雅关闭
"""

import asyncio
import sys
from datetime import datetime, time
from enum import Enum
from typing import Optional

from backend.core.config import settings
from backend.core.logging import get_logger
from backend.core.shutdown import shutdown_manager
from backend.core.trading_calendar import (
    is_weekday, is_trading_time,
    CALL_AUCTION_END, CLOSE_CANCEL_TIME,
)
from backend.engine.strategy_registry import create, get_instance, get_active_instances
from backend.engine.signal_bus import SignalBus, SignalMerger
from backend.engine.risk_manager import RiskManager

from backend.trade.real_executor import RealTradeExecutor
from backend.trade.quote_pump import QuotePump
from backend.trade.order_broker import OrderBroker
from backend.trade.order_tracker import OrderTracker, TraderCallbackBridge
from backend.trade.state_sync import StateSync

logger = get_logger("trade_engine")


class SessionState(Enum):
    INITIALIZING = "initializing"
    PRE_MARKET = "pre_market"
    TRADING = "trading"
    PAUSED = "paused"
    PRE_CLOSE = "pre_close"
    POST_CLOSE = "post_close"
    CLOSED = "closed"


class TradeEngine:
    def __init__(self):
        self._executor: Optional[RealTradeExecutor] = None
        self._tracker: Optional[OrderTracker] = None
        self._signal_bus: Optional[SignalBus] = None
        self._broker: Optional[OrderBroker] = None
        self._quote_pump: Optional[QuotePump] = None
        self._state_sync: Optional[StateSync] = None
        self._state: SessionState = SessionState.INITIALIZING
        self._tasks: list[asyncio.Task] = []
        self._ws_manager = None

    @property
    def state(self) -> SessionState:
        return self._state

    def set_ws_manager(self, manager) -> None:
        self._ws_manager = manager

    async def initialize(self) -> bool:
        logger.info("TradeEngine initializing...")
        self._state = SessionState.INITIALIZING

        if sys.platform != "win32":
            logger.warning("TradeEngine requires Windows (xtquant SDK)")
            return False

        # 创建回调桥
        self._tracker = OrderTracker(timeout=5.0)

        # 创建执行器，注入回调桥
        mode = settings.trade.mode
        if mode == "sim":
            from backend.trade.sim_executor import SimTradeExecutor
            self._executor = SimTradeExecutor()
            logger.info("Using SimTradeExecutor (paper trading mode)")
        else:
            self._executor = RealTradeExecutor(
                config={
                    "qmt_path": settings.trade.qmt_path,
                    "account_id": settings.trade.account_id,
                },
                callback=TraderCallbackBridge(self._tracker),
            )
            logger.info("Using RealTradeExecutor (live trading mode)")

        ok = await self._executor.initialize()
        if not ok:
            logger.error("Failed to initialize executor")
            return False

        self._tracker.set_executor(self._executor)

        # 信号总线
        self._signal_bus = SignalBus()

        # 订单经纪
        self._broker = OrderBroker(
            signal_bus=self._signal_bus,
            order_tracker=self._tracker,
            risk_manager=RiskManager(),
        )
        self._broker.set_executor(self._executor)
        if self._ws_manager:
            self._broker.set_ws_manager(self._ws_manager)

        # 加载策略
        self._load_strategies()

        # 构建行情池 (策略关注的股票 + 当前持仓 + 默认 ETF)
        stock_codes = self._build_stock_pool()
        if not stock_codes:
            logger.warning("No stock codes to subscribe, using defaults")
            stock_codes = ["510880.SH", "159905.SZ", "510300.SH"]

        # 行情泵
        self._quote_pump = QuotePump(
            stock_codes=stock_codes,
            on_quote=self._on_quote,
            min_interval=0.1,
        )

        # 状态同步器
        self._state_sync = StateSync(interval=10.0)
        self._state_sync.set_executor(self._executor)
        if self._ws_manager:
            self._state_sync.set_ws_manager(self._ws_manager)

        # 设置 DB session factory
        from backend.db.database import get_session_factory
        sf = get_session_factory()
        self._broker.set_db_factory(sf)
        self._state_sync.set_db_factory(sf)

        # 注册关闭回调
        shutdown_manager.register_callback(self.close)

        logger.info("TradeEngine initialized")
        return True

    def _load_strategies(self) -> None:
        from src.strategies.bonus_stocks import BonusStocksStrategy

        instance = create("bonus_stocks")
        if instance:
            instance.enabled = True
            logger.info(f"Strategy loaded: {instance.display_name}")

    def _build_stock_pool(self) -> list[str]:
        codes: set[str] = set()

        for s in get_active_instances():
            codes.update(getattr(s, "watched_stocks", []))

        if not codes:
            codes.add("510880.SH")

        return list(codes)

    def _on_quote(self, quote) -> None:
        tasks = []
        for strategy in get_active_instances():
            t = asyncio.ensure_future(self._dispatch_quote(strategy, quote))
            tasks.append(t)

        async def _gather():
            results = await asyncio.gather(*tasks, return_exceptions=True)
            signals = []
            for r in results:
                if r is not None and not isinstance(r, Exception):
                    signals.append(r)
            if signals:
                merged = SignalMerger.merge(signals)
                for sig in merged:
                    await self._signal_bus.publish(sig)

        asyncio.ensure_future(_gather())

    async def _dispatch_quote(self, strategy, quote):
        try:
            signal = await strategy.on_quote(quote)
            return signal
        except Exception as e:
            logger.error(f"Strategy {strategy.name} error: {e}")
            return None

    async def run(self) -> None:
        logger.info("TradeEngine starting...")

        # 初始同步：立即将 QMT 账户/持仓写入 DB
        await self._state_sync.sync()
        logger.info("Initial state synced to DB")

        # StateSync 持续运行
        sync_task = asyncio.ensure_future(self._state_sync.run())
        self._tasks.append(sync_task)

        # 等待开盘
        await self._wait_for_market_open()

        # 启动交易子组件
        tasks = [
            asyncio.ensure_future(self._quote_pump.run()),
            asyncio.ensure_future(self._tracker.run()),
            asyncio.ensure_future(self._session_loop()),
        ]
        self._tasks.extend(tasks)

        # 设置 SignalBus handler -> OrderBroker
        self._signal_bus.add_handler(self._broker.handle_signal)
        asyncio.ensure_future(self._broker.run())

        try:
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            pass
        finally:
            await self.close()

    async def _session_loop(self) -> None:
        self._state = SessionState.PRE_MARKET
        logger.info("Entered PRE_MARKET")

        while not shutdown_manager.is_set:
            now = datetime.now()
            weekday = now.weekday()

            if weekday >= 5:
                await asyncio.sleep(60)
                continue

            t = now.time()

            if self._state == SessionState.PRE_MARKET:
                if t >= time(9, 30):
                    self._state = SessionState.TRADING
                    logger.info("Entered TRADING (9:30)")

            elif self._state == SessionState.TRADING:
                if t >= time(11, 30) and t < time(13, 0):
                    self._state = SessionState.PAUSED
                    logger.info("Entered PAUSED (11:30 lunch)")

                elif t >= time(14, 50):
                    self._state = SessionState.PRE_CLOSE
                    logger.info("Entered PRE_CLOSE (14:50), canceling unfilled")
                    await self._cancel_unfilled()

            elif self._state == SessionState.PAUSED:
                if t >= time(13, 0):
                    self._state = SessionState.TRADING
                    logger.info("Entered TRADING (13:00 resume)")

            elif self._state == SessionState.PRE_CLOSE:
                if t >= time(15, 0):
                    self._state = SessionState.POST_CLOSE
                    logger.info("Entered POST_CLOSE (15:00)")
                    await self._state_sync.sync()
                    self._state = SessionState.CLOSED
                    logger.info("Session closed, waiting for next trading day")
                    await asyncio.sleep(3600)

            elif self._state == SessionState.CLOSED:
                if t < time(9, 25):
                    self._state = SessionState.PRE_MARKET
                    logger.info("New day: PRE_MARKET")

            await asyncio.sleep(1)

    async def _wait_for_market_open(self) -> None:
        logger.info("Waiting for pre-market window (8:50)...")
        while True:
            now = datetime.now()
            if now.weekday() >= 5:
                logger.debug("Weekend, sleeping 1h")
                await asyncio.sleep(3600)
                continue
            t = now.time()
            if t >= time(8, 50):
                logger.info(f"Pre-market window reached, time={t}")
                return
            # 计算到 8:50 还需等待的秒数
            target_sec = 8 * 3600 + 50 * 60
            current_sec = t.hour * 3600 + t.minute * 60 + t.second
            if current_sec < target_sec:
                wait = target_sec - current_sec
            else:
                wait = 24 * 3600 - current_sec + target_sec
            wait = min(wait, 3600)
            logger.debug(f"Waiting {wait:.0f}s until 8:50")
            await asyncio.sleep(wait)

    async def _cancel_unfilled(self) -> None:
        if not self._executor:
            return
        try:
            from backend.grpc import trade_pb2
            resp = await self._executor.get_orders(
                trade_pb2.OrdersRequest(cancelable_only=True)
            )
            if resp and resp.success:
                count = 0
                for order in resp.orders:
                    if order.status in ("pending", "reported", "partial"):
                        await self._executor.cancel_order(
                            trade_pb2.CancelRequest(order_id=order.order_id)
                        )
                        count += 1
                logger.info(f"Canceled {count} unfilled orders")
        except Exception as e:
            logger.error(f"Cancel unfilled error: {e}")

    async def _final_sync(self, sync_task: Optional[asyncio.Task]) -> None:
        if sync_task:
            sync_task.cancel()
            try:
                await sync_task
            except asyncio.CancelledError:
                pass
        if self._state_sync:
            await self._state_sync.sync()

    async def close(self) -> None:
        logger.info("TradeEngine closing...")

        if self._broker:
            await self._broker.stop()
        if self._state_sync:
            await self._state_sync.stop()
        if self._quote_pump:
            await self._quote_pump.stop()
        if self._tracker:
            await self._tracker.stop()
        if self._executor:
            await self._executor.close()

        for t in self._tasks:
            if not t.done():
                t.cancel()

        self._state = SessionState.CLOSED
        logger.info("TradeEngine closed")
