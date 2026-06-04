"""Fee calculation (commission, stamp tax, transfer fee, slippage)"""

from dataclasses import dataclass


@dataclass
class TradeCost:
    commission: float = 0.0
    stamp_tax: float = 0.0
    transfer_fee: float = 0.0
    slippage_cost: float = 0.0
    total: float = 0.0
    net_amount: float = 0.0


class FeeCalculator:
    def __init__(self, commission_rate: float = 0.00025, stamp_tax_rate: float = 0.001,
                 transfer_fee_rate: float = 0.00002, min_commission: float = 5.0,
                 slippage_rate: float = 0.001):
        self.commission_rate = commission_rate
        self.stamp_tax_rate = stamp_tax_rate
        self.transfer_fee_rate = transfer_fee_rate
        self.min_commission = min_commission
        self.slippage_rate = slippage_rate

    def calc_trade_cost(self, price: float, volume: int, side: str) -> TradeCost:
        amount = price * volume
        commission = max(amount * self.commission_rate, self.min_commission)
        stamp_tax = amount * self.stamp_tax_rate if side == "sell" else 0.0
        transfer_fee = amount * self.transfer_fee_rate
        slippage = amount * self.slippage_rate
        total = commission + stamp_tax + transfer_fee + slippage
        net = amount + total if side == "buy" else amount - total
        return TradeCost(
            commission=round(commission, 4), stamp_tax=round(stamp_tax, 4),
            transfer_fee=round(transfer_fee, 4), slippage_cost=round(slippage, 4),
            total=round(total, 4), net_amount=round(net, 4),
        )

    def calc_slippage_price(self, price: float, side: str) -> float:
        if side == "buy":
            return round(price * (1 + self.slippage_rate), 4)
        else:
            return round(price * (1 - self.slippage_rate), 4)
