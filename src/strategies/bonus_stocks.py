"""
红利ETF定投策略

在候选红利ETF（json文件配置）中选择合适的ETF进行定投

定投时间：每周周三（json文件配置，默认值为"周三"）
定投数量：json文件配置，单位为股
定投策略为多个短期指标指导买入额度，或者取消买入
- 计算 RSI，大于 60 时不买入，小于 20 时不额外增加
- 计算乖离率（乖离率 = (现价 - 250 均线) / 250 均线），超过 5% 时不买入，小于 -15% 时不额外增加
- 计算当日开盘价相比前日的涨幅，涨幅超过 1% 时减少买入份额

# 代码要求

- 记录每周三的各项指标值，以及最后的买入股数
- 获得的最后股数一定是 100 的整数倍
- 存在多个候选ETF时，最后选择计算后买入股数最大的ETF进行交易，记录比较结果
"""

import json
import os
from datetime import datetime, timedelta
from typing import Optional
from dataclasses import dataclass

try:
    from utils.logger import get_logger
    from utils.config import Config
    _LEGACY_AVAILABLE = True
except ImportError:
    get_logger = None  # type: ignore
    Config = None  # type: ignore
    _LEGACY_AVAILABLE = False

try:
    import xtquant.xtdata as xtdata
    _XTQUANT_AVAILABLE = True
except ImportError:
    xtdata = None  # type: ignore
    _XTQUANT_AVAILABLE = False

from .strategy_utils import (
    calculate_rsi,
    calculate_ma,
    calculate_bias_rate,
    calculate_open_change_ratio,
    round_to_lot_size,
    is_investment_day,
)

try:
    from ..trade_db import record_buy
except ImportError:
    record_buy = None  # type: ignore

if _LEGACY_AVAILABLE:
    _logger = get_logger("bonus_stocks")
else:
    import logging
    _logger = logging.getLogger("bonus_stocks")


@dataclass
class ETFConfig:
    """ETF配置"""
    code: str
    name: str


@dataclass
class StrategyParams:
    """策略超参数"""
    rsi_period: int = 14
    rsi_overbought: float = 70
    rsi_oversold: float = 30
    rsi_additional: int = 100

    bias_ma_period: int = 250
    bias_upper: float = 0.1
    bias_lower: float = -0.1
    bias_additional: int = 100

    open_change_threshold: float = 0.01


@dataclass
class IndicatorResult:
    """指标计算结果"""
    etf_code: str
    rsi: Optional[float]
    bias: Optional[float]
    open_change: Optional[float]
    ma250: Optional[float]

    should_buy: bool
    additional_volume: int
    base_volume: int
    final_volume: int

    buy_reason: str
    skip_reason: str


