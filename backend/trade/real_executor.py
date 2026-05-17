"""
真实交易执行器 (xtquant/QMT)

封装 xtquant SDK，仅在 Windows 上可用。
需要 QMT 客户端运行。
"""

import asyncio
import time
from datetime import datetime
from typing import AsyncIterator, Optional

from backend.core.config import settings
from backend.core.logging import get_logger
from backend.grpc import trade_pb2
from backend.trade.base_executor import TradeExecutor
from backend.trade.fees import fee_calculator

logger = get_logger("real_executor")

# xtquant 是 Windows 专有 SDK，跨平台环境下不可用
try:
    from xtquant.xttrader import XtQuantTrader, XtQuantTraderCallback
    from xtquant.xttype import StockAccount
    from xtquant import xtconstant
    _XTQUANT_AVAILABLE = True
except ImportError:
    XtQuantTrader = object
    XtQuantTraderCallback = object
    _XTQUANT_AVAILABLE = False


class _TraderCallback(XtQuantTraderCallback):
    """xtquant 回调处理器"""

    def __init__(self, executor: "RealTradeExecutor"):
        super().__init__()
        self._executor = executor

    def on_disconnected(self):
        logger.warning("QMT connection disconnected")

    def on_stock_order(self, order):
        logger.info(f"Order update: id={order.order_id}, status={order.order_status}, remark={order.order_remark}")
        self._executor._orders[order.order_id] = order

    def on_stock_trade(self, trade):
        logger.info(f"Trade: {trade.stock_code} x{trade.trade_volume} @ {trade.trade_price}")
        self._executor._trades.append(trade)

    def on_order_error(self, order_error):
        logger.error(f"Order error: {order_error.error_msg}")

    def on_cancel_error(self, cancel_error):
        logger.error(f"Cancel error: {cancel_error}")

    def on_account_status(self, status):
        logger.info(f"Account status update: {status}")


