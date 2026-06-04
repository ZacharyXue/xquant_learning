"""Strategy base classes: Quote, Signal, StrategyBase"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Quote:
    stock_code: str
    last_price: float
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    last_close: float = 0.0
    volume: int = 0
    amount: float = 0.0
    time: datetime = field(default_factory=datetime.now)


@dataclass
class Signal:
    stock_code: str
    side: str          # "buy" | "sell" | "skip"
    volume: int = 0
    price: float = 0.0
    reason: str = ""
    indicators: dict = field(default_factory=dict)


class StrategyBase(ABC):
    """Base strategy class.

    Subclasses must define `name` and implement `on_quote()`.
    Both backtest and live trading share the same on_quote method.
    """

    name: str = ""
    display_name: str = ""
    description: str = ""
    watched_stocks: list[str] = []

    def __init__(self, config: dict = None):
        self._config = config or {}
        for k, v in self._config.items():
            if hasattr(self, k):
                setattr(self, k, v)

    @abstractmethod
    def on_quote(self, quote: Quote) -> Optional[Signal]:
        """Receive market data, return a trading signal or None."""
        ...

    def get_config_schema(self) -> dict:
        return {"type": "object", "properties": {}}

    def get_tuning_space(self) -> list[dict]:
        return []

    def update_params(self, params: dict) -> None:
        for k, v in params.items():
            if hasattr(self, k):
                setattr(self, k, v)
