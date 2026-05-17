"""FastAPI 应用工厂"""

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.core.config import settings
from backend.core.logging import setup_logging, get_logger
from backend.db.database import init_db, close_db, get_session
from backend.api.websocket import websocket_endpoint

logger = get_logger("app")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """应用生命周期: 启动时初始化，关闭时清理"""
    setup_logging()
    logger.info(f"Starting {settings.app.host}:{settings.app.port}")

    try:
        await asyncio.wait_for(init_db(), timeout=5.0)
        logger.info("Database initialized")
    except asyncio.TimeoutError:
        logger.warning("Database init timed out (server may be offline)")
    except Exception as e:
        logger.warning(f"Database init skipped: {e}")

    yield

    try:
        await close_db()
    except Exception:
        pass
    logger.info("Shutdown complete")


def create_app() -> FastAPI:
    app = FastAPI(
        title="XTQuant Trading System",
        description="基于 xtquant 的量化交易系统",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # WebSocket
    app.add_api_websocket_route("/ws", websocket_endpoint)

    # REST 路由
    from backend.api.routes.dashboard import router as dashboard_router
    from backend.api.routes.trade import router as trade_router
    from backend.api.routes.strategy import router as strategy_router
    from backend.api.routes.backtest import router as backtest_router
    from backend.api.routes.settings import router as settings_router

    app.include_router(dashboard_router, prefix="/api/dashboard", tags=["Dashboard"])
    app.include_router(trade_router, prefix="/api/trade", tags=["Trade"])
    app.include_router(strategy_router, prefix="/api/strategy", tags=["Strategy"])
    app.include_router(backtest_router, prefix="/api/backtest", tags=["Backtest"])
    app.include_router(settings_router, prefix="/api/settings", tags=["Settings"])

    # 健康检查
    @app.get("/api/health")
    async def health():
        return {"status": "ok", "version": "0.1.0"}

    # 优雅关闭
    @app.post("/api/shutdown")
    async def shutdown():
        from backend.core.shutdown import shutdown_manager
        asyncio.ensure_future(shutdown_manager.trigger())
        return {"status": "shutting_down"}

    return app


app = create_app()
