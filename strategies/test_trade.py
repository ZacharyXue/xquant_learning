"""One-shot test trade strategy — buys specified stock once and stops"""

from datetime import datetime
from typing import Optional

from engine.strategy_base import StrategyBase, Quote, Signal
from engine.strategy_registry import register


@register
class TestTradeStrategy(StrategyBase):
    """Test trade: buy specified stock x specified volume at current price, once."""

    name = "test_trade"
    display_name = "Test Trade"
    description = "One-shot buy order for testing"
    watched_stocks = ["520990.SH"]

    def __init__(self, config: dict = None):
        super().__init__(config)
        self._executed: bool = False
        self._target_code: str = config.get("stock_code", "520990.SH") if config else "520990.SH"
        self._target_volume: int = int(config.get("volume", 400)) if config else 400
        self.watched_stocks = [self._target_code]

    def on_quote(self, quote: Quote) -> Optional[Signal]:
        if self._executed:
            return None

        # Only trade within market hours
        t = quote.time
        if t.hour < 9 or (t.hour == 9 and t.minute < 30):
            return None
        if t.hour >= 15:
            return None
        if t.hour == 11 and t.minute >= 30:
            return None
        if t.hour == 12:
            return None

        code = quote.stock_code
        if code != self._target_code:
            return None

        self._executed = True
        return Signal(
            stock_code=code,
            side="buy",
            volume=self._target_volume,
            price=quote.last_price,
            reason=f"Test trade: buy {self._target_volume} shares at market",
            indicators={
                "last_price": quote.last_price,
                "open": quote.open,
                "last_close": quote.last_close,
            },
        )
