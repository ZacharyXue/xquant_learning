"""
状态同步器 (StateSync)

定时将账户、持仓快照写入数据库，并通过 WebSocket 推送 Dashboard。
"""

import asyncio
from datetime import datetime
from typing import Optional

from backend.core.logging import get_logger
from backend.core.config import settings

logger = get_logger("state_sync")


class StateSync:
    def __init__(self, interval: float = 10.0):
        self._interval = interval
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
        logger.info(f"StateSync started (interval={self._interval}s)")
        while self._running:
            try:
                await asyncio.sleep(self._interval)
                await self.sync()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"StateSync error: {e}")

    async def sync(self) -> None:
        if not self._executor:
            return

        try:
            from backend.grpc import trade_pb2

            # 账户快照
            account_resp = await self._executor.get_account(
                trade_pb2.AccountRequest()
            )

            # 持仓快照
            pos_resp = await self._executor.get_positions(
                trade_pb2.PositionsRequest()
            )

            account_data = None
            positions_data = []

            if account_resp and account_resp.success:
                account_data = {
                    "total_asset": account_resp.total_asset,
                    "available_cash": account_resp.available_cash,
                    "frozen_cash": account_resp.frozen_cash,
                    "market_value": account_resp.market_value,
                    "total_profit_loss": account_resp.total_profit_loss,
                }

            if pos_resp and pos_resp.success:
                positions_data = [
                    {
                        "stock_code": p.stock_code,
                        "stock_name": p.stock_name,
                        "volume": p.volume,
                        "avg_cost": float(p.avg_cost),
                        "current_price": float(p.current_price),
                        "market_value": float(p.market_value),
                        "profit_loss": float(p.profit_loss),
                    }
                    for p in pos_resp.positions
                ]

            # 写入 DB
            await self._persist(account_data, positions_data)

            # WebSocket 推送
            await self._broadcast(account_data, positions_data)

        except Exception as e:
            logger.error(f"Sync failed: {e}")

    async def _persist(self, account_data: Optional[dict], positions_data: list[dict]):
        if not self._db_session_factory:
            return
        try:
            from backend.db.repository import (
                save_account_snapshot,
                save_positions,
            )
            async with self._db_session_factory() as db:
                if account_data:
                    await save_account_snapshot(
                        db, trade_mode=self._trade_mode, **account_data,
                    )

                if positions_data:
                    await save_positions(
                        db,
                        [{**p, "trade_mode": self._trade_mode} for p in positions_data],
                    )

                await db.commit()
        except Exception as e:
            logger.warning(f"DB persist failed: {e}")

    async def _broadcast(self, account_data: Optional[dict], positions_data: list[dict]):
        if not self._ws_manager:
            return
        try:
            await self._ws_manager.broadcast({
                "type": "state_sync",
                "timestamp": datetime.now().isoformat(),
                "account": account_data,
                "positions": positions_data,
            })
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
        logger.info("StateSync stopped")
