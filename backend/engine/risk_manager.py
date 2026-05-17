"""
风控管理器

控制仓位上限、资金管理、下单频率等风险限制。
"""

from dataclasses import dataclass

from backend.core.config import settings
from backend.core.logging import get_logger

logger = get_logger("risk_manager")


@dataclass
class RiskLimits:
    """风控限制参数"""
    max_position_per_stock: int = 10000     # 单只股票最大持仓 (股)
    max_position_ratio: float = 0.3        # 单只股票最大仓位比例
    max_total_positions: int = 5            # 最大持仓股票数
    max_order_frequency: int = 5            # 每分钟最大下单次数
    min_cash_reserve: float = 1000.0       # 最低现金保留


class RiskManager:
    """风控管理器"""

    def __init__(self, limits: RiskLimits = None):
        self.limits = limits or RiskLimits(
            max_position_per_stock=settings.trade.max_position_per_stock,
            max_position_ratio=0.3,
            max_total_positions=5,
            max_order_frequency=5,
            min_cash_reserve=1000.0,
        )
        self._order_counters: dict[str, int] = {}  # 分钟级下单计数

    def check_buy(
        self,
        stock_code: str,
        volume: int,
        price: float,
        current_positions: dict[str, dict],
        available_cash: float,
        total_asset: float,
    ) -> tuple[bool, str]:
        """检查买入是否符合风控

        Returns:
            (allowed, reason)
        """
        # 持仓数量检查
        current_count = len([p for p in current_positions.values() if p.get("volume", 0) > 0])
        if current_count >= self.limits.max_total_positions:
            return False, f"Max total positions ({self.limits.max_total_positions}) reached"

        # 单只股票仓位检查
        position = current_positions.get(stock_code, {})
        current_vol = position.get("volume", 0)
        if current_vol + volume > self.limits.max_position_per_stock:
            return False, f"Max position per stock ({self.limits.max_position_per_stock}) exceeded"

        # 仓位比例检查
        order_amount = price * volume
        if total_asset > 0 and order_amount / total_asset > self.limits.max_position_ratio:
            return False, f"Position ratio ({self.limits.max_position_ratio}) exceeded"

        # 资金检查
        total_needed = order_amount  # 不含费用
        if available_cash - total_needed < self.limits.min_cash_reserve:
            return False, f"Insufficient cash (need {total_needed}, have {available_cash}, reserve {self.limits.min_cash_reserve})"

        return True, "OK"

    def check_sell(
        self, stock_code: str, volume: int, current_positions: dict[str, dict],
    ) -> tuple[bool, str]:
        """检查卖出是否符合风控"""
        position = current_positions.get(stock_code, {})
        current_vol = position.get("volume", 0)
        if current_vol < volume:
            return False, f"Insufficient position ({current_vol} < {volume})"
        return True, "OK"

    def record_order(self, stock_code: str) -> bool:
        """记录下单，检查频率"""
        import time
        minute_key = time.strftime("%Y%m%d%H%M")
        count = self._order_counters.get(minute_key, 0)
        if count >= self.limits.max_order_frequency:
            return False
        self._order_counters[minute_key] = count + 1
        return True
