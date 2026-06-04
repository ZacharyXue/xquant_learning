#!/usr/bin/env python3
"""Real trading CLI — requires QMT client running on Windows"""
import argparse
import asyncio
import importlib
import json
import os
import sys

import yaml

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.schema import init_db
from db.queries import list_strategies, get_strategy
from engine.strategy_registry import create as create_strategy
from trade.real_executor import RealExecutor
from trade.quote_pump import QuotePump
from trade.broker import Broker


def _scan():
    d = os.path.join(os.path.dirname(__file__), "..", "strategies")
    for f in sorted(os.listdir(d)):
        if f.endswith(".py") and not f.startswith("_"):
            try:
                importlib.import_module(f"strategies.{f[:-3]}")
            except Exception:
                pass


def _config():
    with open(os.path.join(os.path.dirname(__file__), "..", "config.yaml")) as f:
        return yaml.safe_load(f)


async def run(names):
    _scan()
    init_db()
    cfg = _config()
    qmt = os.environ.get("XTQUANT_QMT_PATH", cfg["trade"]["qmt_path"])
    aid = os.environ.get("XTQUANT_ACCOUNT_ID", cfg["trade"]["account_id"])
    if not qmt or not aid:
        print("Error: qmt_path and account_id required")
        return
    executor = RealExecutor(qmt, aid)
    broker = Broker(executor, mode="real")
    pump = QuotePump()
    strats = []
    watched = set()
    for name in names:
        s = get_strategy(name)
        config = json.loads(s["config"]) if isinstance(s["config"], str) else (s["config"] if s else {})
        inst = create_strategy(name, config)
        strats.append((name, inst))
        watched.update(inst.watched_stocks)
    ok = await executor.initialize()
    if not ok:
        print("Failed to connect to QMT")
        return
    print(f"Connected. Watching {watched}")

    def on_q(quote):
        for sname, strat in strats:
            if quote.stock_code not in strat.watched_stocks:
                continue
            sig = strat.on_quote(quote)
            if sig and sig.side in ("buy", "sell"):
                print(f"[{datetime.now()}] {sname}: {sig.side} {sig.stock_code} x{sig.volume} — {sig.reason}")
                asyncio.ensure_future(broker.handle_signal(sig, sname))

    from datetime import datetime

    pump.on_quote(on_q)
    await pump.subscribe(list(watched))
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down...")
        await pump.stop()
        await executor.close()


def main():
    p = argparse.ArgumentParser(description="Real trading")
    p.add_argument("--strategy", type=str)
    args = p.parse_args()
    _scan()
    if args.strategy:
        names = [args.strategy]
    else:
        names = [s["name"] for s in list_strategies() if s.get("enabled")]
    if not names:
        print("No strategies. Run manage.py --init")
        return
    asyncio.run(run(names))


if __name__ == "__main__":
    main()
