"""
回测报告生成器

生成 HTML/Markdown 格式的回测报告。
"""

from datetime import datetime
from typing import Optional

from backend.core.logging import get_logger

logger = get_logger("reporter")


def generate_report(result: dict, strategy_name: str, stock_code: str) -> str:
    """生成 Markdown 格式回测报告

    Args:
        result: 回测结果字典
        strategy_name: 策略名称
        stock_code: 股票代码

    Returns:
        Markdown 字符串
    """
    lines = [
        f"# 回测报告",
        f"",
        f"**策略**: {strategy_name}  ",
        f"**股票**: {stock_code}  ",
        f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  ",
        f"",
        f"## 绩效指标",
        f"",
        f"| 指标 | 数值 |",
        f"|------|------|",
        f"| 交易次数 | {result.get('total_trades', 0)} |",
        f"| 胜率 | {result.get('win_rate', 0) * 100:.2f}% |",
        f"| 总投入 | {result.get('total_investment', 0):,.2f} |",
        f"| 最终净值 | {result.get('final_value', 0):,.2f} |",
        f"| 收益率 | {result.get('return_rate', 0) * 100:.2f}% |",
        f"| 年化收益 | {result.get('annualized_return', 0) * 100:.2f}% |",
        f"| 最大回撤 | {result.get('max_drawdown', 0) * 100:.2f}% |",
        f"| 波动率 | {result.get('volatility', 0) * 100:.2f}% |",
        f"| 夏普比率 | {result.get('sharpe_ratio', 0):.2f} |",
        f"| 卡玛比率 | {result.get('calmar_ratio', 0):.2f} |",
        f"",
    ]

    return "\n".join(lines)


def generate_optimization_report(
    results: list[dict],
    strategy_name: str,
    stock_code: str,
    metric: str = "sharpe_ratio",
) -> str:
    """生成参数优化报告"""
    lines = [
        f"# 参数优化报告",
        f"",
        f"**策略**: {strategy_name} | **股票**: {stock_code}  ",
        f"**优化目标**: {metric} | **最优组合数**: {len(results)}  ",
        f"",
        f"## Top 10 最优参数",
        f"",
    ]

    # 构建表头
    if results:
        param_keys = list(results[0]["params"].keys())
        header = "| 排名 | " + " | ".join(param_keys) + f" | {metric} | 收益率 |"
        sep = "|------|" + "|".join(["------"] * len(param_keys)) + "|------|------|"
        lines.append(header)
        lines.append(sep)

        for i, r in enumerate(results[:10]):
            params_str = " | ".join(str(r["params"].get(k, "")) for k in param_keys)
            metric_val = r.get(metric, 0)
            return_val = r.get("return_rate", 0)
            lines.append(f"| {i + 1} | {params_str} | {metric_val:.4f} | {return_val * 100:.2f}% |")

    return "\n".join(lines)
