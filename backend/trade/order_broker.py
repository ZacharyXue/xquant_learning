"""
订单经纪 (OrderBroker)

消费策略信号，经风控检查后下单，并持久化到数据库。
"""

import asyncio
from datetime import datetime
from typing import Optional

from backend.core.logging import get_logger
from backend.core.config import settings
from backend.engine.strategy_base import Signal
from backend.engine.signal_bus import SignalBus, SignalMerger
from backend.engine.risk_manager import RiskManager, RiskLimits
from backend.trade.fees import fee_calculator, TradeCost
from backend.trade.order_tracker import OrderTracker, OrderRecord

logger = get_logger("order_broker")


class OrderBroker:
    def __init__(
        self,
        signal_bus: SignalBus,
        order_tracker: OrderTracker,
        risk_manager: RiskManager = None,
    ):
        self._signal_bus = signal_bus
        self._order_tracker = order_tracker
        self._risk_manager = risk_manager or RiskManager()
        self._executor = None
        self._db_session_factory = None
        self._ws_manager = None
        self._trade_mode = settings.trade.mode
        self._running = False
        self._task: Optional[asyncio.Task] = None

    def set_executor(self, executor) -> None:
        self._executor = executor

    def set_db_factory(self, factory) -> None:
        self._db_session_factory = factory

    def set_ws_manager(self, manager) -> None:
        self._ws_manager = manager

    async def run(self) -> None:
        self._running = True
        self._task = asyncio.current_task()
        logger.info("OrderBroker started")
        await self._signal_bus.consume()

    async def handle_signal(self, signal: Signal) -> None:
        if not self._executor:
            logger.error("OrderBroker: no executor set")
            return

        # 风控检查
        ok, reason = await self._risk_check(signal)
        if not ok:
            logger.warning(f"Signal rejected: {signal.stock_code} {signal.side} - {reason}")
            await self._save_signal(signal, rejected=True, reason=reason)
            return

        # 计算费用
        cost = self._calc_cost(signal)

        # 下单
        response = await self._place_order(signal, cost)
        if not response.success:
            logger.error(f"Order failed: {response.error}")
            await self._save_signal(signal, rejected=True, reason=response.error)
            return

        # 持久化
        trade_record = await self._save_trade(signal, response, cost)

        # 注册订单追踪
        seq = response.order_id
        record = OrderRecord(
            order_id=seq,
            stock_code=signal.stock_code,
            side=signal.side,
            volume=signal.volume,
            price=signal.price,
            strategy_name=getattr(signal, "strategy_name", ""),
        )
        self._order_tracker.register(seq, record)

        # WebSocket 推送
        await self._ws_push({
            "type": "new_order",
            "order_id": seq,
            "stock_code": signal.stock_code,
            "side": signal.side,
            "volume": signal.volume,
            "price": signal.price,
            "status": "pending",
        })

        logger.info(f"Order placed: {signal.stock_code} {signal.side} x{signal.volume}, seq={seq}")

    async def _risk_check(self, signal: Signal) -> tuple[bool, str]:
        try:
            from backend.grpc import trade_pb2
            resp = await self._executor.get_account(trade_pb2.AccountRequest())
            if not resp.success:
                return False, "Cannot query account"

            pos_resp = await self._executor.get_positions(trade_pb2.PositionsRequest())
            positions = {}
            if pos_resp.success:
                for p in pos_resp.positions:
                    positions[p.stock_code] = {
                        "volume": p.volume,
                        "avg_cost": p.avg_cost,
                    }

            if signal.side == "buy":
                return self._risk_manager.check_buy(
                    signal.stock_code, signal.volume, signal.price,
                    positions, resp.available_cash, resp.total_asset,
                )
            else:
                return self._risk_manager.check_sell(
                    signal.stock_code, signal.volume, positions,
                )
        except Exception as e:
            return False, str(e)

    def _calc_cost(self, signal: Signal) -> TradeCost:
        if signal.price > 0:
            return fee_calculator.calc_trade_cost(
                signal.price, signal.volume, signal.side
            )
        return TradeCost()

    async def _place_order(self, signal: Signal, cost: TradeCost):
        from backend.grpc import trade_pb2

        request = trade_pb2.OrderRequest(
            stock_code=signal.stock_code,
            volume=signal.volume,
            price=signal.price,
            side=signal.side,
            order_type="limit" if signal.price > 0 else "market",
            strategy_name=getattr(signal, "strategy_name", ""),
            order_remark=signal.reason,
        )
        return await self._executor.place_order(request)

    async def _save_signal(self, signal: Signal, rejected: bool = False, reason: str = ""):
        if not self._db_session_factory:
            return
        try:
            from backend.db.repository import save_signal
            async with self._db_session_factory() as db:
                await save_signal(
                    db,
                    strategy_name=getattr(signal, "strategy_name", ""),
                    stock_code=signal.stock_code,
                    signal_type=f"{signal.side}_rejected" if rejected else signal.side,
                    price=signal.price,
                    volume=signal.volume,
                    reason=reason or signal.reason,
                    indicators=signal.indicators,
                )
                await db.commit()
        except Exception as e:
            logger.error(f"Failed to save signal: {e}")

    async def _save_trade(self, signal: Signal, response, cost: TradeCost):
        if not self._db_session_factory:
            return None
        try:
            from backend.db.repository import insert_trade
            order_amount = signal.price * signal.volume if signal.price > 0 else 0
            async with self._db_session_factory() as db:
                record = await insert_trade(
                    db,
                    strategy_name=getattr(signal, "strategy_name", ""),
                    stock_code=signal.stock_code,
                    side=signal.side,
                    volume=signal.volume,
                    order_price=signal.price,
                    order_id=response.order_id,
                    status="pending",
                    commission=cost.commission,
                    stamp_tax=cost.stamp_tax,
                    transfer_fee=cost.transfer_fee,
                    slippage=cost.slippage_cost,
                    amount=order_amount,
                    trade_mode=self._trade_mode,
                    order_remark=signal.reason,
                    trade_time=datetime.now(),
                )
                await db.commit()
                return record
        except Exception as e:
            logger.error(f"Failed to save trade: {e}")
            return None

    async def _ws_push(self, data: dict):
        if self._ws_manager:
            try:
                await self._ws_manager.broadcast(data)
            except Exception:
                pass

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("OrderBroker stopped")
