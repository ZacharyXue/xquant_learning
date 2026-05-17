"""
参数优化回测脚本

对RSI和乖离率的不同参数组合进行近三年回测，找出最优参数
"""

import json
import os
import itertools
from datetime import datetime, timedelta
from typing import Optional
from dataclasses import dataclass

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from src.backtest.backtest_engine import BacktestEngine, calculate_rsi, calculate_ma, calculate_bias_rate, is_investment_day
from src.backtest.history_data import get_historical_kline


# 参数搜索空间
RSI_PERIODS = [14]
RSI_OVERBOUGHT_RANGE = [60, 65, 70, 75, 80]
RSI_OVERSOLD_RANGE = [20, 25, 30, 35, 40]
RSI_ADDITIONAL_RANGE = [0, 100, 200, 300]

BIAS_MA_PERIODS = [250]
BIAS_UPPER_RANGE = [0.05, 0.08, 0.10, 0.12, 0.15]
BIAS_LOWER_RANGE = [-0.15, -0.12, -0.10, -0.08, -0.05]
BIAS_ADDITIONAL_RANGE = [0, 100, 200, 300]


@dataclass
class ParamResult:
    """参数回测结果"""
    params: dict
    total_trades: int
    total_investment: float
    final_value: float
    return_rate: float
    sharpe_ratio: float
    etf_code: str

    def to_dict(self) -> dict:
        return {
            "params": self.params,
            "total_trades": self.total_trades,
            "total_investment": round(self.total_investment, 2),
            "final_value": round(self.final_value, 2),
            "return_rate": round(self.return_rate * 100, 2),
            "sharpe_ratio": round(self.sharpe_ratio, 4),
            "etf_code": self.etf_code,
        }


