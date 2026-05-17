"""
参数优化回测脚本 - 测试 additional 参数

测试 RSI 和 bias 的 additional 参数不同值的回测效果
"""

import json
import os
from datetime import datetime, timedelta
from dataclasses import dataclass

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from src.backtest.backtest_engine import calculate_rsi, calculate_ma, calculate_bias_rate, is_investment_day
from src.backtest.history_data import get_historical_kline


# 固定参数（已从之前优化确定）
FIXED_PARAMS = {
    "rsi_period": 14,
    "rsi_overbought": 60,
    "rsi_oversold": 20,
    "bias_ma_period": 250,
    "bias_upper": 0.05,
    "bias_lower": -0.15,
}

# additional 参数搜索空间 - 更细分
RSI_ADDITIONAL_RANGE = [0, 50, 100, 150, 200, 250, 300]
BIAS_ADDITIONAL_RANGE = [0, 50, 100, 150, 200, 250, 300]


@dataclass
class ParamResult:
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
    times, prices,
    rsi_additional, bias_additional,
    base_volume=500, lot_size=100,
    investment_days=["周三"],
):
    buy_records = []
    preloaded_prices = []

    for time, price in zip(times, prices):
        current_prices = preloaded_prices + [price]

        try:
            dt = datetime.strptime(time, "%Y%m%d")
            if not is_investment_day(dt, investment_days):
                preloaded_prices = current_prices
                continue
        except:
            preloaded_prices = current_prices
            continue

        rsi = calculate_rsi(current_prices, 14) if len(current_prices) > 14 else None
        ma250 = calculate_ma(current_prices, 250) if len(current_prices) >= 250 else None
        bias = calculate_bias_rate(price, ma250) if ma250 else None

        should_buy = True
        additional_volume = 0

        if rsi and rsi > 60:
            should_buy = False
        elif rsi and rsi < 20:
            additional_volume += rsi_additional

        if bias and bias > 0.05:
            should_buy = False
        elif bias and bias < -0.15:
            additional_volume += bias_additional

        if should_buy:
            volume = base_volume + additional_volume
            volume = (volume // lot_size) * lot_size
            if volume > 0:
                buy_records.append({
                    "time": time,
                    "price": price,
                    "volume": volume,
                    "cost": price * volume,
                })

        preloaded_prices = current_prices

    if not buy_records:
        return {
            "total_trades": 0,
            "total_investment": 0,
            "final_value": 0,
            "return_rate": 0,
            "sharpe_ratio": 0,
        }

    total_investment = sum(r["cost"] for r in buy_records)
    final_price = prices[-1] if prices else 0
    total_shares = sum(r["volume"] for r in buy_records)
    final_value = total_shares * final_price
    return_rate = (final_value - total_investment) / total_investment if total_investment > 0 else 0

    if len(prices) > 1:
        avg_price = sum(prices) / len(prices)
        variance = sum((p - avg_price) ** 2 for p in prices) / len(prices)
        volatility = variance ** 0.5 / avg_price if avg_price > 0 else 0
    else:
        volatility = 0

    sharpe_ratio = (return_rate - 0.03) / volatility if volatility > 0 else 0

    return {
        "total_trades": len(buy_records),
        "total_investment": total_investment,
        "final_value": final_value,
        "return_rate": return_rate,
        "sharpe_ratio": sharpe_ratio,
    }


def run_optimization(etf_code, duration="3y"):
    if duration.endswith('y'):
        years = int(duration[:-1])
        end_time = datetime.now()
        start_time = end_time - timedelta(days=years * 365)
    else:
        end_time = datetime.now()
        start_time = end_time - timedelta(days=365)

    start_str = start_time.strftime("%Y%m%d")
    end_str = end_time.strftime("%Y%m%d")

    print(f"加载 {etf_code} 历史数据...")
    data = get_historical_kline(etf_code, start_str, end_str, fields=["close"])

    if not data or not data.get("close"):
        print(f"无法加载 {etf_code} 的历史数据")
        return []

    prices = data.get("close", [])
    times = data.get("time", [])
    print(f"加载 {len(prices)} 条数据 ({times[0]} - {times[-1]})")

    results = []
    for rsi_add in RSI_ADDITIONAL_RANGE:
        for bias_add in BIAS_ADDITIONAL_RANGE:
            result = run_backtest_with_params(
                times, prices,
                rsi_additional=rsi_add,
                bias_additional=bias_add,
            )
            results.append(ParamResult(
                params={
                    "rsi_additional": rsi_add,
                    "bias_additional": bias_add,
                },
                total_trades=result["total_trades"],
                total_investment=result["total_investment"],
                final_value=result["final_value"],
                return_rate=result["return_rate"],
                sharpe_ratio=result["sharpe_ratio"],
                etf_code=etf_code,
            ))

    return results


def optimize_all_etfs(duration="3y"):
    config_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "config", "bonus_stocks.json"
    )
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)

    etfs = config.get("etfs", [])
    print(f"开始优化，共 {len(etfs)} 个ETF...")

    all_results = {}

    for etf in etfs:
        etf_code = etf["code"]
        etf_name = etf["name"]
        print(f"\n{'='*60}")
        print(f"优化 ETF: {etf_name} ({etf_code})")
        print(f"{'='*60}")

        results = run_optimization(etf_code, duration)

        if results:
            results.sort(key=lambda x: x.return_rate, reverse=True)
            all_results[etf_code] = [r.to_dict() for r in results[:15]]

            best = results[0]
            print(f"\n最优参数 (收益率: {best.return_rate*100:.2f}%):")
            print(f"  RSI additional: {best.params['rsi_additional']}")
            print(f"  Bias additional: {best.params['bias_additional']}")
            print(f"  交易次数: {best.total_trades}")
            print(f"  总投入: {best.total_investment:.2f}")
            print(f"  最终价值: {best.final_value:.2f}")

    output_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "frontend", "data"
    )
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "additional_optimization.json")

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)

    print(f"\n结果已保存到: {output_path}")
    return all_results


def main():
    import argparse
    parser = argparse.ArgumentParser(description="additional参数优化")
    parser.add_argument("--duration", "-d", default="3y", help="回测时长")
    args = parser.parse_args()

    optimize_all_etfs(args.duration)


if __name__ == "__main__":
    main()