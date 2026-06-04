#!/usr/bin/env python3
"""Backtest CLI with grid search optimization"""
import argparse
import importlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.schema import init_db
from db.queries import get_strategy, get_backtest_runs, get_backtest_run
from engine.strategy_registry import create as create_strategy, list_all, get as get_cls
from backtest.engine import BacktestEngine
from backtest.optimizer import GridOptimizer


def _scan():
    d = os.path.join(os.path.dirname(__file__), "..", "strategies")
    for f in sorted(os.listdir(d)):
        if f.endswith(".py") and not f.startswith("_"):
            try:
                importlib.import_module(f"strategies.{f[:-3]}")
            except Exception:
                pass


def _stock_code(name):
    s = get_strategy(name)
    if s:
        config = json.loads(s["config"]) if isinstance(s["config"], str) else s["config"]
        w = config.get("watched_stocks", [])
        if w:
            return w[0]
    cls = get_cls(name)
    if cls and cls.watched_stocks:
        return cls.watched_stocks[0]
    return ""


def _print_report(r, strategy, start, end, capital):
    print("=" * 50)
    print(f"  Backtest: {strategy}")
    print("=" * 50)
    print(f"  Period: {start} -> {end}")
    print(f"  Initial: {capital:,.0f}")
    print(f"  Final: {r['final_value']:,.2f} ({r['return_rate']*100:+.2f}%)")
    print(f"  Annual: {r['annualized_return']*100:+.2f}%")
    print(f"  Max DD: {r['max_drawdown']*100:+.2f}%")
    print(f"  Sharpe: {r['sharpe_ratio']:.2f}")
    print(f"  Trades: {r['total_trades']}")
    if r.get("trades"):
        tc = sum(t.get("total_fee", 0) for t in r["trades"])
        tcom = sum(t.get("commission", 0) for t in r["trades"])
        tstamp = sum(t.get("stamp_tax", 0) for t in r["trades"])
        print(f"  Fees: {tc:,.0f} (comm {tcom:.0f}, stamp {tstamp:.0f})")
    print("=" * 50)
    if r.get("run_id"):
        print(f"  Run ID: {r['run_id']}")
    curve = r.get("equity_curve", [])
    if len(curve) > 10:
        print("  Equity (first 5):")
        for p in curve[:5]:
            print(f"    {p['date']}: {p['value']:,.2f}")
        print(f"    ... ({len(curve)-10} points)")
        print("  Equity (last 5):")
        for p in curve[-5:]:
            print(f"    {p['date']}: {p['value']:,.2f}")


def cmd_list():
    runs = get_backtest_runs(limit=30)
    if not runs:
        print("No runs.")
        return
    print(f"{'Run ID':<30} {'Strategy':<20} {'Start':<10} {'End':<10} {'Return':>8} {'Sharpe':>8}")
    print("-" * 90)
    for r in runs:
        ret = r.get('total_return', 0)
        if isinstance(ret, (int, float)):
            ret_str = f"{ret*100:>+7.2f}%"
        else:
            ret_str = f"{'N/A':>8}"
        print(f"{r['run_id']:<30} {r['strategy']:<20} {r['start_date'][:10]:<10} {r['end_date'][:10]:<10} {ret_str} {r.get('sharpe_ratio',0):>8.2f}")


def cmd_show(rid):
    r = get_backtest_run(rid)
    if not r:
        print(f"Run '{rid}' not found")
        return
    print(f"Run: {r['run_id']}\nStrategy: {r['strategy']}\nPeriod: {r['start_date']} -> {r['end_date']}")
    print(f"Return: {r.get('total_return',0)*100:+.2f}%  Sharpe: {r.get('sharpe_ratio',0):.2f}")
    print(f"Max DD: {r.get('max_drawdown',0)*100:.2f}%  Trades: {r.get('total_trades',0)}")
    curve = json.loads(r.get("equity_curve", "[]")) if isinstance(r.get("equity_curve"), str) else r.get("equity_curve", [])
    if curve:
        print("\nEquity curve:")
        for p in curve:
            print(f"  {p['date']}: ¥{p['value']:,.2f}")


def main():
    p = argparse.ArgumentParser(description="Backtest")
    p.add_argument("--strategy", type=str)
    p.add_argument("--stock", type=str)
    p.add_argument("--start", type=str, default="20220101")
    p.add_argument("--end", type=str, default="20231231")
    p.add_argument("--initial-cash", type=float, default=100000)
    p.add_argument("--optimize", action="store_true")
    p.add_argument("--target", type=str, default="sharpe_ratio", choices=["sharpe_ratio", "annualized_return", "max_drawdown"])
    p.add_argument("--list", action="store_true")
    p.add_argument("--show", type=str)
    args = p.parse_args()

    if args.list:
        cmd_list()
    elif args.show:
        cmd_show(args.show)
    elif args.strategy:
        _scan()
        init_db()
        stock = args.stock or _stock_code(args.strategy)
        if not stock:
            print("Error: no stock code")
            return

        if args.optimize:
            cls = get_cls(args.strategy)
            if cls:
                instance = cls()
                tuning = instance.get_tuning_space()
                param_grid = {}
                for t in tuning:
                    if t["type"] == "int":
                        vals = list(range(t["min"], t["max"] + 1, t.get("step", 1)))
                    elif t["type"] == "float":
                        vals = []
                        v = t["min"]
                        step = t.get("step", 0.01)
                        while v <= t["max"]:
                            vals.append(round(v, 6))
                            v += step
                    else:
                        vals = t.get("choices", [t["min"], t["max"]])
                    param_grid[t["name"]] = vals
                opt = GridOptimizer(args.strategy, stock, args.start, args.end, args.initial_cash)
                results = opt.top_n(param_grid, n=10, metric=args.target)
                print(f"Top 10 by {args.target}:")
                for i, r in enumerate(results):
                    print(f"  #{i+1}: {args.target}={r.get(args.target,'N/A'):.4f}  params={r['params']}")
        else:
            engine = BacktestEngine()
            result = engine.run(args.strategy, stock, args.start, args.end, initial_capital=args.initial_cash)
            if "error" in result:
                print(f"Error: {result['error']}")
            else:
                _print_report(result, args.strategy, args.start, args.end, args.initial_cash)
    else:
        p.print_help()


if __name__ == "__main__":
    main()
