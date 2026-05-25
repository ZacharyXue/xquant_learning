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


@dataclass
class TuneParam:
    """超参数优化搜索空间定义

    Attributes:
        name: 参数名 (对应 self.params 中的 key)
        type: 参数类型 "int" | "float" | "categorical"
        low: 下界 (int/float 类型)
        high: 上界 (int/float 类型)
        step: 步长 (离散参数; None 表示连续)
        choices: categorical 类型的候选项列表
        log_scale: 是否对数空间采样 (适用于跨越数量级的参数)
        constraints: 与其他参数的约束表达式, 如 "rsi_oversold < rsi_overbought"
    """
    name: str
    type: str = "int"
    low: float = 0.0
    high: float = 1.0
    step: float = None
    choices: list = None
    log_scale: bool = False
    constraints: str = ""


class StrategyBase(ABC):
    """策略基类

    Attributes:
        name: 策略唯一标识
        display_name: 策略显示名称
        description: 策略描述
        strategy_type: 策略类型 ("dca"|"buy_hold"|"momentum"|"custom"), 决定基准行为
        params: 策略可配置参数
    """

    name: str = "base"
    display_name: str = "基础策略"
    description: str = ""
    strategy_type: str = "dca"

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

    def get_baseline_config(self) -> dict:
        """返回基准行为配置

        引擎使用此配置决定如何构造基准对比。
        不同 strategy_type 有不同的默认实现。策略可覆盖。

        Returns:
            {
                "baseline_type": "dca" | "buy_hold" | "index",
                "index_code": str,          # baseline_type="index" 时使用
                "baseline_amount": float,   # DCA 基准每次定投金额
                "investment_days": list,    # DCA 基准定投日
                "lot_size": int,            # 每手股数
            }
        """
        return {
            "baseline_type": self.strategy_type,
            "index_code": "",
        }

    def get_tuning_space(self) -> list[TuneParam]:
        """返回策略可优化参数的搜索空间

        默认从 get_config_schema() 自动推导。策略可覆盖以定制搜索空间。
        """
        return self._derive_tuning_space_from_schema()

    def _derive_tuning_space_from_schema(self) -> list[TuneParam]:
        """从 JSON Schema 自动生成 TuneParam 列表

        推导规则:
        - type=integer + minimum/maximum → TuneParam(type="int", low, high)
        - type=number  + minimum/maximum → TuneParam(type="float", low, high)
        - type=array   + enum            → TuneParam(type="categorical", choices)
        - 有 step → 传递
        - 有 x_log_scale → log_scale=True
        - 有 x_constraints → 传递约束
        """
        schema = self.get_config_schema()
        properties = schema.get("properties", {})
        params = []
        for key, prop in properties.items():
            ptype = prop.get("type", "")
            tt = None
            if ptype == "integer":
                tt = "int"
                low = prop.get("minimum", 0)
                high = prop.get("maximum", 100)
                step = prop.get("step")
                params.append(TuneParam(
                    name=key, type=tt, low=low, high=high, step=step,
                ))
            elif ptype == "number":
                tt = "float"
                low = prop.get("minimum", 0.0)
                high = prop.get("maximum", 1.0)
                params.append(TuneParam(
                    name=key, type=tt, low=low, high=high,
                    log_scale=prop.get("x_log_scale", False),
                    constraints=prop.get("x_constraints", ""),
                ))
            elif ptype == "array" and "enum" in prop:
                params.append(TuneParam(
                    name=key, type="categorical", choices=prop["enum"],
                ))
        return params
