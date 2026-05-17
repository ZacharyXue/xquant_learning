"""
回测引擎模块

根据历史数据模拟策略执行，记录买入点并输出结果。
支持两种策略:
1. buy_on_dips: 跌后买入策略 - 当价格下跌超过阈值时买入
2. bonus_stocks: 红利ETF定投策略 - 每周定投，结合RSI和乖离率指标

主要功能:
- 加载历史K线数据 (通过 history_data 模块)
- 根据策略逻辑模拟交易
- 计算回测指标 (收益率、夏普比率、最大回撤等)
- 输出交易记录和结果统计
"""

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

from .history_data import get_historical_kline


# ==================== 策略工具函数 ====================

def calculate_rsi(prices: list[float], period: int = 14) -> Optional[float]:
    """
    计算 RSI (Relative Strength Index) 相对强弱指标

    RSI 是衡量股票价格变动的速度和幅度的技术指标，取值范围 0-100:
    - RSI > 70: 超买区域，可能出现回调
    - RSI < 30: 超卖区域，可能出现反弹
    - RSI = 50: 多空平衡

    Args:
        prices: 价格列表
        period: RSI 周期，默认14天

    Returns:
        RSI 值 (0-100)，如果数据不足返回 None
    """
    # 需要至少 period+1 个数据点才能计算
    if len(prices) < period + 1:
        return None

    # 计算价格变动
    deltas = [prices[i] - prices[i - 1] for i in range(1, len(prices))]

    # 分离上涨和下跌
    gains = [d if d > 0 else 0 for d in deltas[-period:]]
    losses = [-d if d < 0 else 0 for d in deltas[-period:]]

    # 计算平均涨跌幅
    avg_gain = sum(gains) / period if gains else 0
    avg_loss = sum(losses) / period if losses else 0

    # 避免除零错误
    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else 50.0

    # 计算 RS 和 RSI
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def calculate_ma(prices: list[float], period: int) -> Optional[float]:
    """
    计算 MA (Moving Average) 移动平均线

    移动平均线是过去 N 天收盘价的平均值，用于判断价格趋势。
    常用周期: 5日、10日、20日、60日、120日、250日等

    Args:
        prices: 价格列表
        period: 均线周期

    Returns:
        均线值，如果数据不足返回 None
    """
    if len(prices) < period:
        return None
    return sum(prices[-period:]) / period


def calculate_bias_rate(current_price: float, ma_price: float) -> float:
    """
    计算 BIAS (Bias Rate) 乖离率

    乖离率 = (当前价格 - 均线价格) / 均线价格
    反映当前价格与均线的偏离程度:
    - 乖离率 > 0: 价格高于均线，可能回调
    - 乖离率 < 0: 价格低于均线，可能反弹

    Args:
        current_price: 当前价格
        ma_price: 均线价格

    Returns:
        乖离率 (如 0.1 表示高于均线 10%)
    """
    if ma_price <= 0:
        return 0.0
    return (current_price - ma_price) / ma_price


def is_investment_day(now: datetime, investment_days: list[str]) -> bool:
    """
    检查是否为定投日

    Args:
        now: 当前日期时间
        investment_days: 定投日列表，支持中文 ("周三") 或英文 ("Wed")

    Returns:
        True 是定投日，False 不是
    """
    # 支持中英文星期名称
    chinese_names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    english_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

    # Python weekday(): Monday=0, Sunday=6
    weekday = now.weekday()

    # 检查是否在定投日列表中
    return chinese_names[weekday] in investment_days or english_names[weekday] in investment_days


# ==================== 回测配置 ====================

