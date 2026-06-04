"""Bonus stocks ETF DCA strategy — weekly Wednesday RSI+bias timing"""

from datetime import datetime
from typing import Optional
from engine.strategy_base import StrategyBase, Quote, Signal
from engine.strategy_registry import register
from engine.indicators import calc_rsi, calc_ma, calc_bias, calc_open_change, round_to_lot


DEFAULTS = {
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


def _is_investment_day(dt: datetime, days: list[str]) -> bool:
    chinese = ["周一","周二","周三","周四","周五","周六","周日"]
    english_full = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
    english_short = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]
    w = dt.weekday()
    variants = {chinese[w], english_full[w], english_short[w]}
    for d in days:
        if d in variants or d.lower() == english_full[w].lower():
            return True
    return False


@register
class BonusStocksStrategy(StrategyBase):
    name = "bonus_stocks"
    display_name = "Bonus ETF DCA"
    description = "Weekly Wednesday RSI+bias timed buy of bonus ETFs"
    watched_stocks = ["510880.SH", "159905.SZ"]

    def __init__(self, config: dict = None):
        super().__init__(config)
        self._price_history: dict[str, list[float]] = {}
        self._last_trade_date: str = ""
        for k, v in DEFAULTS.items():
            if not hasattr(self, k):
                setattr(self, k, v)

    def on_quote(self, quote: Quote) -> Optional[Signal]:
        code = quote.stock_code
        if code not in self._price_history:
            self._price_history[code] = []
        self._price_history[code].append(quote.last_close)
        if len(self._price_history[code]) > 450:
            self._price_history[code] = self._price_history[code][-450:]

        days = getattr(self, "investment_days", ["Wednesday"])
        if not _is_investment_day(quote.time, days):
            return None

        today_str = quote.time.strftime("%Y%m%d")
        if self._last_trade_date == today_str:
            return None

        prices = self._price_history.get(code, [])
        rsi_val = calc_rsi(prices, getattr(self, "rsi_period", 14))
        ma_val = calc_ma(prices, getattr(self, "bias_ma_period", 250))
        bias_val = calc_bias(quote.last_price, ma_val)
        open_change = calc_open_change(quote.open, quote.last_close)

        p = self
        base = getattr(p, "base_volume", 500)
        additional = 0
        reasons = []

        if rsi_val > getattr(p, "rsi_overbought", 70):
            return Signal(stock_code=code, side="skip",
                          reason=f"RSI({rsi_val:.1f}) overbought",
                          volume=0, price=quote.last_price,
                          indicators={"rsi": round(rsi_val, 2), "ma": round(ma_val, 4)})
        elif rsi_val < getattr(p, "rsi_oversold", 30):
            additional += getattr(p, "rsi_additional", 100)
            reasons.append(f"RSI oversold({rsi_val:.1f})")

        if bias_val > getattr(p, "bias_upper", 0.10):
            return Signal(stock_code=code, side="skip",
                          reason=f"Bias({bias_val:.2%}) too high",
                          volume=0, price=quote.last_price,
                          indicators={"rsi": round(rsi_val, 2), "bias": round(bias_val, 4)})
        elif bias_val < getattr(p, "bias_lower", -0.10):
            additional += getattr(p, "bias_additional", 100)
            reasons.append(f"Negative bias({bias_val:.2%})")

        if open_change is not None and abs(open_change) > getattr(p, "open_change_threshold", 0.01):
            ratio = getattr(p, "open_change_threshold", 0.01) / abs(open_change)
            additional = int(additional * ratio)
            reasons.append("gap adjustment")

        volume = base + additional
        volume = round_to_lot(volume, getattr(p, "lot_size", 100))
        if volume <= 0:
            return Signal(stock_code=code, side="skip", reason="volume zero",
                          volume=0, price=quote.last_price)

        reason_text = " | ".join(reasons) if reasons else "Regular DCA buy"
        self._last_trade_date = today_str

        return Signal(
            stock_code=code, side="buy", volume=volume, price=quote.last_price,
            reason=reason_text,
            indicators={
                "rsi": round(rsi_val, 2), "ma": round(ma_val, 4),
                "bias": round(bias_val, 4) if bias_val else None,
                "open_change": round(open_change, 4) if open_change else None,
                "base_volume": base, "additional_volume": additional,
                "final_volume": volume,
            },
        )

    def get_config_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "investment_days": {"type": "array", "items": {"type": "string"}, "title": "Investment days", "default": ["Wednesday"]},
                "base_volume": {"type": "integer", "title": "Base shares", "default": 500, "minimum": 100},
                "lot_size": {"type": "integer", "title": "Lot size", "default": 100},
                "rsi_period": {"type": "integer", "title": "RSI period", "default": 14, "minimum": 5, "maximum": 50},
                "rsi_overbought": {"type": "integer", "title": "RSI overbought", "default": 70, "minimum": 50, "maximum": 90},
                "rsi_oversold": {"type": "integer", "title": "RSI oversold", "default": 30, "minimum": 10, "maximum": 50},
                "rsi_additional": {"type": "integer", "title": "RSI oversold extra shares", "default": 100, "minimum": 0, "maximum": 500},
                "bias_ma_period": {"type": "integer", "title": "MA period", "default": 250, "minimum": 50, "maximum": 500},
                "bias_upper": {"type": "number", "title": "Bias upper limit", "default": 0.10, "minimum": 0.01, "maximum": 0.50},
                "bias_lower": {"type": "number", "title": "Bias lower limit", "default": -0.10, "minimum": -0.50, "maximum": -0.01},
                "bias_additional": {"type": "integer", "title": "Negative bias extra shares", "default": 100, "minimum": 0, "maximum": 500},
                "open_change_threshold": {"type": "number", "title": "Open gap threshold", "default": 0.01, "minimum": 0.001, "maximum": 0.10},
            },
        }

    def get_tuning_space(self) -> list[dict]:
        return [
            {"name": "rsi_period", "type": "int", "min": 5, "max": 50, "step": 1},
            {"name": "rsi_overbought", "type": "int", "min": 60, "max": 80, "step": 5},
            {"name": "rsi_oversold", "type": "int", "min": 20, "max": 40, "step": 5},
            {"name": "rsi_additional", "type": "int", "min": 0, "max": 300, "step": 50},
            {"name": "bias_ma_period", "type": "int", "min": 50, "max": 500, "step": 50},
            {"name": "bias_upper", "type": "float", "min": 0.03, "max": 0.20, "step": 0.01},
            {"name": "bias_lower", "type": "float", "min": -0.20, "max": -0.03, "step": 0.01},
            {"name": "bias_additional", "type": "int", "min": 0, "max": 300, "step": 50},
        ]