class RealTradeExecutor(TradeExecutor):
    """真实交易执行器 (通过 xtquant 连接 QMT)"""

    def __init__(self, config: dict = None):
        super().__init__(config)
        self._trader: Optional[XtQuantTrader] = None
        self._account: Optional[StockAccount] = None
        self._callback: Optional[_TraderCallback] = None
        self._orders: dict[str, any] = {}
        self._trades: list[any] = []
        self._cancel_timer_task: Optional[asyncio.Task] = None

    async def initialize(self) -> bool:
        if not _XTQUANT_AVAILABLE:
            logger.error("xtquant SDK not available (Windows only)")
            return False

        qmt_path = self._config.get("qmt_path") or settings.trade.qmt_path
        account_id = self._config.get("account_id") or settings.trade.account_id

        if not qmt_path or not account_id:
            logger.error("QMT path and account_id are required")
            return False

        try:
            session_id = int(time.time())
            self._trader = XtQuantTrader(qmt_path, session_id)
            self._callback = _TraderCallback(self)
            self._trader.register_callback(self._callback)
            self._trader.start()

            connect_result = self._trader.connect()
            logger.info(f"Connected to QMT: path={qmt_path}, result={connect_result}")

            self._account = StockAccount(account_id)
            subscribe_result = self._trader.subscribe(self._account)
            if subscribe_result != 0:
                logger.error(f"Subscribe account failed: {subscribe_result}")
                return False

            self._initialized = True
            logger.info(f"Real trade executor initialized, account={account_id}")

            # 启动收盘自动撤单
            self._start_cancel_timer()

            return True
        except Exception as e:
            logger.error(f"Failed to initialize QMT: {e}")
            return False

    # ---- Order ----

    async def place_order(self, request: trade_pb2.OrderRequest) -> trade_pb2.OrderResponse:
        if not self._trader or not self._account:
            return trade_pb2.OrderResponse(success=False, error="Not initialized")

        order_type = xtconstant.STOCK_BUY if request.side == "buy" else xtconstant.STOCK_SELL
        price_type = xtconstant.FIX_PRICE if request.price > 0 else xtconstant.LATEST_PRICE

        # 预估费用
        if request.price > 0:
            est_cost = fee_calculator.calc_trade_cost(request.price, request.volume, request.side)
            est_fee = est_cost.total
            slippage_price = fee_calculator.calc_slippage_price(request.price, request.side)
        else:
            est_fee = 0.0
            slippage_price = 0.0

        try:
            async_seq = self._trader.order_stock_async(
                account=self._account,
                stock_code=request.stock_code,
                order_type=order_type,
                order_volume=request.volume,
                price_type=price_type,
                price=request.price,
                strategy_name=request.strategy_name,
                order_remark=request.order_remark,
            )
            logger.info(f"Order placed: {request.stock_code} {request.side} x{request.volume}, seq={async_seq}")

            return trade_pb2.OrderResponse(
                success=True,
                order_id=str(async_seq),
                estimated_fee=est_fee,
                slippage_price=slippage_price,
                order_price=request.price,
                order_volume=request.volume,
                status="pending",
            )
        except Exception as e:
            logger.error(f"Order failed: {e}")
            return trade_pb2.OrderResponse(success=False, error=str(e))

    async def cancel_order(self, request: trade_pb2.CancelRequest) -> trade_pb2.CancelResponse:
        if not self._trader or not self._account:
            return trade_pb2.CancelResponse(success=False, error="Not initialized")

        try:
            self._trader.cancel_order_stock_async(
                account=self._account,
                order_id=int(request.order_id) if request.order_id.isdigit() else request.order_id,
            )
            return trade_pb2.CancelResponse(success=True, canceled_count=1)
        except Exception as e:
            logger.error(f"Cancel failed: {e}")
            return trade_pb2.CancelResponse(success=False, error=str(e))

    # ---- Account ----

    async def get_account(self, request: trade_pb2.AccountRequest) -> trade_pb2.AccountResponse:
        if not self._trader or not self._account:
            return trade_pb2.AccountResponse(success=False)

        try:
            asset = self._trader.query_stock_asset(self._account)
            return trade_pb2.AccountResponse(
                success=True,
                account_id=str(self._account.account_id),
                total_asset=asset.total_asset if asset else 0,
                available_cash=asset.cash if asset else 0,
                frozen_cash=asset.frozen_cash if asset else 0,
                market_value=asset.market_value if asset else 0,
                total_profit_loss=0.0,
                today_profit_loss=0.0,
                trade_mode="real",
            )
        except Exception as e:
            logger.error(f"Query account failed: {e}")
            return trade_pb2.AccountResponse(success=False)

    async def get_positions(self, request: trade_pb2.PositionsRequest) -> trade_pb2.PositionsResponse:
        if not self._trader or not self._account:
            return trade_pb2.PositionsResponse(success=False)

        try:
            xt_positions = self._trader.query_stock_positions(self._account)
            positions = []
            for pos in xt_positions:
                mv = pos.volume * pos.avg_price
                positions.append(trade_pb2.Position(
                    stock_code=pos.stock_code,
                    stock_name=getattr(pos, "stock_name", ""),
                    volume=pos.volume,
                    available_volume=pos.can_use_volume,
                    avg_cost=pos.avg_price,
                    current_price=0.0,
                    market_value=mv,
                    profit_loss=0.0,
                    profit_loss_ratio=0.0,
                    trade_mode="real",
                ))
            return trade_pb2.PositionsResponse(success=True, positions=positions)
        except Exception as e:
            logger.error(f"Query positions failed: {e}")
            return trade_pb2.PositionsResponse(success=False, error=str(e))

    async def get_orders(self, request: trade_pb2.OrdersRequest) -> trade_pb2.OrdersResponse:
        if not self._trader or not self._account:
            return trade_pb2.OrdersResponse(success=False)

        try:
            xt_orders = self._trader.query_stock_orders(self._account)
            orders = []
            for o in xt_orders:
                status_map = {48: "pending", 49: "partial", 50: "filled", 51: "partial", 52: "cancelled", 53: "partial"}
                orders.append(trade_pb2.Order(
                    order_id=str(o.order_id),
                    stock_code=o.stock_code,
                    stock_name=getattr(o, "stock_name", ""),
                    side="buy" if o.order_type == 23 else "sell",
                    order_volume=o.order_volume,
                    traded_volume=o.traded_volume,
                    order_price=o.price,
                    traded_price=o.traded_price,
                    status=status_map.get(o.order_status, "unknown"),
                    strategy_name=getattr(o, "strategy_name", ""),
                    order_remark=getattr(o, "order_remark", ""),
                    order_time=datetime.now().isoformat(),
                ))
            return trade_pb2.OrdersResponse(success=True, orders=orders)
        except Exception as e:
            logger.error(f"Query orders failed: {e}")
            return trade_pb2.OrdersResponse(success=False, error=str(e))

    async def get_trades(self, request: trade_pb2.TradesRequest) -> trade_pb2.TradesResponse:
        if not self._trader or not self._account:
            return trade_pb2.TradesResponse(success=False)

        try:
            xt_trades = self._trader.query_stock_trades(self._account)
            trades = []
            for t in xt_trades:
                trades.append(trade_pb2.Trade(
                    trade_id=str(t.trade_id),
                    order_id=str(t.order_id),
                    stock_code=t.stock_code,
                    stock_name=getattr(t, "stock_name", ""),
                    side="buy" if t.order_type == 23 else "sell",
                    trade_volume=t.trade_volume,
                    trade_price=t.trade_price,
                    trade_amount=t.trade_amount,
                    trade_time=datetime.now().isoformat(),
                ))
            return trade_pb2.TradesResponse(success=True, trades=trades)
        except Exception as e:
            logger.error(f"Query trades failed: {e}")
            return trade_pb2.TradesResponse(success=False, error=str(e))

    # ---- Market Data ----

    async def subscribe_quotes(self, stock_codes: list[str]) -> AsyncIterator[trade_pb2.MarketDataTick]:
        try:
            from xtquant import xtdata
        except ImportError:
            logger.error("xtquant.xtdata not available")
            return

        quotes_queue: asyncio.Queue = asyncio.Queue()

        def _on_quote(data):
            for code, quote in data.items():
                tick = trade_pb2.MarketDataTick(
                    stock_code=code,
                    last_price=quote.get("lastPrice", 0),
                    open=quote.get("open", 0),
                    high=quote.get("high", 0),
                    low=quote.get("low", 0),
                    last_close=quote.get("lastClose", 0),
                    volume=quote.get("volume", 0),
                    amount=quote.get("amount", 0),
                    time=quote.get("time", ""),
                    trade_mode="real",
                )
                asyncio.create_task(quotes_queue.put(tick))

        try:
            xtdata.subscribe_whole_quote(stock_codes, callback=_on_quote)
            while True:
                try:
                    tick = await asyncio.wait_for(quotes_queue.get(), timeout=30)
                    yield tick
                except asyncio.TimeoutError:
                    pass
        finally:
            xtdata.unsubscribe_whole_quote(stock_codes)

    async def get_history_kline(self, request: trade_pb2.KlineRequest) -> trade_pb2.KlineResponse:
        try:
            from xtquant import xtdata
            data = xtdata.get_market_data(
                field_list=list(request.fields),
                stock_list=[request.stock_code],
                start_time=request.start_time,
                end_time=request.end_time,
                period=request.period,
            )
            return trade_pb2.KlineResponse(success=True, error="Data extraction needed")
        except ImportError:
            return trade_pb2.KlineResponse(success=False, error="xtquant not available")
        except Exception as e:
            return trade_pb2.KlineResponse(success=False, error=str(e))

    async def get_stock_list(self, request: trade_pb2.StockListRequest) -> trade_pb2.StockListResponse:
        return trade_pb2.StockListResponse(success=True, stocks=[])

    # ---- Lifecycle ----

    def _start_cancel_timer(self):
        """启动收盘前自动撤单定时器"""
        from backend.core.trading_calendar import CLOSE_CANCEL_TIME
        import threading

        def _check():
            while self._initialized:
                now = datetime.now()
                if now.time() >= CLOSE_CANCEL_TIME and now.weekday() < 5:
                    self._cancel_unfilled()
                    time.sleep(3600)  # 一小时后重试
                else:
                    time.sleep(60)

        t = threading.Thread(target=_check, daemon=True)
        t.start()

    def _cancel_unfilled(self):
        """取消所有未成交订单"""
        try:
            orders = self._trader.query_stock_orders(self._account, cancelable_only=True)
            count = 0
            for o in orders:
                try:
                    self._trader.cancel_order_stock_async(self._account, o.order_id)
                    count += 1
                except Exception:
                    pass
            logger.info(f"Auto-canceled {count} unfilled orders at market close")
        except Exception:
            pass

    async def close(self) -> None:
        self._initialized = False
        if self._trader:
            try:
                self._trader.stop()
            except Exception:
                pass
        logger.info("Real executor closed")
