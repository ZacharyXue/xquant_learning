"""
模拟交易执行器

维护虚拟账户，按实时行情当前价成交。
计算完整的费率 (佣金/印花税/过户费/滑点)。
所有操作记录到 PostgreSQL。
"""

import asyncio
import time
from datetime import datetime
from typing import AsyncIterator, Optional

from backend.core.config import settings
from backend.core.logging import get_logger
from backend.grpc import trade_pb2
from backend.trade.base_executor import TradeExecutor
from backend.trade.fees import fee_calculator, TradeCost

logger = get_logger("sim_executor")


class SimAccount:
    """虚拟账户"""

    def __init__(self, initial_capital: float = None):
        if initial_capital is None:
            initial_capital = settings.trade.sim_initial_capital
        self.account_id = "SIM-001"
        self.initial_capital = initial_capital
        self.available_cash = initial_capital
        self.frozen_cash = 0.0
        self.positions: dict[str, dict] = {}  # stock_code -> {volume, avg_cost}
        self.trade_history: list[dict] = []
        self.order_seq = 0

    def _next_order_id(self) -> str:
        self.order_seq += 1
        return f"SIM-{int(time.time() * 1000)}-{self.order_seq:04d}"

    @property
    def market_value(self) -> float:
        total = 0.0
        for code, pos in self.positions.items():
            total += pos["current_price"] * pos["volume"]
        return total

    @property
    def total_asset(self) -> float:
        return self.available_cash + self.frozen_cash + self.market_value

    @property
    def total_profit_loss(self) -> float:
        return self.total_asset - self.initial_capital

    def can_buy(self, price: float, volume: int, cost: TradeCost) -> bool:
        needed = price * volume + cost.total
        return self.available_cash >= needed

    def can_sell(self, stock_code: str, volume: int) -> bool:
        pos = self.positions.get(stock_code, {})
        return pos.get("volume", 0) >= volume

    def apply_buy(self, stock_code: str, price: float, volume: int, cost: TradeCost) -> float:
        """执行买入，返回实际成交金额"""
        position = self.positions.get(stock_code, {"volume": 0, "avg_cost": 0.0, "current_price": price})
        old_volume = position["volume"]
        old_cost = position["avg_cost"]

        new_volume = old_volume + volume
        new_avg_cost = (old_cost * old_volume + price * volume) / new_volume if new_volume > 0 else 0

        self.positions[stock_code] = {
            "volume": new_volume,
            "avg_cost": round(new_avg_cost, 4),
            "current_price": price,
        }

        total_cost = price * volume + cost.total
        self.available_cash -= total_cost

        return total_cost

    def apply_sell(self, stock_code: str, price: float, volume: int, cost: TradeCost) -> float:
        """执行卖出，返回回笼资金"""
        position = self.positions.get(stock_code, {"volume": 0, "avg_cost": 0.0, "current_price": price})
        old_volume = position["volume"]
        new_volume = old_volume - volume

        if new_volume <= 0:
            self.positions.pop(stock_code, None)
        else:
            self.positions[stock_code] = {
                "volume": new_volume,
                "avg_cost": position["avg_cost"],
                "current_price": price,
            }

        proceeds = price * volume - cost.total
        self.available_cash += proceeds
        return proceeds


