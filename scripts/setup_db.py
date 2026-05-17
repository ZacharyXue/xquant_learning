#!/usr/bin/env python
"""数据库初始化脚本

创建所有 ORM 表（通过 SQLAlchemy Base.metadata.create_all）。
如果使用 Alembic 迁移，改用 alembic upgrade head。
"""

import asyncio
import sys
from pathlib import Path

# 确保项目根目录在 sys.path 中
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.core.logging import setup_logging, get_logger

setup_logging()
logger = get_logger("setup_db")


async def main():
    """初始化数据库：创建所有表（幂等操作）"""
    logger.info("正在检查数据库连接...")

    try:
        from backend.db.database import init_db
        await asyncio.wait_for(init_db(), timeout=10.0)
        logger.info("数据库初始化完成")
    except asyncio.TimeoutError:
        logger.warning("数据库连接超时，请检查 PostgreSQL 是否运行")
        sys.exit(1)
    except Exception as e:
        logger.error(f"数据库初始化失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
