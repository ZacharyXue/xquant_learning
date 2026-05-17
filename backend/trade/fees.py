"""
费率与滑点计算

所有交易 (真实/模拟/回测) 均通过此模块计算费用。
"""

from dataclasses import dataclass

from backend.core.config import settings


@dataclass
class TradeCost:
    """单笔交易费用明细"""
    commission: float = 0.0       # 佣金
    stamp_tax: float = 0.0        # 印花税 (仅卖出)
    transfer_fee: float = 0.0     # 过户费
    slippage_cost: float = 0.0    # 滑点成本
    total: float = 0.0            # 总费用
    net_amount: float = 0.0       # 净成本/净收入 (成交金额 - 总费用)


class FeeCalculator:
    """费用计算器"""

    def __init__(self, config=None):
        if config is None:
            config = settings.fee
        self.commission_rate = config.commission_rate
        self.stamp_tax_rate = config.stamp_tax_rate
        self.transfer_fee_rate = config.transfer_fee_rate
        self.min_commission = config.min_commission

    def calc_trade_cost(self, price: float, volume: int, side: str) -> TradeCost:
        """计算单笔交易费用

        Args:
            price: 成交单价
            volume: 成交量 (股)
            side: "buy" / "sell"
        """
        amount = price * volume

        # 佣金
        commission = max(amount * self.commission_rate, self.min_commission)

        # 印花税 (仅卖出)
        stamp_tax = amount * self.stamp_tax_rate if side == "sell" else 0.0

        # 过户费
        transfer_fee = amount * self.transfer_fee_rate

        # 滑点成本 = 滑点率 * 金额
        slippage_cost = amount * self.slippage_rate

        total = commission + stamp_tax + transfer_fee + slippage_cost

        if side == "buy":
            net_amount = amount + total
        else:
            net_amount = amount - total

        return TradeCost(
            commission=round(commission, 4),
            stamp_tax=round(stamp_tax, 4),
            transfer_fee=round(transfer_fee, 4),
            slippage_cost=round(slippage_cost, 4),
            total=round(total, 4),
            net_amount=round(net_amount, 4),
        )

    @property
    def slippage_rate(self) -> float:
        return settings.slippage.rate

    def calc_slippage_price(self, price: float, side: str) -> float:
        """计算含滑点的预期成交价

        买入: 价格上浮 (买得更贵)
        卖出: 价格下浮 (卖得更便宜)
        """
        if side == "buy":
            return price * (1 + self.slippage_rate)
        else:
            return price * (1 - self.slippage_rate)


# 全局单例
fee_calculator = FeeCalculator()
