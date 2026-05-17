"""
gRPC 服务端 (仅 Windows / Trade Engine)

实现 TradeService，封装 TradeExecutor。
"""

from concurrent import futures
from typing import Optional

import grpc

from backend.core.config import settings
from backend.core.logging import get_logger
from backend.grpc import trade_pb2, trade_pb2_grpc

logger = get_logger("grpc_server")


class TradeServiceServicer(trade_pb2_grpc.TradeServiceServicer):
    """TradeService gRPC 实现"""

    def __init__(self, executor=None):
        self._executor = executor
        self._stock_codes = set()

    def set_executor(self, executor):
        self._executor = executor

    # ---- Trade Operations ----

    async def PlaceOrder(self, request, context):
        if not self._executor:
            return trade_pb2.OrderResponse(success=False, error="Executor not initialized")
        return await self._executor.place_order(request)

    async def CancelOrder(self, request, context):
        if not self._executor:
            return trade_pb2.CancelResponse(success=False, error="Executor not initialized")
        return await self._executor.cancel_order(request)

    async def GetAccount(self, request, context):
        if not self._executor:
            return trade_pb2.AccountResponse(success=False)
        return await self._executor.get_account(request)

    async def GetPositions(self, request, context):
        if not self._executor:
            return trade_pb2.PositionsResponse(success=False)
        return await self._executor.get_positions(request)

    async def GetOrders(self, request, context):
        if not self._executor:
            return trade_pb2.OrdersResponse(success=False)
        return await self._executor.get_orders(request)

    async def GetTrades(self, request, context):
        if not self._executor:
            return trade_pb2.TradesResponse(success=False)
        return await self._executor.get_trades(request)

    async def SubscribeMarketData(self, request, context):
        if not self._executor:
            return
        async for tick in self._executor.subscribe_quotes(request.stock_codes):
            yield tick

    async def GetHistoryKline(self, request, context):
        if not self._executor:
            return trade_pb2.KlineResponse(success=False, error="Executor not initialized")
        return await self._executor.get_history_kline(request)

    async def GetStockList(self, request, context):
        if not self._executor:
            return trade_pb2.StockListResponse(success=False)
        return await self._executor.get_stock_list(request)

    async def Ping(self, request, context):
        from datetime import datetime
        return trade_pb2.PingResponse(
            ok=True,
            server_time=datetime.now().isoformat(),
            trade_mode=settings.trade.mode,
        )

    async def GetTradeMode(self, request, context):
        import sys
        return trade_pb2.TradeModeResponse(
            mode=settings.trade.mode,
            server_platform=sys.platform,
        )


class GRPCServer:
    """gRPC 服务端管理器"""

    def __init__(self, executor=None, host: str = None, port: int = None):
        self.host = host or settings.grpc.host
        self.port = port or settings.grpc.port
        self._executor = executor
        self._server: Optional[grpc.aio.Server] = None

    async def start(self) -> None:
        self._server = grpc.aio.server(
            futures.ThreadPoolExecutor(max_workers=10),
            options=[
                ("grpc.max_send_message_length", 50 * 1024 * 1024),
                ("grpc.max_receive_message_length", 50 * 1024 * 1024),
            ],
        )

        servicer = TradeServiceServicer(self._executor)
        trade_pb2_grpc.add_TradeServiceServicer_to_server(servicer, self._server)

        addr = f"{self.host}:{self.port}"
        self._server.add_insecure_port(addr)

        await self._server.start()
        logger.info(f"gRPC server started on {addr}")

    async def stop(self) -> None:
        if self._server:
            await self._server.stop(grace=5)
            logger.info("gRPC server stopped")

    async def wait_for_termination(self) -> None:
        if self._server:
            await self._server.wait_for_termination()