def run_backtest_with_params(
    stock_code: str,
    times: list,
    prices: list,
    base_volume: int,
    lot_size: int,
    rsi_period: int,
    rsi_overbought: float,
    rsi_oversold: float,
    rsi_additional: int,
    bias_ma_period: int,
    bias_upper: float,
    bias_lower: float,
    bias_additional: int,
    investment_days: list,
) -> dict:
    """使用指定参数运行回测"""
    buy_records = []
    preloaded_prices = []

    for i, (time, price) in enumerate(zip(times, prices)):
        current_prices = preloaded_prices + [price]

        try:
            dt = datetime.strptime(time, "%Y%m%d")
            if not is_investment_day(dt, investment_days):
                preloaded_prices = current_prices
                continue
        except:
            preloaded_prices = current_prices
            continue

        rsi = calculate_rsi(current_prices, rsi_period) if len(current_prices) > rsi_period else None
        ma250 = calculate_ma(current_prices, bias_ma_period) if len(current_prices) >= bias_ma_period else None
        bias = calculate_bias_rate(price, ma250) if ma250 else None

        should_buy = True
        additional_volume = 0

        if rsi and rsi > rsi_overbought:
            should_buy = False
        elif rsi and rsi < rsi_oversold:
            additional_volume += rsi_additional

        if bias and bias > bias_upper:
            should_buy = False
        elif bias and bias < bias_lower:
            additional_volume += bias_additional

        if should_buy:
            volume = base_volume + additional_volume
            volume = (volume // lot_size) * lot_size
            if volume > 0:
                cost = price * volume
                buy_records.append({
                    "time": time,
                    "price": price,
                    "volume": volume,
                    "cost": cost,
                })

        preloaded_prices = current_prices

    # 计算结果
    if not buy_records:
        return {
            "total_trades": 0,
            "total_investment": 0,
            "final_value": 0,
            "return_rate": 0,
            "sharpe_ratio": 0,
            "buy_records": [],
        }

    total_investment = sum(r["cost"] for r in buy_records)
    final_price = prices[-1] if prices else 0
    total_shares = sum(r["volume"] for r in buy_records)
    final_value = total_shares * final_price

    total_return = final_value - total_investment
    return_rate = total_return / total_investment if total_investment > 0 else 0

    # 计算波动率和夏普比率
    if len(prices) > 1:
        avg_price = sum(prices) / len(prices)
        variance = sum((p - avg_price) ** 2 for p in prices) / len(prices)
        volatility = variance ** 0.5 / avg_price if avg_price > 0 else 0
    else:
        volatility = 0

    risk_free_rate = 0.03
    sharpe_ratio = (return_rate - risk_free_rate) / volatility if volatility > 0 else 0

    return {
        "total_trades": len(buy_records),
        "total_investment": total_investment,
        "final_value": final_value,
        "return_rate": return_rate,
        "sharpe_ratio": sharpe_ratio,
        "buy_records": buy_records,
    }


def generate_param_combinations():
    """生成所有参数组合"""
    combos = []
    for rsi_overbought in RSI_OVERBOUGHT_RANGE:
        for rsi_oversold in RSI_OVERSOLD_RANGE:
            if rsi_oversold >= rsi_overbought:
                continue
            for rsi_additional in RSI_ADDITIONAL_RANGE:
                for bias_upper in BIAS_UPPER_RANGE:
                    for bias_lower in BIAS_LOWER_RANGE:
                        if bias_lower >= bias_upper:
                            continue
                        for bias_additional in BIAS_ADDITIONAL_RANGE:
                            combos.append({
                                "rsi_period": 14,
                                "rsi_overbought": rsi_overbought,
                                "rsi_oversold": rsi_oversold,
                                "rsi_additional": rsi_additional,
                                "bias_ma_period": 250,
                                "bias_upper": bias_upper,
                                "bias_lower": bias_lower,
                                "bias_additional": bias_additional,
                            })
    return combos


def run_parameter_optimization(etf_code: str, duration: str = "3y"):
    """运行参数优化"""
    # 计算时间范围
    if duration.endswith('y'):
        years = int(duration[:-1])
        end_time = datetime.now()
        start_time = end_time - timedelta(days=years * 365)
    else:
        end_time = datetime.now()
        start_time = end_time - timedelta(days=365)

    start_str = start_time.strftime("%Y%m%d")
    end_str = end_time.strftime("%Y%m%d")

    # 加载历史数据
    print(f"加载 {etf_code} 历史数据...")
    data = get_historical_kline(
        etf_code,
        start_str,
        end_str,
        fields=["close"]
    )

    if not data or not data.get("close"):
        print(f"无法加载 {etf_code} 的历史数据")
        return []

    prices = data.get("close", [])
    times = data.get("time", [])

    if not prices:
        print(f"无价格数据")
        return []

    print(f"加载 {len(prices)} 条数据 ({times[0]} - {times[-1]})")

    # 基础参数
    base_volume = 500
    lot_size = 100
    investment_days = ["周三"]

    # 生成参数组合
    param_combos = generate_param_combinations()
    print(f"共 {len(param_combos)} 种参数组合")

    # 回测每种组合
    results = []
    for i, params in enumerate(param_combos):
        result = run_backtest_with_params(
            stock_code=etf_code,
            times=times,
            prices=prices,
            base_volume=base_volume,
            lot_size=lot_size,
            rsi_period=params["rsi_period"],
            rsi_overbought=params["rsi_overbought"],
            rsi_oversold=params["rsi_oversold"],
            rsi_additional=params["rsi_additional"],
            bias_ma_period=params["bias_ma_period"],
            bias_upper=params["bias_upper"],
            bias_lower=params["bias_lower"],
            bias_additional=params["bias_additional"],
            investment_days=investment_days,
        )

        results.append(ParamResult(
            params=params,
            total_trades=result["total_trades"],
            total_investment=result["total_investment"],
            final_value=result["final_value"],
            return_rate=result["return_rate"],
            sharpe_ratio=result["sharpe_ratio"],
            etf_code=etf_code,
        ))

        if (i + 1) % 50 == 0:
            print(f"已处理 {i + 1}/{len(param_combos)}")

    return results


def optimize_all_etfs(duration: str = "3y"):
    """优化所有ETF"""
    # 加载ETF列表
    config_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "config", "bonus_stocks.json"
    )
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)

    etfs = config.get("etfs", [])
    print(f"开始参数优化，共 {len(etfs)} 个ETF...")

    all_results = {}

    for etf in etfs:
        etf_code = etf["code"]
        etf_name = etf["name"]
        print(f"\n{'='*60}")
        print(f"优化 ETF: {etf_name} ({etf_code})")
        print(f"{'='*60}")

        results = run_parameter_optimization(etf_code, duration)

        if results:
            # 按收益率排序
            results.sort(key=lambda x: x.return_rate, reverse=True)
            all_results[etf_code] = [r.to_dict() for r in results[:10]]  # 保存前10

            # 打印最优参数
            best = results[0]
            print(f"\n最优参数 (收益率: {best.return_rate*100:.2f}%):")
            print(f"  RSI: overbought={best.params['rsi_overbought']}, oversold={best.params['rsi_oversold']}, additional={best.params['rsi_additional']}")
            print(f"  乖离率: upper={best.params['bias_upper']}, lower={best.params['bias_lower']}, additional={best.params['bias_additional']}")
            print(f"  交易次数: {best.total_trades}")
            print(f"  总投入: {best.total_investment:.2f}")
            print(f"  最终价值: {best.final_value:.2f}")

    # 保存所有结果
    output_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "frontend", "data"
    )
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "param_optimization.json")

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)

    print(f"\n结果已保存到: {output_path}")

    return all_results


def main():
    import argparse
    parser = argparse.ArgumentParser(description="参数优化回测")
    parser.add_argument("--etf", "-e", help="ETF代码")
    parser.add_argument("--duration", "-d", default="3y", help="回测时长")
    args = parser.parse_args()

    if args.etf:
        results = run_parameter_optimization(args.etf, args.duration)
        results.sort(key=lambda x: x.return_rate, reverse=True)

        print(f"\n最优结果:")
        best = results[0]
        print(f"  RSI: overbought={best.params['rsi_overbought']}, oversold={best.params['rsi_oversold']}, additional={best.params['rsi_additional']}")
        print(f"  乖离率: upper={best.params['bias_upper']}, lower={best.params['bias_lower']}, additional={best.params['bias_additional']}")
        print(f"  收益率: {best.return_rate*100:.2f}%")
        print(f"  交易次数: {best.total_trades}")
    else:
        optimize_all_etfs(args.duration)


if __name__ == "__main__":
    main()