#!/usr/bin/env python3
"""Trade record query CLI"""
import argparse
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.queries import get_trades


def main():
    p = argparse.ArgumentParser(description="Trade query")
    p.add_argument("--strategy", type=str)
    p.add_argument("--mode", type=str, choices=["sim", "real", "backtest"])
    p.add_argument("--start", type=str)
    p.add_argument("--end", type=str)
    p.add_argument("--stock", type=str, help="Stock code")
    p.add_argument("--today", action="store_true")
    p.add_argument("--limit", type=int, default=100)
    args = p.parse_args()
    start = args.start
    if args.today:
        start = datetime.now().strftime("%Y-%m-%d")
    trades = get_trades(
        strategy=args.strategy,
        mode=args.mode,
        start=start,
        end=args.end,
        stock_code=args.stock,
        limit=args.limit,
    )
    if not trades:
        print("No trades.")
        return
    print(f"{'Time':<20} {'Strategy':<18} {'Mode':<10} {'Stock':<12} {'Side':<6} {'Vol':>6} {'Price':>8} {'Cost':>8} {'Reason'}")
    print("-" * 110)
    for t in trades:
        tt = t.get("trade_time", "")[:19]
        print(f"{tt:<20} {t['strategy']:<18} {t['mode']:<10} {t['stock_code']:<12} {t['side']:<6} {t['volume']:>6} {t['price']:>8.2f} {t.get('total_cost',0):>8.2f} {t.get('reason','')[:30]}")
    tc = sum(t.get("total_cost", 0) for t in trades)
    print("-" * 110)
    print(f"Total: {len(trades)} trades, fees: {tc:,.2f}")


if __name__ == "__main__":
    main()
