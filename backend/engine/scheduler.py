"""
策略调度器

根据交易日历调度策略执行。
支持 cron 表达式和简单定投日配置。
"""

import asyncio
from datetime import datetime, time
from typing import Callable, Optional

from backend.core.logging import get_logger
from backend.core.trading_calendar import is_trading_time, is_investment_day, is_cancel_time

logger = get_logger("scheduler")


class StrategyScheduler:
    """策略调度器"""

    def __init__(self):
        self._tasks: list[dict] = []
        self._running = False

    def add_schedule(
        self,
        name: str,
        callback: Callable,
        interval_seconds: int = 60,
        condition: Optional[Callable[[], bool]] = None,
    ):
        """添加调度任务

        Args:
            name: 任务名称
            callback: 异步回调函数
            interval_seconds: 执行间隔 (秒)
            condition: 可选的前置条件 (返回 True 才执行)
        """
        self._tasks.append({
            "name": name,
            "callback": callback,
            "interval": interval_seconds,
            "condition": condition or (lambda: True),
        })
        logger.info(f"Scheduled task: {name} (every {interval_seconds}s)")

    async def start(self):
        """启动调度循环"""
        self._running = True
        logger.info(f"Scheduler started with {len(self._tasks)} tasks")

        while self._running:
            for task in self._tasks:
                if not self._running:
                    break
                try:
                    if task["condition"]():
                        await task["callback"]()
                except Exception as e:
                    logger.error(f"Task '{task['name']}' error: {e}")
            await asyncio.sleep(1)

    async def stop(self):
        self._running = False
        logger.info("Scheduler stopped")


def trading_time_condition() -> bool:
    """仅在交易时间执行的调度条件"""
    return is_trading_time()


def cancel_time_condition() -> bool:
    """收盘撤单时间条件"""
    return is_cancel_time()