# 默认配置参数
DEFAULT_CONFIG = {
    # 跌后买入策略配置
    "buy_on_dips": {
        "threshold": 0.99,       # 下跌阈值: 价格跌破前一天的 99% 时买入
        "order_volume": 100,      # 每次买入数量 (手)
    },
    # 红利ETF定投策略配置
    "bonus_stocks": {
        "investment_days": ["周三"],   # 定投日: 每周三
        "base_volume": 500,            # 基础买入数量
        "lot_size": 100,               # 交易单位: 每手100股
        "rsi_period": 14,              # RSI 周期
        "rsi_overbought": 70,          # RSI 超买阈值 (不买入)
        "rsi_oversold": 30,            # RSI 超卖阈值 (加仓)
        "bias_ma_period": 250,         # 乖离率均线周期 (250日均线)
        "bias_upper": 0.1,             # 乖离率上限 (不买入)
        "bias_lower": -0.1,            # 乖离率下限 (加仓)
    }
}


# ==================== 回测结果数据类 ====================

@dataclass
class BacktestResult:
    """
    回测结果数据类

    存储回测完成后产生的所有统计指标和交易记录
    """
    strategy: str              # 策略名称
    stock_code: str            # 股票代码
    start_time: str            # 回测开始日期 (YYYYMMDD)
    end_time: str              # 回测结束日期 (YYYYMMDD)

    # 交易统计
    total_trades: int = 0      # 总交易次数
    profitable_trades: int = 0  # 盈利交易次数

    # 资金统计
    total_investment: float = 0   # 总投入金额
    final_value: float = 0        # 最终持仓价值
    total_return: float = 0        # 总收益 (金额)
    return_rate: float = 0       # 总收益率 (小数形式)

    # 风险指标
    volatility: float = 0          # 波动率: 价格变化的标准差/均值
    sharpe_ratio: float = 0        # 夏普比率: (年化收益-无风险利率)/波动率
    annualized_return: float = 0   # 年化收益率
    max_drawdown: float = 0        # 最大回撤: (最高点-最低点)/最高点
    calmar_ratio: float = 0        # 卡玛比率: 年化收益/最大回撤
    win_rate: float = 0            # 胜率: 盈利次数/总次数

    # 详细数据
    buy_records: list = field(default_factory=list)  # 买入记录列表
    prices: list = field(default_factory=list)       # 价格序列
    times: list = field(default_factory=list)        # 时间序列

    def to_dict(self) -> dict:
        """
        转换为字典格式，用于 JSON 序列化

        Returns:
            包含所有字段的字典
        """
        return {
            "strategy": self.strategy,
            "stock_code": self.stock_code,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "total_trades": self.total_trades,
            "profitable_trades": self.profitable_trades,
            "total_investment": round(self.total_investment, 2),
            "final_value": round(self.final_value, 2),
            "total_return": round(self.total_return, 2),
            # 收益率转换为百分比形式
            "return_rate": round(self.return_rate * 100, 2),
            "volatility": round(self.volatility, 4),
            "sharpe_ratio": round(self.sharpe_ratio, 4),
            "annualized_return": round(self.annualized_return * 100, 2),
            "max_drawdown": round(self.max_drawdown, 4),
            "calmar_ratio": round(self.calmar_ratio, 4),
            "win_rate": round(self.win_rate, 4),
            "buy_records": self.buy_records,
            "prices": self.prices,
            "times": self.times,
        }


# ==================== 回测引擎类 ====================

