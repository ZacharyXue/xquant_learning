"""
订单状态管理器

跟踪订单从 pending → filled/partial/cancelled/rejected 的状态流转。
将交易记录持久化到 PostgreSQL。
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from backend.core.logging import get_logger

logger = get_logger("order_manager")


class OrderStatus(str, Enum):
    PENDING = "pending"
    FILLED = "filled"
    PARTIAL = "partial"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


class Order:
    """订单状态"""

    def __init__(
        self,
        order_id: str,
        stock_code: str,
        side: str,
        volume: int,
        price: float = 0.0,
        strategy_name: str = "",
        order_remark: str = "",
    ):
        self.order_id = order_id
        self.stock_code = stock_code
        self.side = side
        self.volume = volume
        self.price = price
        self.strategy_name = strategy_name
        self.order_remark = order_remark

        self.status = OrderStatus.PENDING
        self.filled_volume = 0
        self.filled_price = 0.0
        self.commission = 0.0
        self.stamp_tax = 0.0
        self.transfer_fee = 0.0
        self.slippage = 0.0
        self.error_msg = ""
        self.created_at = datetime.now()
        self.updated_at = datetime.now()


class OrderManager:
    """订单管理器"""

    def __init__(self, max_orders: int = 10000):
        self._orders: dict[str, Order] = {}
        self._max_orders = max_orders

    def create(
        self, order_id: str, stock_code: str, side: str, volume: int,
        price: float = 0.0, strategy_name: str = "", order_remark: str = "",
    ) -> Order:
        order = Order(
            order_id=order_id, stock_code=stock_code, side=side,
            volume=volume, price=price, strategy_name=strategy_name,
            order_remark=order_remark,
        )
        self._orders[order_id] = order

        # 清理老旧订单
        if len(self._orders) > self._max_orders:
            remove_keys = sorted(self._orders.keys())[:len(self._orders) - self._max_orders]
            for k in remove_keys:
                del self._orders[k]

        return order

    def update_status(
        self, order_id: str, status: OrderStatus,
        filled_volume: int = None, filled_price: float = None,
        error_msg: str = None,
    ) -> Optional[Order]:
        order = self._orders.get(order_id)
        if not order:
            return None

        order.status = status
        order.updated_at = datetime.now()
        if filled_volume is not None:
            order.filled_volume = filled_volume
        if filled_price is not None:
            order.filled_price = filled_price
        if error_msg is not None:
            order.error_msg = error_msg

        logger.debug(f"Order {order_id}: {status.value}, filled={order.filled_volume}/{order.volume}")
        return order

    def update_fees(
        self, order_id: str, commission: float = 0.0,
        stamp_tax: float = 0.0, transfer_fee: float = 0.0,
        slippage: float = 0.0,
    ) -> None:
        order = self._orders.get(order_id)
        if order:
            order.commission = commission
            order.stamp_tax = stamp_tax
            order.transfer_fee = transfer_fee
            order.slippage = slippage

    def get(self, order_id: str) -> Optional[Order]:
        return self._orders.get(order_id)

    def get_all(self, status: OrderStatus = None) -> list[Order]:
        orders = list(self._orders.values())
        if status:
            orders = [o for o in orders if o.status == status]
        return orders

    def get_pending(self) -> list[Order]:
        return self.get_all(OrderStatus.PENDING)

    def get_active_count(self) -> int:
        return len([o for o in self._orders.values() if o.status == OrderStatus.PENDING])

    def to_dict(self, order: Order) -> dict:
        return {
            "order_id": order.order_id,
            "stock_code": order.stock_code,
            "side": order.side,
            "volume": order.volume,
            "filled_volume": order.filled_volume,
            "order_price": order.price,
            "filled_price": order.filled_price,
            "commission": order.commission,
            "stamp_tax": order.stamp_tax,
            "transfer_fee": order.transfer_fee,
            "slippage": order.slippage,
            "status": order.status.value,
            "strategy_name": order.strategy_name,
            "order_remark": order.order_remark,
            "error_msg": order.error_msg,
            "created_at": order.created_at.isoformat(),
            "updated_at": order.updated_at.isoformat(),
        }