class BonusStocksConfig:
    """红利ETF定投策略配置"""

    def __init__(self, config_path: str = None, base_config: Config = None):
        # 支持直接传入配置文件路径
        if config_path and not base_config:
            with open(config_path, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
            self.logger = _logger
        elif base_config:
            self.config = base_config.config.copy()
            self.logger = base_config.logger
            # 加载bonus_stocks策略专用配置
            bonus_config_path = "config/bonus_stocks.json"
            with open(bonus_config_path, 'r', encoding='utf-8') as f:
                bonus_config = json.load(f)
            self.config.update(bonus_config)
        else:
            # 默认配置路径
            bonus_config_path = os.path.join(os.path.dirname(__file__), "bonus_stocks.json")
            with open(bonus_config_path, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
            self.logger = _logger

        self._parse_investment()
        self._parse_etfs()
        self._parse_params()

    @classmethod
    def init_config(cls, config: Config):
        """从基础配置初始化"""
        return cls(base_config=config)

    def _parse_investment(self):
        """解析定投配置"""
        inv = self.config.get("investment", {})
        self.investment_days = inv.get("days", ["周三"])
        self.base_volume = inv.get("base_volume", 500)
        self.lot_size = inv.get("lot_size", 100)

    def _parse_etfs(self):
        """解析ETF列表"""
        self.etfs = [
            ETFConfig(etf["code"], etf["name"])
            for etf in self.config.get("etfs", [])
        ]

    def _parse_params(self):
        """解析策略参数"""
        params = self.config.get("params", {})

        rsi_cfg = params.get("rsi", {})
        self.rsi_period = rsi_cfg.get("period", 14)
        self.rsi_overbought = rsi_cfg.get("overbought", 70)
        self.rsi_oversold = rsi_cfg.get("oversold", 30)
        self.rsi_additional = rsi_cfg.get("buy_additional", 100)

        bias_cfg = params.get("bias", {})
        self.bias_ma_period = bias_cfg.get("ma_period", 250)
        self.bias_upper = bias_cfg.get("upper_threshold", 0.1)
        self.bias_lower = bias_cfg.get("lower_threshold", -0.1)
        self.bias_additional = bias_cfg.get("buy_additional", 100)

        open_cfg = params.get("open_change", {})
        self.open_change_threshold = open_cfg.get("threshold", 0.01)

    def get_strategy_params(self) -> StrategyParams:
        """获取策略参数对象"""
        return StrategyParams(
            rsi_period=self.rsi_period,
            rsi_overbought=self.rsi_overbought,
            rsi_oversold=self.rsi_oversold,
            rsi_additional=self.rsi_additional,
            bias_ma_period=self.bias_ma_period,
            bias_upper=self.bias_upper,
            bias_lower=self.bias_lower,
            bias_additional=self.bias_additional,
            open_change_threshold=self.open_change_threshold
        )

    def get_etf_codes(self) -> list[str]:
        """获取所有ETF代码列表"""
        return [etf.code for etf in self.etfs]


class BonusStocksPolicy:
    """红利ETF定投策略"""

    def __init__(self, config):
        """
        初始化策略

        Args:
            config: Config对象或配置文件路径字符串
        """
        # 支持传入Config对象或配置文件路径
        if isinstance(config, str):
            self.config = BonusStocksConfig(config_path=config)
        else:
            self.config = BonusStocksConfig.init_config(config)

        self.logger = _logger
        self.params = self.config.get_strategy_params()

        # 价格历史数据 {etf_code: [prices]}
        self.price_history: dict[str, list[float]] = {}

        # 记录当前交易日的指标结果
        self.today_results: dict[str, IndicatorResult] = {}

        # 今日是否已执行过交易
        self.today_executed = False
        self.last_trade_date = None

        # 预加载历史数据
        self._load_historical_data()

    def _load_historical_data(self):
        """使用xtquant预加载历史数据（需要 QMT 运行时可用）"""
        if not _XTQUANT_AVAILABLE:
            self.logger.warning("xtquant 不可用，跳过历史数据加载（将使用实时数据累积）")
            for etf in self.config.etfs:
                self.price_history[etf.code] = []
            return

        self.logger.info("开始加载ETF历史数据...")

        # 需要获取足够的历史数据用于计算RSI和250日均线
        end_time = datetime.now().strftime("%Y%m%d")
        # 预取一年加一个月的数据（确保有足够的250日数据）
        start_time = (datetime.now() - timedelta(days=400)).strftime("%Y%m%d")

        for etf in self.config.etfs:
            try:
                # 先尝试下载历史数据
                xtdata.download_history_data(
                    stock_code=etf.code,
                    period='1d',
                    start_time=start_time,
                    end_time=end_time
                )

                # 获取历史K线数据
                data = xtdata.get_market_data(
                    field_list=['close'],
                    stock_list=[etf.code],
                    start_time=start_time,
                    end_time=end_time,
                    period='1d'
                )

                # data 格式为 {field: DataFrame}
                if 'close' in data:
                    df = data['close']
                    if etf.code in df.index:
                        close_prices = df.loc[etf.code].dropna().tolist()
                        self.price_history[etf.code] = close_prices
                        self.logger.info(f"加载 {etf.name}({etf.code}) 历史数据 {len(close_prices)} 条")
                    else:
                        self.logger.warning(f"无法获取 {etf.name}({etf.code}) 的历史数据")
                        self.price_history[etf.code] = []
                else:
                    self.logger.warning(f"无法获取 {etf.name}({etf.code}) 的历史数据")
                    self.price_history[etf.code] = []

            except Exception as e:
                self.logger.error(f"加载 {etf.name}({etf.code}) 历史数据失败: {e}")
                self.price_history[etf.code] = []

        self.logger.info("历史数据加载完成")

    def update_price(self, etf_code: str, price: float):
        """更新价格数据（兼容别名）"""
        self.update_price_from_realtime(etf_code, price)

    def update_price_from_realtime(self, etf_code: str, price: float):
        """从实时行情更新价格数据"""
        if etf_code not in self.price_history:
            self.price_history[etf_code] = []
        # 避免重复添加同一价格
        if not self.price_history[etf_code] or self.price_history[etf_code][-1] != price:
            self.price_history[etf_code].append(price)

    def calculate_indicators(self, etf_code: str, data: dict) -> IndicatorResult:
        """
        计算单个ETF的各项指标

        Args:
            etf_code: ETF代码
            data: 市场数据

        Returns:
            IndicatorResult: 指标计算结果
        """
        etf_data = data.get(etf_code, {})
        if not etf_data:
            return self._create_empty_result(etf_code, "数据为空")

        prices = self.price_history.get(etf_code, [])
        current_price = etf_data.get("lastPrice", 0)
        open_price = etf_data.get("open", 0)
        last_close = etf_data.get("lastClose", 0)

        # 计算RSI
        rsi = calculate_rsi(prices, self.params.rsi_period)

        # 计算250日均线
        ma250 = calculate_ma(prices, self.params.bias_ma_period)

        # 计算乖离率
        bias = None
        if ma250 is not None and current_price > 0:
            bias = calculate_bias_rate(current_price, ma250)

        # 计算开盘涨幅
        open_change = None
        if last_close > 0:
            open_change = calculate_open_change_ratio(open_price, last_close)

        # 判断是否买入
        should_buy = True
        additional_volume = 0
        skip_reason = ""
        buy_reason = []

        # RSI判断
        if rsi is not None:
            if rsi > self.params.rsi_overbought:
                should_buy = False
                skip_reason = f"RSI({rsi:.1f}) > {self.params.rsi_overbought} (超买)"
            elif rsi < self.params.rsi_oversold:
                additional_volume += self.params.rsi_additional
                buy_reason.append(f"RSI({rsi:.1f}) < {self.params.rsi_oversold} (+{self.params.rsi_additional}份)")

        # 乖离率判断
        if bias is not None:
            if bias > self.params.bias_upper:
                should_buy = False
                skip_reason = f"乖离率({bias:.2%}) > {self.params.bias_upper:.0%} (偏离过大)"
            elif bias < self.params.bias_lower:
                additional_volume += self.params.bias_additional
                buy_reason.append(f"乖离率({bias:.2%}) < {self.params.bias_lower:.0%} (+{self.params.bias_additional}份)")

        # 开盘涨幅判断
        if open_change is not None:
            if abs(open_change) > self.params.open_change_threshold:
                # 开盘涨幅超过阈值，减少买入（不取消，只减少）
                reduce_ratio = min(abs(open_change) / self.params.open_change_threshold - 1, 1)
                additional_volume = int(additional_volume * (1 - reduce_ratio))
                buy_reason.append(f"开盘涨幅({open_change:.2%})较大，减少份额")

        # 计算最终买入股数
        if should_buy:
            final_volume = self.config.base_volume + additional_volume
            # 不在这里取整，保留精确值用于ETF间比较
            if not buy_reason:
                buy_reason.append(f"各指标正常，按基础份额买入")
        else:
            final_volume = 0

        if not buy_reason:
            buy_reason_str = skip_reason if not should_buy else "各指标正常，按基础份额买入"
        else:
            buy_reason_str = "; ".join(buy_reason)

        return IndicatorResult(
            etf_code=etf_code,
            rsi=rsi,
            bias=bias,
            open_change=open_change,
            ma250=ma250,
            should_buy=should_buy,
            additional_volume=additional_volume,
            base_volume=self.config.base_volume,
            final_volume=final_volume,
            buy_reason=buy_reason_str,
            skip_reason=skip_reason
        )

    def _create_empty_result(self, etf_code: str, reason: str) -> IndicatorResult:
        """创建空结果"""
        return IndicatorResult(
            etf_code=etf_code,
            rsi=None,
            bias=None,
            open_change=None,
            ma250=None,
            should_buy=False,
            additional_volume=0,
            base_volume=self.config.base_volume,
            final_volume=0,
            buy_reason="",
            skip_reason=reason
        )

    def evaluate_and_select(self, data: dict) -> tuple[Optional[IndicatorResult], dict[str, IndicatorResult]]:
        """
        评估所有ETF并选择最优

        Args:
            data: 市场数据

        Returns:
            tuple: (最优ETF结果, 所有结果字典)
        """
        results = {}
        best_result = None

        for etf in self.config.etfs:
            result = self.calculate_indicators(etf.code, data)
            results[etf.code] = result

            # 选择买入股数最大的ETF
            if best_result is None or result.final_volume > best_result.final_volume:
                best_result = result

        return best_result, results

    def should_invest_today(self, now: datetime) -> bool:
        """检查今天是否为定投日"""
        return is_investment_day(now, self.config.investment_days)

    def print_indicators_report(
        self,
        now: datetime,
        results: dict[str, IndicatorResult]
    ):
        """打印指标报告"""
        self.logger.info("=" * 60)
        self.logger.info(f"【定投日指标报告】{now.strftime('%Y-%m-%d %A')}")

        for etf in self.config.etfs:
            result = results.get(etf.code)
            if result is None:
                continue

            self.logger.info("-" * 60)
            self.logger.info(f"ETF: {etf.name} ({etf.code})")
            self.logger.info(f"  RSI(14):     {result.rsi:.2f}" if result.rsi else "  RSI(14):     N/A")
            self.logger.info(f"  250日均线:   {result.ma250:.4f}" if result.ma250 else "  250日均线:   N/A")
            self.logger.info(f"  乖离率:      {result.bias:.2%}" if result.bias else "  乖离率:      N/A")
            self.logger.info(f"  开盘涨幅:    {result.open_change:.2%}" if result.open_change else "  开盘涨幅:    N/A")

            if result.should_buy:
                self.logger.info(f"  基础份额:    {result.base_volume}份")
                self.logger.info(f"  加减份额:    {'+' if result.additional_volume >= 0 else ''}{result.additional_volume}份")
                self.logger.info(f"  最终份额:    {result.final_volume // self.config.lot_size}份 ({result.final_volume}股)")
                self.logger.info(f"  买入原因:    {result.buy_reason}")
            else:
                self.logger.info(f"  最终份额:    0 (不买入)")
                self.logger.info(f"  跳过原因:    {result.skip_reason}")

        self.logger.info("=" * 60)

    def __call__(self, data: dict) -> Optional[dict]:
        """
        策略调用入口，与 DataProcessor 集成

        Args:
            data: 行情数据 {stock_code: {lastPrice, open, lastClose, ...}}

        Returns:
            dict: 交易指令 {stock_code: {stock_code, type, volume, price}} 或 None
        """
        now = datetime.now()

        # 检查是否跨天，重置交易状态
        today = now.date()
        if self.last_trade_date != today:
            self.today_executed = False
            self.last_trade_date = today

        # 非交易时间不处理
        if (now.hour < 9 or (now.hour == 9 and now.minute < 30)) or \
           (now.hour > 14 or (now.hour == 14 and now.minute >= 55)):
            return None

        # 更新实时价格数据
        for etf in self.config.etfs:
            if etf.code in data and "lastPrice" in data[etf.code]:
                self.update_price_from_realtime(etf.code, data[etf.code]["lastPrice"])

        # 非定投日不交易
        if not self.should_invest_today(now):
            self.logger.debug(f"{now} 非定投日，跳过")
            return None

        # 今日已执行过则跳过
        if self.today_executed:
            self.logger.debug(f"{now} 今日已完成定投，跳过")
            return None

        # 评估并选择最优ETF
        best_result, all_results = self.evaluate_and_select(data)

        # 打印报告
        self.print_indicators_report(now, all_results)

        # 无有效结果或不应买入
        if best_result is None or not best_result.should_buy or best_result.final_volume == 0:
            self.logger.info("今日不进行定投买入")
            self.today_executed = True  # 标记今日已处理
            return None

        # 查找ETF名称
        etf_name = ""
        for etf in self.config.etfs:
            if etf.code == best_result.etf_code:
                etf_name = etf.name
                break

        # 在最终确定购买前取整到可买的数量（100的整数倍）
        final_volume = round_to_lot_size(best_result.final_volume, self.config.lot_size)
        self.logger.info(f"【最终决策】买入 {etf_name}({best_result.etf_code}) {final_volume}股")

        # 记录交易到数据库
        etf_code = best_result.etf_code
        current_price = data.get(etf_code, {}).get("lastPrice", 0) if etf_code in data else 0
        extra = {
            "rsi": best_result.rsi,
            "bias": best_result.bias,
            "open_change": best_result.open_change,
            "ma250": best_result.ma250,
            "base_volume": best_result.base_volume,
            "additional_volume": best_result.additional_volume,
            "raw_volume": best_result.final_volume,  # 取整前的精确值
            "buy_reason": best_result.buy_reason,
        }
        record_buy(
            strategy="bonus_stocks",
            stock_code=etf_code,
            volume=final_volume,
            price=current_price,
            trade_time=now,
            stock_name=etf_name,
            extra=extra,
        )

        # 标记今日已执行
        self.today_executed = True

        return {
            best_result.etf_code: {
                "stock_code": best_result.etf_code,
                "type": "buy",
                "volume": final_volume,
                "price": 0
            }
        }


# ============================================================
# 平台集成: StrategyBase 兼容的策略类 (可被 TradeEngine 加载)
# ============================================================

try:
    from backend.engine.strategy_registry import register
    from backend.engine.strategy_base import StrategyBase, Signal, Quote
    _PLATFORM_AVAILABLE = True
except ImportError:
    _PLATFORM_AVAILABLE = False


if _PLATFORM_AVAILABLE:

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
        """红利ETF定投策略 (平台集成版本)"""

        name = "bonus_stocks"
        display_name = "红利ETF定投"
        description = "每周三基于RSI和均线乖离率择时买入红利ETF"

        watched_stocks = [
            "510880.SH",  # 红利ETF
            "159905.SZ",  # 深红利ETF
        ]

        def __init__(self, config: dict = None):
            super().__init__(config)
            self._price_history: dict[str, list[float]] = {}
            self._last_trade_date: Optional[str] = None

        @property
        def params(self) -> dict:
            return {**DEFAULT_PARAMS, **self._config}

        async def on_quote(self, quote: Quote) -> Optional[Signal]:
            now = datetime.now()

            # 交易时间检查
            if now.hour < 9 or (now.hour == 9 and now.minute < 30):
                return None
            if now.hour > 14 or (now.hour == 14 and now.minute >= 55):
                return None

            # 定投日检查
            days = self.params["investment_days"]
            if not is_investment_day(now, days):
                return None

            # 当日已处理则跳过
            today_str = now.strftime("%Y%m%d")
            if self._last_trade_date == today_str:
                return None

            # 更新价格历史
            code = quote.stock_code
            if code not in self._price_history:
                self._price_history[code] = []
            self._price_history[code].append(quote.last_price)
            if len(self._price_history[code]) > 400:
                self._price_history[code] = self._price_history[code][-400:]

            # 计算指标
            indicators = self._calc_indicators(code, quote.last_price, quote.open, quote.last_close)
            if not indicators:
                return None

            # 决策
            volume = self._decide_volume(indicators)
            if volume <= 0:
                return Signal(
                    stock_code=code,
                    side="skip",
                    reason=indicators.get("skip_reason", "不满足买入条件"),
                    indicators=indicators,
                )

            volume = round_to_lot_size(volume, self.params["lot_size"])
            self._last_trade_date = today_str

            return Signal(
                stock_code=code,
                side="buy",
                volume=volume,
                reason=indicators.get("buy_reason", "定投"),
                indicators=indicators,
            )

        def _calc_indicators(self, stock_code: str, last_price: float,
                            open_price: float, last_close: float) -> Optional[dict]:
            prices = self._price_history.get(stock_code, [])
            needed = max(self.params["rsi_period"], self.params["bias_ma_period"])
            if len(prices) < needed + 1:
                return None

            rsi_value = calculate_rsi(prices, self.params["rsi_period"])
            ma_value = calculate_ma(prices, self.params["bias_ma_period"])
            bias_value = calculate_bias_rate(last_price, ma_value) if ma_value else None
            open_change = calculate_open_change_ratio(open_price, last_close)

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
            skip_reason = ""

            rsi = indicators["rsi"]
            bias = indicators["bias"]
            open_change = indicators["open_change"]

            if rsi is not None:
                if rsi > p["rsi_overbought"]:
                    indicators["skip_reason"] = f"RSI({rsi:.1f}) > {p['rsi_overbought']} (超买)"
                    return 0
                elif rsi < p["rsi_oversold"]:
                    additional += p["rsi_additional"]
                    reasons.append(f"RSI超卖({rsi:.1f})")

            if bias is not None:
                if bias > p["bias_upper"]:
                    indicators["skip_reason"] = f"乖离率({bias:.2%}) > {p['bias_upper']:.0%} (偏离过大)"
                    return 0
                elif bias < p["bias_lower"]:
                    additional += p["bias_additional"]
                    reasons.append(f"负乖离({bias:.3f})")

            if open_change is not None and abs(open_change) > p["open_change_threshold"]:
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
                        "title": "定投日", "default": ["Wednesday"],
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