class BacktestEngine:
    """
    回测引擎核心类

    负责:
    1. 加载历史数据
    2. 执行策略逻辑
    3. 计算回测指标
    """

    def __init__(self, strategy: str, stock_code: str, config: dict = None):
        """
        初始化回测引擎

        Args:
            strategy: 策略名称 ("buy_on_dips" 或 "bonus_stocks")
            stock_code: 股票代码 (如 "515650.SH")
            config: 策略参数配置，如果为 None 则使用默认配置
        """
        self.strategy = strategy
        self.stock_code = stock_code
        # 合并默认配置和自定义配置
        self.config = config or DEFAULT_CONFIG.get(strategy, {})

        # 存储数据
        self.prices = []      # 收盘价列表
        self.times = []       # 日期列表
        self.buy_records = []  # 买入记录列表

    def load_data(self, start_time: str, end_time: str) -> bool:
        """
        加载历史K线数据

        Args:
            start_time: 开始日期 (YYYYMMDD)
            end_time: 结束日期 (YYYYMMDD)

        Returns:
            加载成功返回 True，失败返回 False
        """
        # 调用 history_data 模块获取数据
        data = get_historical_kline(
            self.stock_code,
            start_time,
            end_time,
            fields=["close", "open", "high", "low", "volume"]
        )

        # 检查数据有效性
        if not data or not data.get("close"):
            print(f"无法加载 {self.stock_code} 的历史数据")
            return False

        # 存储数据
        self.prices = data.get("close", [])
        self.times = data.get("time", [])

        print(f"加载 {self.stock_code} 数据 {len(self.prices)} 条 ({self.times[0] if self.times else 'N/A'} - {self.times[-1] if self.times else 'N/A'})")
        return len(self.prices) > 0

    def run_buy_on_dips(self) -> BacktestResult:
        """
        运行跌后买入策略

        策略逻辑:
        - 每日比较当日收盘价与前一交易日收盘价
        - 如果价格跌幅超过 threshold，买入固定数量
        - threshold=0.99 表示跌幅超过 1% 时买入

        Returns:
            回测结果
        """
        # 获取策略参数
        threshold = self.config.get("threshold", 0.95)  # 下跌阈值
        order_volume = self.config.get("order_volume", 100)  # 买入数量
        last_price = None  # 记录前一交易日价格

        # 遍历所有交易日
        for i, (time, price) in enumerate(zip(self.times, self.prices)):
            if price <= 0:
                continue

            # 跳过第一天
            if last_price is None:
                last_price = price
                continue

            # 计算价格比率
            ratio = price / last_price

            # 如果价格跌幅超过阈值，买入
            if ratio < threshold:
                cost = price * order_volume
                self.buy_records.append({
                    "time": time,
                    "price": price,
                    "volume": order_volume,
                    "cost": cost,
                })
                # 更新参考价格
                last_price = price

        # 计算回测结果
        return self._calculate_result()

    def run_bonus_stocks(self) -> BacktestResult:
        """
        运行红利ETF定投策略

        策略逻辑:
        1. 只在定投日 (如每周三) 进行交易
        2. RSI 指标判断:
           - RSI > 70 (超买): 不买入
           - RSI < 30 (超卖): +100股
        3. 乖离率判断 (与250日均线比较):
           - 乖离率 > 10%: 不买入
           - 乖离率 < -10%: +100股
        4. 基础买入 500 股，根据指标加减仓

        Returns:
            回测结果
        """
        # 获取策略参数
        investment_days = self.config.get("investment_days", ["周三"])  # 定投日
        base_volume = self.config.get("base_volume", 500)  # 基础买入数量
        lot_size = self.config.get("lot_size", 100)  # 交易单位

        # RSI 参数
        rsi_period = self.config.get("rsi_period", 14)
        rsi_overbought = self.config.get("rsi_overbought", 70)
        rsi_oversold = self.config.get("rsi_oversold", 30)
        rsi_additional = self.config.get("rsi_additional", 100)  # 超卖加仓数量

        # 乖离率参数
        bias_ma_period = self.config.get("bias_ma_period", 250)
        bias_upper = self.config.get("bias_upper", 0.1)
        bias_lower = self.config.get("bias_lower", -0.1)
        bias_additional = self.config.get("bias_additional", 100)  # 负乖离加仓数量

        # 用于累积价格计算指标
        preloaded_prices = []

        # 遍历所有交易日
        for i, (time, price) in enumerate(zip(self.times, self.prices)):
            # 累积价格数据用于计算 RSI
            current_prices = preloaded_prices + [price]

            # 检查是否为定投日
            try:
                dt = datetime.strptime(time, "%Y%m%d")
                if not is_investment_day(dt, investment_days):
                    # 非定投日，只累积价格不交易
                    preloaded_prices = current_prices
                    continue
            except:
                preloaded_prices = current_prices
                continue

            # 计算技术指标
            # RSI: 需要足够的历史数据
            rsi = calculate_rsi(current_prices, rsi_period) if len(current_prices) > rsi_period else None
            # 250日均线
            ma250 = calculate_ma(current_prices, bias_ma_period) if len(current_prices) >= bias_ma_period else None
            # 乖离率
            bias = calculate_bias_rate(price, ma250) if ma250 else None

            # 决策是否买入
            should_buy = True  # 默认应该买入
            additional_volume = 0  # 额外加仓数量

            # RSI 判断
            if rsi and rsi > rsi_overbought:
                # 超买，不买入
                should_buy = False
            elif rsi and rsi < rsi_oversold:
                # 超卖，加仓
                additional_volume += rsi_additional

            # 乖离率判断
            if bias and bias > bias_upper:
                # 正乖离过大，不买入
                should_buy = False
            elif bias and bias < bias_lower:
                # 负乖离过大，加仓
                additional_volume += bias_additional

            # 执行买入
            if should_buy:
                volume = base_volume + additional_volume
                # 按整手调整 (A股必须整手交易)
                volume = (volume // lot_size) * lot_size

                if volume > 0:
                    cost = price * volume
                    self.buy_records.append({
                        "time": time,
                        "price": price,
                        "volume": volume,
                        "cost": cost,
                        "rsi": round(rsi, 2) if rsi else None,
                        "bias": round(bias, 4) if bias else None,
                    })

            # 更新价格数据
            preloaded_prices = current_prices

        # 计算回测结果
        return self._calculate_result()

    def _calculate_result(self) -> BacktestResult:
        """
        计算回测结果指标

        计算以下指标:
        - 总投入、最终价值、总收益、收益率
        - 胜率 (盈利交易/总交易)
        - 年化收益率
        - 最大回撤
        - 波动率
        - 夏普比率
        - 卡玛比率

        Returns:
            回测结果
        """
        # 无交易记录时返回空结果
        if not self.buy_records:
            return BacktestResult(
                strategy=self.strategy,
                stock_code=self.stock_code,
                start_time=self.times[0] if self.times else "",
                end_time=self.times[-1] if self.times else "",
            )

        # ==================== 基础统计 ====================
        total_investment = sum(r["cost"] for r in self.buy_records)  # 总投入
        final_price = self.prices[-1] if self.prices else 0  # 最终价格
        total_shares = sum(r["volume"] for r in self.buy_records)  # 总股数
        final_value = total_shares * final_price  # 最终持仓价值

        # 收益计算
        total_return = final_value - total_investment
        return_rate = total_return / total_investment if total_investment > 0 else 0

        # 胜率: 最终价格高于买入价的交易为盈利
        profitable_trades = sum(1 for r in self.buy_records if r["price"] < final_price)
        win_rate = profitable_trades / len(self.buy_records) if self.buy_records else 0

        # ==================== 时间计算 ====================
        if self.times:
            try:
                start_dt = datetime.strptime(self.times[0], "%Y%m%d")
                end_dt = datetime.strptime(self.times[-1], "%Y%m%d")
                days = max(1, (end_dt - start_dt).days)
            except Exception:
                days = 180  # 默认180天
        else:
            days = 180

        # ==================== 年化收益率 ====================
        # 公式: (1 + 总收益率) ^ (365/天数) - 1
        # 例如: 6个月收益率10%，年化 = (1+0.1)^(365/180)-1 ≈ 21.7%
        annualized_return = (1 + return_rate) ** (365 / days) - 1 if days > 0 else 0

        # ==================== 最大回撤 ====================
        # 计算方法: 遍历每个时间点，计算当前价格与历史最高点的跌幅
        # 最大回撤 = max(历史最高点 - 最低点) / 历史最高点
        max_drawdown = 0.0
        if self.prices:
            peak = self.prices[0]  # 初始最高点
            for price in self.prices:
                if price > peak:
                    peak = price
                # 计算当前回撤
                drawdown = (peak - price) / peak if peak > 0 else 0
                if drawdown > max_drawdown:
                    max_drawdown = drawdown

        # ==================== 波动率 ====================
        # 波动率 = 价格标准差 / 平均价格
        if len(self.prices) > 1:
            avg_price = sum(self.prices) / len(self.prices)
            variance = sum((p - avg_price) ** 2 for p in self.prices) / len(self.prices)
            volatility = variance ** 0.5 / avg_price if avg_price > 0 else 0
        else:
            volatility = 0

        # ==================== 夏普比率 ====================
        # 夏普比率 = (年化收益率 - 无风险利率) / 波动率
        # 衡量承担单位风险获得的超额收益
        # 无风险利率通常取 3% (国债收益率)
        risk_free_rate = 0.03
        sharpe_ratio = (annualized_return - risk_free_rate) / volatility if volatility > 0 else 0

        # ==================== 卡玛比率 ====================
        # 卡玛比率 = 年化收益率 / 最大回撤
        # 衡量单位最大回撤获得的年化收益
        calmar_ratio = annualized_return / max_drawdown if max_drawdown > 0 else 0

        return BacktestResult(
            strategy=self.strategy,
            stock_code=self.stock_code,
            start_time=self.times[0] if self.times else "",
            end_time=self.times[-1] if self.times else "",
            total_trades=len(self.buy_records),
            profitable_trades=profitable_trades,
            total_investment=total_investment,
            final_value=final_value,
            total_return=total_return,
            return_rate=return_rate,
            volatility=volatility,
            sharpe_ratio=sharpe_ratio,
            annualized_return=annualized_return,
            max_drawdown=max_drawdown,
            calmar_ratio=calmar_ratio,
            win_rate=win_rate,
            buy_records=self.buy_records,
            prices=self.prices,
            times=self.times,
        )

    def run(self) -> BacktestResult:
        """
        运行回测的入口方法

        根据策略名称选择对应的回测方法

        Returns:
            回测结果

        Raises:
            ValueError: 未知策略
        """
        if self.strategy == "buy_on_dips":
            return self.run_buy_on_dips()
        elif self.strategy == "bonus_stocks":
            return self.run_bonus_stocks()
        else:
            raise ValueError(f"未知策略: {self.strategy}")


# ==================== 公开 API ====================

def run_backtest(
    strategy: str,
    stock_code: str,
    duration: str = "6m",
    config: dict = None
) -> dict:
    """
    运行回测的公开接口

    Args:
        strategy: 策略名称 ("buy_on_dips" 或 "bonus_stocks")
        stock_code: 股票代码 (如 "515650.SH")
        duration: 回测时长
            - "1m": 1个月
            - "3m": 3个月
            - "6m": 6个月
            - "1y": 1年
            - "2y": 2年
            - ... 以此类推
        config: 策略参数配置，如果为 None 则从配置文件加载

    Returns:
        回测结果字典，包含所有统计指标和交易记录
        如果出错返回 {"error": "错误信息"}
    """
    # ==================== 计算日期范围 ====================
    if duration.endswith('m'):
        # 月份: 1m, 3m, 6m 等
        months = int(duration[:-1])
        end_time = datetime.now()
        start_time = end_time - timedelta(days=months * 30)
    elif duration.endswith('y'):
        # 年份: 1y, 2y, 3y 等
        years = int(duration[:-1])
        start_time = datetime.now() - timedelta(days=years * 365)
        end_time = datetime.now()
    else:
        # 默认6个月
        end_time = datetime.now()
        start_time = end_time - timedelta(days=180)

    # 转换为字符串格式
    start_str = start_time.strftime("%Y%m%d")
    end_str = end_time.strftime("%Y%m%d")

    # ==================== 加载策略配置 ====================
    # bonus_stocks 策略从配置文件加载参数
    if strategy == "bonus_stocks" and config is None:
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "config", "bonus_stocks.json"
        )
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                bonus_config = json.load(f)
            # 从配置文件构建回测配置
            params = bonus_config.get("params", {})
            inv = bonus_config.get("investment", {})
            config = {
                "investment_days": inv.get("days", ["周三"]),
                "base_volume": inv.get("base_volume", 500),
                "lot_size": inv.get("lot_size", 100),
                "rsi_period": params.get("rsi", {}).get("period", 14),
                "rsi_overbought": params.get("rsi", {}).get("overbought", 70),
                "rsi_oversold": params.get("rsi", {}).get("oversold", 30),
                "rsi_additional": params.get("rsi", {}).get("buy_additional", 100),
                "bias_ma_period": params.get("bias", {}).get("ma_period", 250),
                "bias_upper": params.get("bias", {}).get("upper_threshold", 0.1),
                "bias_lower": params.get("bias", {}).get("lower_threshold", -0.1),
                "bias_additional": params.get("bias", {}).get("buy_additional", 100),
            }

    # ==================== 执行回测 ====================
    engine = BacktestEngine(strategy, stock_code, config)

    # 加载数据
    if not engine.load_data(start_str, end_str):
        return {"error": "无法加载历史数据，请检查股票代码是否正确"}

    # 运行策略
    result = engine.run()
    return result.to_dict()


