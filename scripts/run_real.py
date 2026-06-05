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

# xtquant SDK path setup
_xtquant_path = r"D:\国金证券QMT交易端\bin.x64\Lib\site-packages"
if os.path.isdir(_xtquant_path):
    sys.path.insert(0, _xtquant_path)
    os.environ.setdefault("PATH", r"D:\国金证券QMT交易端\bin.x64;" + os.environ.get("PATH", ""))

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
    with open(os.path.join(os.path.dirname(__file__), "..", "config.yaml"), encoding="utf-8") as f:
        return yaml.safe_load(f)


async def run(names):
    _scan()
    init_db()
    cfg = _config()
    qmt = os.environ.get("XTQUANT_QMT_PATH", cfg["trade"]["qmt_path"])
    aid = os.environ.get("XTQUANT_ACCOUNT_ID", cfg["trade"]["account_id"])
    if not qmt or not aid:
        print("Error: qmt_path and account_id required in config.yaml or env vars")
        _wait_exit()
        return

    print(f"QMT path: {qmt}")
    print(f"Account:  {aid}")

    # Verify xtquant import
    try:
        import xtquant.xtdata as xtdata
        print("xtquant: OK")
    except Exception as e:
        print(f"xtquant FAILED: {e}")
        print("  Ensure xtquant is installed in the venv.")
        _wait_exit()
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
        print(f"Strategy: {name} watching {inst.watched_stocks}")

    print(f"\nConnecting to QMT...")
    ok = await executor.initialize()
    if not ok:
        print("FAILED to connect to QMT.")
        print("  Ensure QMT client is running and logged in.")
        print(f"  Check: qmt_path={qmt}")
        _wait_exit()
        return

    print(f"Connected to QMT. Subscribing to {watched}...")

    quote_count = [0]

    def on_q(quote):
        quote_count[0] += 1
        if quote_count[0] <= 3:
            print(f"  [{datetime.now()}] tick: {quote.stock_code} last={quote.last_price}")
        for sname, strat in strats:
            if quote.stock_code not in strat.watched_stocks:
                continue
            sig = strat.on_quote(quote)
            if sig and sig.side in ("buy", "sell"):
                print(f"[{datetime.now()}] {sname}: {sig.side} {sig.stock_code} x{sig.volume} @ {sig.price:.4f} — {sig.reason}")
                asyncio.ensure_future(broker.handle_signal(sig, sname))
            elif sig and sig.side == "skip":
                print(f"[{datetime.now()}] {sname}: SKIP — {sig.reason}")

    from datetime import datetime

    pump.on_quote(on_q)
    await pump.subscribe(list(watched))

    print(f"Waiting for quotes... (Ctrl+C to stop)")
    print(f"  Check result: python scripts/show_trades.py --today\n")

    last_print = 0
    try:
        while True:
            await asyncio.sleep(5)
            elapsed = last_print + 5
            if quote_count[0] > last_print:
                elapsed = 0
            last_print = quote_count[0]
            if quote_count[0] == 0 and elapsed > 30:
                print("  No quotes received in 30s. Is the market open?")
                elapsed = -30  # reset timer
    except KeyboardInterrupt:
        print("\nShutting down...")
        await pump.stop()
        await executor.close()


def _wait_exit():
    try:
        input("\nPress Enter to close...")
    except (EOFError, KeyboardInterrupt):
        pass


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
