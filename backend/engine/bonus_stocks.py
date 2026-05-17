"""
红利ETF定投策略 (Bonus Stocks)

每周三在交易时段内评估 ETF 指标：
- RSI(14): 超买不买，超卖加仓
- 250日均线乖离率: 正乖离过大不买，负乖离加仓
- 开盘变化率: 跳空过大减少买入量

信号通过 SignalBus 发布，经风控检查后发送到交易执行器。
"""

from datetime import datetime
from typing import Optional

from backend.core.logging import get_logger
from backend.core.trading_calendar import is_trading_time, is_investment_day
from backend.engine.strategy_base import StrategyBase, Signal, Quote
from backend.engine.strategy_registry import register
from backend.engine.indicators import calc_rsi, calc_ma, calc_bias, calc_open_change, round_to_lot

logger = get_logger("strategy.bonus_stocks")


DEFAULT_PARAMS = {
    "investment_days": ["Wednesday"],
    "base_volume": 500,
    "lot_size": 100,
    "rsi_period": 14,
    "rsi_overbought": 70,
    "rsi_oversold": 30,
    "rsi_additional": 100,
    "bias_ma_period": 250,
    "bias_upper": 0.10,
    "bias_lower": -0.10,
    "bias_additional": 100,
    "open_change_threshold": 0.01,
}


@register
class BonusStocksStrategy(StrategyBase):
    """红利ETF定投策略"""

    name = "bonus_stocks"
    display_name = "红利ETF定投"
    description = "每周三基于RSI和均线乖离率择时买入红利ETF"

    def __init__(self, config: dict = None):
        super().__init__(config)
        self._price_history: dict[str, list[float]] = {}  # stock_code -> [prices]
        self._last_trade_date: Optional[str] = None
        self._indicators_cache: dict[str, dict] = {}

    @property
    def params(self) -> dict:
        return {**DEFAULT_PARAMS, **self._config}

    async def on_quote(self, quote: Quote) -> Optional[Signal]:
        # 检查交易时间
        now = datetime.now()
        if not is_trading_time(now):
            return None

        # 检查定投日
        days = self.params["investment_days"]
        if not is_investment_day(now, days):
            return None

        # 更新价格历史
        self._update_price_history(quote)

        # 计算指标
        indicators = self._calc_indicators(quote.stock_code, quote.last_price, quote.open)
        if not indicators:
            return None

        # 决策
        volume = self._decide_volume(indicators)
        if volume <= 0:
            return Signal(
                stock_code=quote.stock_code,
                side="skip",
                reason=indicators.get("skip_reason", "No signal"),
                indicators=indicators,
            )

        volume = round_to_lot(volume, self.params["lot_size"])
        return Signal(
            stock_code=quote.stock_code,
            side="buy",
            volume=volume,
            reason=indicators.get("buy_reason", ""),
            indicators=indicators,
        )

    def _update_price_history(self, quote: Quote):
        code = quote.stock_code
        if code not in self._price_history:
            self._price_history[code] = []
        prices = self._price_history[code]
        prices.append(quote.last_price)
        # 保留最近 400 天
        if len(prices) > 400:
            self._price_history[code] = prices[-400:]

    def _calc_indicators(self, stock_code: str, last_price: float, open_price: float) -> Optional[dict]:
        prices = self._price_history.get(stock_code, [])
        if len(prices) < max(self.params["rsi_period"], self.params["bias_ma_period"]) + 1:
            logger.debug(f"{stock_code}: insufficient price data ({len(prices)})")
            return None

        rsi_value = calc_rsi(prices, self.params["rsi_period"])
        ma_value = calc_ma(prices, self.params["bias_ma_period"])
        bias_value = calc_bias(last_price, ma_value)
        last_close = prices[-2] if len(prices) >= 2 else open_price
        open_change = calc_open_change(open_price, last_close)

        return {
            "rsi": rsi_value,
            "ma": ma_value,
            "bias": bias_value,
            "open_change": open_change,
            "last_price": last_price,
        }

    def _decide_volume(self, indicators: dict) -> int:
        p = self.params
        base = p["base_volume"]
        additional = 0
        reasons = []

        rsi = indicators["rsi"]
        bias = indicators["bias"]
        open_change = indicators["open_change"]

        # RSI 判断
        if rsi > p["rsi_overbought"]:
            return 0  # 超买，不买
        elif rsi < p["rsi_oversold"]:
            additional += p["rsi_additional"]
            reasons.append(f"RSI超卖({rsi:.1f})")

        # 乖离率判断
        if bias > p["bias_upper"]:
            return 0  # 正乖离过大，不买
        elif bias < p["bias_lower"]:
            additional += p["bias_additional"]
            reasons.append(f"负乖离({bias:.3f})")

        # 开盘跳空调整
        if abs(open_change) > p["open_change_threshold"]:
            ratio = p["open_change_threshold"] / abs(open_change)
            additional = int(additional * ratio)
            reasons.append(f"跳空调整(x{ratio:.2f})")

        volume = base + additional
        indicators["buy_reason"] = " | ".join(reasons) if reasons else "定投"
        indicators["base_volume"] = base
        indicators["additional_volume"] = additional
        indicators["final_volume"] = volume

        return volume

    def get_config_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "investment_days": {
                    "type": "array", "items": {"type": "string"},
                    "title": "定投日", "default": ["周三"],
                },
                "base_volume": {
                    "type": "integer", "title": "基础份数",
                    "default": 500, "minimum": 100, "step": 100,
                },
                "lot_size": {
                    "type": "integer", "title": "每手股数",
                    "default": 100, "minimum": 1,
                },
                "rsi_period": {
                    "type": "integer", "title": "RSI周期",
                    "default": 14, "minimum": 5, "maximum": 50,
                },
                "rsi_overbought": {
                    "type": "integer", "title": "RSI超买阈值",
                    "default": 70, "minimum": 50, "maximum": 90,
                },
                "rsi_oversold": {
                    "type": "integer", "title": "RSI超卖阈值",
                    "default": 30, "minimum": 10, "maximum": 50,
                },
                "rsi_additional": {
                    "type": "integer", "title": "RSI超卖加仓",
                    "default": 100, "minimum": 0, "maximum": 500,
                },
                "bias_ma_period": {
                    "type": "integer", "title": "均线周期",
                    "default": 250, "minimum": 50, "maximum": 500,
                },
                "bias_upper": {
                    "type": "number", "title": "乖离率上限",
                    "default": 0.10, "minimum": 0.01, "maximum": 0.50,
                },
                "bias_lower": {
                    "type": "number", "title": "乖离率下限",
                    "default": -0.10, "minimum": -0.50, "maximum": -0.01,
                },
                "bias_additional": {
                    "type": "integer", "title": "负乖离加仓",
                    "default": 100, "minimum": 0, "maximum": 500,
                },
                "open_change_threshold": {
                    "type": "number", "title": "开盘跳空阈值",
                    "default": 0.01, "minimum": 0.001, "maximum": 0.10,
                },
            },
        }
