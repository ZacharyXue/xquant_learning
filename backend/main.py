"""XTQuant Trading System - 统一入口

Usage:
    python -m backend.main              # 启动 Dashboard API 服务
    python -m backend.main --trade      # 仅启动 Trade Engine (Windows)
    python -m backend.main --full       # Dashboard + Trade Engine (Windows only)
"""

import argparse
import asyncio
import sys
import uvicorn

from backend.core.config import settings
from backend.core.logging import setup_logging, get_logger

logger = get_logger("main")


async def start_dashboard():
    """启动 Dashboard API 服务"""
    config = uvicorn.Config(
        "backend.api.app:app",
        host=settings.app.host,
        port=settings.app.port,
        reload=False,
        log_level="info",
    )
    server = uvicorn.Server(config)
    await server.serve()


async def start_trade_engine():
    """启动 Trade Engine"""
    logger.info("Trade Engine not yet implemented")
    await asyncio.sleep(1)


async def start_full():
    """同时启动 Dashboard 和 Trade Engine"""
    await asyncio.gather(
        start_dashboard(),
        start_trade_engine(),
    )


def main():
    parser = argparse.ArgumentParser(description="XTQuant Trading System")
    parser.add_argument("--trade", action="store_true", help="仅启动 Trade Engine")
    parser.add_argument("--full", action="store_true", help="Dashboard + Trade Engine")
    args = parser.parse_args()

    setup_logging()

    if args.trade:
        asyncio.run(start_trade_engine())
    elif args.full and sys.platform == "win32":
        asyncio.run(start_full())
    else:
        asyncio.run(start_dashboard())


if __name__ == "__main__":
    main()
