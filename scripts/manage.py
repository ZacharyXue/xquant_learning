#!/usr/bin/env python3
"""Strategy management CLI — single point of strategy configuration"""
import argparse
import importlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.schema import init_db
from db.queries import register_strategy, list_strategies, get_strategy, enable_strategy, update_strategy_config
from engine.strategy_registry import list_all, get as get_cls


def _scan():
    d = os.path.join(os.path.dirname(__file__), "..", "strategies")
    for f in sorted(os.listdir(d)):
        if f.endswith(".py") and not f.startswith("_"):
            try:
                importlib.import_module(f"strategies.{f[:-3]}")
            except Exception as e:
                print(f"  [WARN] Failed: {f} - {e}")


def cmd_init():
    init_db()
    _scan()
    for name in list_all():
        cls = get_cls(name)
        config = {}
        if cls and hasattr(cls, 'get_config_schema'):
            for prop, info in cls().get_config_schema().get("properties", {}).items():
                if "default" in info:
                    config[prop] = info["default"]
        register_strategy(name, cls.display_name if cls else name, config)
        print(f"  Registered: {name}")
    print("Done.")


def cmd_list():
    ss = list_strategies()
    if not ss:
        print("No strategies. Run --init first.")
        return
    print(f"{'Name':<20} {'Display':<25} {'Enabled':<8}")
    print("-" * 55)
    for s in ss:
        print(f"{s['name']:<20} {s.get('display_name',''):<25} {'ON' if s['enabled'] else 'OFF':<8}")


def cmd_show(name):
    s = get_strategy(name)
    if not s:
        print(f"Strategy '{name}' not found")
        return
    config = json.loads(s["config"]) if isinstance(s["config"], str) else s["config"]
    print(f"Name:    {s['name']}")
    print(f"Display: {s.get('display_name','')}")
    print(f"Enabled: {'Yes' if s['enabled'] else 'No'}")
    print("Config:")
    for k, v in config.items():
        print(f"  {k}: {v}")


def cmd_set(name, params):
    s = get_strategy(name)
    if not s:
        print(f"Strategy '{name}' not found")
        return
    config = json.loads(s["config"]) if isinstance(s["config"], str) else s["config"]
    for p in params:
        if "=" not in p:
            print(f"Ignored: {p}")
            continue
        k, v_str = p.split("=", 1)
        try:
            v = int(v_str)
        except ValueError:
            try:
                v = float(v_str)
            except ValueError:
                v = v_str.strip('"').strip("'")
        config[k] = v
        print(f"  {k} = {v}")
    update_strategy_config(name, config)
    print(f"Updated {name}")


def main():
    p = argparse.ArgumentParser(description="Strategy management")
    p.add_argument("--init", action="store_true")
    p.add_argument("--list", action="store_true")
    p.add_argument("--enable", type=str)
    p.add_argument("--disable", type=str)
    p.add_argument("--show", type=str)
    p.add_argument("--set", type=str)
    p.add_argument("--param", type=str, action="append")
    args = p.parse_args()
    if args.list:
        cmd_list()
    elif args.init:
        cmd_init()
    elif args.enable:
        enable_strategy(args.enable, True)
        print(f"Enabled: {args.enable}")
    elif args.disable:
        enable_strategy(args.disable, False)
        print(f"Disabled: {args.disable}")
    elif args.show:
        cmd_show(args.show)
    elif args.set:
        cmd_set(args.set, args.param or [])
    else:
        p.print_help()


if __name__ == "__main__":
    main()