# ==================== 命令行入口 ====================

def main():
    """命令行入口函数

    使用方法:
        python -m src.backtest.backtest_engine -s bonus_stocks -d 1y

    参数:
        -s, --strategy: 策略名称 (buy_on_dips 或 bonus_stocks)
        -d, --duration: 回测时长 (1m, 3m, 6m, 1y 等)
        -o, --output: 输出文件路径 (可选)
    """
    import argparse

    parser = argparse.ArgumentParser(description="策略回测")
    parser.add_argument("--strategy", "-s", default="buy_on_dips",
                      choices=["buy_on_dips", "bonus_stocks"],
                      help="策略名称")
    parser.add_argument("--stock", default="515650.SH",
                      help="股票代码")
    parser.add_argument("--duration", "-d", default="6m",
                      choices=["1m", "3m", "6m", "1y", "2y", "3y", "5y", "10y"],
                      help="回测时长")
    parser.add_argument("--output", "-o", default=None,
                      help="输出JSON文件路径")

    args = parser.parse_args()

    print(f"运行回测: {args.strategy} {args.stock} {args.duration}")

    result = run_backtest(args.strategy, args.stock, args.duration)

    if "error" in result:
        print(f"错误: {result['error']}")
        return

    # 打印结果摘要
    print(f"\n回测结果:")
    print(f"  交易次数: {result['total_trades']}")
    print(f"  总投入: {result['total_investment']:.2f}")
    print(f"  最终价值: {result['final_value']:.2f}")
    print(f"  收益率: {result['return_rate']:.2f}%")
    print(f"  年化收益率: {result['annualized_return']:.2f}%")
    print(f"  最大回撤: {result['max_drawdown']*100:.2f}%")
    print(f"  波动率: {result['volatility']*100:.2f}%")
    print(f"  夏普比率: {result['sharpe_ratio']:.4f}")
    print(f"  卡玛比率: {result['calmar_ratio']:.4f}")
    print(f"  胜率: {result['win_rate']*100:.2f}%")

    # 保存到文件
    output_path = args.output
    if output_path is None:
        # 默认保存到 frontend/data 目录
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # src/
        base_dir = os.path.dirname(base_dir)  # 项目根目录
        output_dir = os.path.join(base_dir, "frontend", "data")
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, f"{args.strategy}_{args.stock}.json")

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\n结果已保存到: {output_path}")


if __name__ == "__main__":
    main()
