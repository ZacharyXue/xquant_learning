#!/usr/bin/env python
"""数据库初始化脚本"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.core.logging import setup_logging
from backend.db.database import init_db, get_logger

logger = get_logger("setup_db")


async def main():
    setup_logging()
    logger.info("Initializing database...")
    try:
        await init_db()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
