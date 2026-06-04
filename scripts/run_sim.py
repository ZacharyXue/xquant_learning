#!/usr/bin/env python3
"""Simulated trading CLI"""
import argparse
import asyncio
import importlib
import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.schema import init_db
from db.queries import list_strategies, get_strategy
from engine.strategy_registry import create as create_strategy
from engine.strategy_base import Quote
from trade.sim_executor import SimExecutor
from trade.broker import Broker


def _scan():
    d = os.path.join(os.path.dirname(__file__), "..", "strategies")
    for f in sorted(os.listdir(d)):
        if f.endswith(".py") and not f.startswith("_"):
            try:
                importlib.import_module(f"strategies.{f[:-3]}")
            except Exception:
                pass


async def run(names, cash):
    _scan()
    init_db()
    executor = SimExecutor(initial_capital=cash)
    broker = Broker(executor, mode="sim")
    strats = []
    watched = set()
    for name in names:
        s = get_strategy(name)
        config = json.loads(s["config"]) if isinstance(s["config"], str) else (s["config"] if s else {})
        inst = create_strategy(name, config)
        strats.append((name, inst))
        watched.update(inst.watched_stocks)
    if not strats:
        print("No strategies.")
        return
    print(f"Sim trading: {len(strats)} strategies, watching {watched}")
    print(f"Cash: {cash:,.0f}")
    for day in range(1, 101):
        now = datetime.now()
        for code in watched:
            quote = Quote(stock_code=code, last_price=1.0, time=now)
            for sname, strat in strats:
                if code not in strat.watched_stocks:
                    continue
                sig = strat.on_quote(quote)
                if sig and sig.side in ("buy", "sell"):
                    print(f"  [{day}] {sname}: {sig.side} {code} x{sig.volume} — {sig.reason}")
                    r = await broker.handle_signal(sig, sname)
                    if not r.get("executed"):
                        print(f"    Failed: {r.get('reason')}")
        acc = executor.get_account()
        print(f"  [{day}] Cash: ¥{acc['available_cash']:,.2f}")
        await asyncio.sleep(1)


def main():
    p = argparse.ArgumentParser(description="Sim trading")
    p.add_argument("--strategy", type=str)
    p.add_argument("--initial-cash", type=float, default=100000)
    args = p.parse_args()
    _scan()
    if args.strategy:
        names = [args.strategy]
    else:
        names = [s["name"] for s in list_strategies() if s.get("enabled")]
    if not names:
        print("No strategies. Run manage.py --init")
        return
    asyncio.run(run(names, args.initial_cash))


if __name__ == "__main__":
    main()
