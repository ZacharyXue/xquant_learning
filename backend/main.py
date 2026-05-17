"""XTQuant Trading System - 统一入口

Usage:
    python -m backend.main              # 启动 Dashboard API 服务
    python -m backend.main --trade      # 仅启动 Trade Engine (Windows)
    python -m backend.main --full       # Dashboard + Trade Engine (Windows only)
"""

import argparse
import asyncio
import signal
import sys
import uvicorn

from backend.core.config import settings
from backend.core.logging import setup_logging, get_logger
from backend.core.shutdown import shutdown_manager

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

    async def _serve():
        await server.serve()

    task = asyncio.ensure_future(_serve())

    # 等待关闭信号
    await shutdown_manager.event.wait()
    logger.info("Dashboard shutting down...")
    server.should_exit = True
    await task


async def start_trade_engine():
    """启动 Trade Engine"""
    from backend.trade.engine import TradeEngine
    from backend.api.websocket import get_ws_manager

    engine = TradeEngine()
    engine.set_ws_manager(get_ws_manager())

    try:
        ok = await engine.initialize()
        if not ok:
            logger.error("TradeEngine initialization failed")
            return
        await engine.run()
    finally:
        await engine.close()


async def start_full():
    """同时启动 Dashboard 和 Trade Engine"""
    logger.info("Starting full mode (Dashboard + Trade Engine)...")
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

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    shutdown_manager.setup_signal_handlers(loop)

    try:
        if args.trade:
            loop.run_until_complete(start_trade_engine())
        elif args.full and sys.platform == "win32":
            loop.run_until_complete(start_full())
        else:
            loop.run_until_complete(start_dashboard())
    except KeyboardInterrupt:
        pass
    finally:
        pending = asyncio.all_tasks(loop)
        if pending:
            loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        loop.close()
        logger.info("Process exit")


if __name__ == "__main__":
    main()
