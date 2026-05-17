"""
数据库连接管理

使用 SQLAlchemy 2.0 async engine + session。
"""

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import NullPool

from backend.core.config import settings

_engine = None
_session_factory = None


def get_engine():
    """获取异步引擎 (懒加载)"""
    global _engine
    if _engine is None:
        _engine = create_async_engine(
            settings.database.url,
            echo=False,
            poolclass=NullPool,
            pool_pre_ping=True,
            connect_args={
                "timeout": 10,
                "command_timeout": 10,
            },
        )
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """获取异步 session factory"""
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _session_factory


async def get_session() -> AsyncSession:
    """获取数据库 session (FastAPI 依赖注入用)"""
    factory = get_session_factory()
    try:
        async with factory() as session:
            yield session
            await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


async def get_session_safe() -> AsyncSession:
    """安全版 session - DB 不可用时返回 None"""
    factory = get_session_factory()
    try:
        async with factory() as session:
            yield session
            await session.commit()
    except Exception as e:
        from backend.core.logging import get_logger
        get_logger("db").warning(f"DB session unavailable: {e}")
        yield None
        return
    finally:
        try:
            await session.close()
        except Exception:
            pass


async def init_db() -> None:
    """初始化数据库 (创建所有表)"""
    from backend.db.models import Base
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """关闭数据库连接"""
    global _engine
    if _engine:
        await _engine.dispose()
        _engine = None