class SimTradeExecutor(TradeExecutor):
    """模拟交易执行器"""

    def __init__(self, config: dict = None):
        super().__init__(config)
        self._account: Optional[SimAccount] = None
        self._quote_cache: dict[str, trade_pb2.MarketDataTick] = {}
        self._quote_stream_active = False

    async def initialize(self) -> bool:
        self._account = SimAccount()
        self._initialized = True
        logger.info(f"Sim executor initialized, capital={self._account.initial_capital}")
        return True

    # ---- Order ----

    async def place_order(self, request: trade_pb2.OrderRequest) -> trade_pb2.OrderResponse:
        if not self._account:
            return trade_pb2.OrderResponse(success=False, error="Not initialized")

        # Get current price
        tick = self._quote_cache.get(request.stock_code)
        price = request.price if request.price > 0 else (tick.last_price if tick else 0)
        slippage_price = fee_calculator.calc_slippage_price(price, request.side)

        if price <= 0:
            return trade_pb2.OrderResponse(success=False, error=f"No price for {request.stock_code}")

        cost = fee_calculator.calc_trade_cost(slippage_price, request.volume, request.side)
        order_id = self._account._next_order_id()

        if request.side == "buy":
            if not self._account.can_buy(slippage_price, request.volume, cost):
                return trade_pb2.OrderResponse(
                    success=False, order_id=order_id,
                    error=f"Insufficient cash: need {slippage_price * request.volume + cost.total}, "
                          f"have {self._account.available_cash}",
                )
            self._account.apply_buy(request.stock_code, slippage_price, request.volume, cost)
        else:
            if not self._account.can_sell(request.stock_code, request.volume):
                return trade_pb2.OrderResponse(
                    success=False, order_id=order_id,
                    error=f"Insufficient position for {request.stock_code}",
                )
            self._account.apply_sell(request.stock_code, slippage_price, request.volume, cost)

        trade_record = {
            "order_id": order_id,
            "stock_code": request.stock_code,
            "side": request.side,
            "volume": request.volume,
            "order_price": request.price,
            "filled_price": slippage_price,
            "commission": cost.commission,
            "stamp_tax": cost.stamp_tax,
            "transfer_fee": cost.transfer_fee,
            "slippage": cost.slippage_cost,
            "amount": slippage_price * request.volume,
            "strategy_name": request.strategy_name,
            "order_remark": request.order_remark,
            "status": "filled",
            "trade_time": datetime.now(),
        }
        self._account.trade_history.append(trade_record)
        logger.info(f"SIM {request.side.upper()} {request.stock_code} x{request.volume} @ {slippage_price:.4f}")

        return trade_pb2.OrderResponse(
            success=True,
            order_id=order_id,
            estimated_fee=cost.total,
            slippage_price=slippage_price,
            order_price=request.price,
            order_volume=request.volume,
            status="filled",
        )

    async def cancel_order(self, request: trade_pb2.CancelRequest) -> trade_pb2.CancelResponse:
        return trade_pb2.CancelResponse(success=False, error="Sim orders execute immediately, nothing to cancel")

    # ---- Account ----

    async def get_account(self, request: trade_pb2.AccountRequest) -> trade_pb2.AccountResponse:
        if not self._account:
            return trade_pb2.AccountResponse(success=False)
        return trade_pb2.AccountResponse(
            success=True,
            account_id=self._account.account_id,
            total_asset=self._account.total_asset,
            available_cash=self._account.available_cash,
            frozen_cash=self._account.frozen_cash,
            market_value=self._account.market_value,
            total_profit_loss=self._account.total_profit_loss,
            today_profit_loss=0.0,
            trade_mode="sim",
        )

    async def get_positions(self, request: trade_pb2.PositionsRequest) -> trade_pb2.PositionsResponse:
        if not self._account:
            return trade_pb2.PositionsResponse(success=False)
        positions = []
        for code, pos in self._account.positions.items():
            mv = pos["volume"] * pos["current_price"]
            pl = mv - pos["avg_cost"] * pos["volume"]
            positions.append(trade_pb2.Position(
                stock_code=code,
                stock_name="",
                volume=pos["volume"],
                available_volume=pos["volume"],
                avg_cost=pos["avg_cost"],
                current_price=pos["current_price"],
                market_value=mv,
                profit_loss=pl,
                profit_loss_ratio=pl / (pos["avg_cost"] * pos["volume"]) if pos["avg_cost"] > 0 else 0,
                trade_mode="sim",
            ))
        return trade_pb2.PositionsResponse(success=True, positions=positions)

    async def get_orders(self, request: trade_pb2.OrdersRequest) -> trade_pb2.OrdersResponse:
        return trade_pb2.OrdersResponse(success=True, orders=[])

    async def get_trades(self, request: trade_pb2.TradesRequest) -> trade_pb2.TradesResponse:
        trades = []
        for i, t in enumerate(self._account.trade_history if self._account else []):
            trades.append(trade_pb2.Trade(
                trade_id=str(i + 1),
                order_id=t.get("order_id", ""),
                stock_code=t["stock_code"],
                side=t["side"],
                trade_volume=t["volume"],
                trade_price=t["filled_price"],
                trade_amount=t["amount"],
                commission=t["commission"],
                stamp_tax=t["stamp_tax"],
                transfer_fee=t["transfer_fee"],
                trade_time=t["trade_time"].isoformat(),
            ))
        return trade_pb2.TradesResponse(success=True, trades=trades)

    # ---- Market Data ----

    async def subscribe_quotes(self, stock_codes: list[str]) -> AsyncIterator[trade_pb2.MarketDataTick]:
        self._quote_stream_active = True
        try:
            while self._quote_stream_active:
                for code in stock_codes:
                    tick = self._quote_cache.get(code)
                    if tick:
                        yield tick
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            self._quote_stream_active = False

    async def get_history_kline(self, request: trade_pb2.KlineRequest) -> trade_pb2.KlineResponse:
        return trade_pb2.KlineResponse(success=False, error="Sim mode: no historical data source configured")

    async def get_stock_list(self, request: trade_pb2.StockListRequest) -> trade_pb2.StockListResponse:
        return trade_pb2.StockListResponse(success=True, stocks=[])

    async def close(self) -> None:
        self._quote_stream_active = False
        self._initialized = False
        logger.info("Sim executor closed")
