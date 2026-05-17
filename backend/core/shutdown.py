"""
优雅关闭管理

提供全局关闭信号，支持各个组件注册清理回调。
当收到 SIGINT (Ctrl+C) 或 shutdown API 请求时触发。
"""

import asyncio
import signal
from typing import Callable, Awaitable

from backend.core.logging import get_logger

logger = get_logger("shutdown")


class ShutdownManager:
    def __init__(self):
        self._event = asyncio.Event()
        self._callbacks: list[Callable[[], Awaitable[None]]] = []

    @property
    def is_set(self) -> bool:
        return self._event.is_set()

    @property
    def event(self) -> asyncio.Event:
        return self._event

    def register_callback(self, cb: Callable[[], Awaitable[None]]) -> None:
        self._callbacks.append(cb)

    async def trigger(self) -> None:
        logger.info("Shutdown triggered, running cleanup callbacks...")
        self._event.set()
        for cb in self._callbacks:
            try:
                await cb()
            except Exception as e:
                logger.error(f"Shutdown callback error: {e}")
        logger.info("Shutdown complete")

    def setup_signal_handlers(self, loop: asyncio.AbstractEventLoop) -> None:
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(
                    sig,
                    lambda: asyncio.ensure_future(self.trigger()),
                )
            except NotImplementedError:
                pass
        logger.debug("Signal handlers registered")


shutdown_manager = ShutdownManager()
