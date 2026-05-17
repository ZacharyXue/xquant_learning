"""
策略基类

所有交易策略必须继承 StrategyBase 并实现 on_quote 方法。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, Any

from backend.core.logging import get_logger


@dataclass
class Signal:
    """交易信号"""
    stock_code: str
    side: str                          # "buy" / "sell" / "skip"
    volume: int = 0
    price: float = 0.0                 # 0 = 市价
    reason: str = ""
    indicators: dict = field(default_factory=dict)  # RSI, MA, bias 等


@dataclass
class Quote:
    """行情数据"""
    stock_code: str
    last_price: float = 0.0
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    last_close: float = 0.0
    volume: float = 0.0
    amount: float = 0.0
    time: str = ""


class StrategyBase(ABC):
    """策略基类

    Attributes:
        name: 策略唯一标识
        display_name: 策略显示名称
        description: 策略描述
        params: 策略可配置参数
    """

    name: str = "base"
    display_name: str = "基础策略"
    description: str = ""

    def __init__(self, config: dict = None):
        self._config = config or {}
        self._logger = get_logger(f"strategy.{self.name}")
        self._enabled = False

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool):
        self._enabled = value
        self._logger.info(f"Strategy {self.name} {'enabled' if value else 'disabled'}")

    @abstractmethod
    async def on_quote(self, quote: Quote) -> Optional[Signal]:
        """处理行情数据，返回交易信号或 None"""

    def get_config_schema(self) -> dict:
        """返回参数 JSON Schema，供前端渲染表单"""
        return {
            "type": "object",
            "properties": {},
        }

    def update_params(self, params: dict) -> None:
        """更新策略参数 (从数据库或 API 加载)"""
        self._config.update(params)
