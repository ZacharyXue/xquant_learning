"""
gRPC 客户端 (跨平台)

策略引擎通过此客户端连接 Windows 上的交易引擎。
"""

from typing import AsyncIterator, Optional

import grpc

from backend.core.config import settings
from backend.core.logging import get_logger
from backend.grpc import trade_pb2, trade_pb2_grpc

logger = get_logger("grpc_client")


class GRPCClient:
    """gRPC 客户端 (连接到 Trade Engine)"""

    def __init__(self, host: str = None, port: int = None):
        self.host = host or settings.grpc.host
        self.port = port or settings.grpc.port
        self._channel: Optional[grpc.aio.Channel] = None
        self._stub: Optional[trade_pb2_grpc.TradeServiceStub] = None
        self._connected = False

    @property
    def connected(self) -> bool:
        return self._connected

    async def connect(self, timeout: float = 10.0) -> bool:
        try:
            addr = f"{self.host}:{self.port}"
            self._channel = grpc.aio.insecure_channel(
                addr,
                options=[
                    ("grpc.max_send_message_length", 50 * 1024 * 1024),
                    ("grpc.max_receive_message_length", 50 * 1024 * 1024),
                    ("grpc.keepalive_time_ms", 30000),
                    ("grpc.keepalive_timeout_ms", 10000),
                ],
            )
            self._stub = trade_pb2_grpc.TradeServiceStub(self._channel)

            # Test connection
            res = await self._stub.Ping(trade_pb2.PingRequest(), timeout=timeout)
            self._connected = res.ok
            logger.info(f"Connected to gRPC server at {addr}, mode={res.trade_mode}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to {addr}: {e}")
            self._connected = False
            return False

    async def close(self) -> None:
        if self._channel:
            await self._channel.close()
            self._connected = False
            logger.info("gRPC client disconnected")

    # ---- Trade Operations ----

    async def place_order(
        self, stock_code: str, volume: int, side: str, price: float = 0.0,
        strategy_name: str = "", order_type: str = "market",
    ) -> trade_pb2.OrderResponse:
        req = trade_pb2.OrderRequest(
            stock_code=stock_code, volume=volume, side=side,
            price=price, strategy_name=strategy_name, order_type=order_type,
        )
        return await self._stub.PlaceOrder(req)

    async def cancel_order(self, order_id: str, stock_code: str = "") -> trade_pb2.CancelResponse:
        req = trade_pb2.CancelRequest(order_id=order_id, stock_code=stock_code)
        return await self._stub.CancelOrder(req)

    async def get_account(self, trade_mode: str = "real") -> trade_pb2.AccountResponse:
        req = trade_pb2.AccountRequest(trade_mode=trade_mode)
        return await self._stub.GetAccount(req)

    async def get_positions(self, trade_mode: str = "real") -> trade_pb2.PositionsResponse:
        req = trade_pb2.PositionsRequest(trade_mode=trade_mode)
        return await self._stub.GetPositions(req)

    async def get_orders(self, status: str = "", trade_mode: str = "real") -> trade_pb2.OrdersResponse:
        req = trade_pb2.OrdersRequest(status=status, trade_mode=trade_mode)
        return await self._stub.GetOrders(req)

    async def get_trades(self, trade_mode: str = "real") -> trade_pb2.TradesResponse:
        req = trade_pb2.TradesRequest(trade_mode=trade_mode)
        return await self._stub.GetTrades(req)

    async def subscribe_market_data(
        self, stock_codes: list[str], trade_mode: str = "real",
    ) -> AsyncIterator[trade_pb2.MarketDataTick]:
        req = trade_pb2.MarketDataRequest(stock_codes=stock_codes, trade_mode=trade_mode)
        async for tick in self._stub.SubscribeMarketData(req):
            yield tick

    async def get_history_kline(
        self, stock_code: str, period: str, start_time: str, end_time: str,
        fields: list[str] = None,
    ) -> trade_pb2.KlineResponse:
        if fields is None:
            fields = ["close", "open", "high", "low", "volume"]
        req = trade_pb2.KlineRequest(
            stock_code=stock_code, period=period,
            start_time=start_time, end_time=end_time, fields=fields,
        )
        return await self._stub.GetHistoryKline(req)

    async def get_stock_list(self, market: str = "") -> trade_pb2.StockListResponse:
        req = trade_pb2.StockListRequest(market=market)
        return await self._stub.GetStockList(req)

    async def get_trade_mode(self) -> trade_pb2.TradeModeResponse:
        return await self._stub.GetTradeMode(trade_pb2.TradeModeRequest())
