"""
策略注册中心

管理所有策略的注册、发现和生命周期。
"""

from typing import Optional, Type

from backend.core.logging import get_logger
from backend.engine.strategy_base import StrategyBase

logger = get_logger("strategy_registry")

_registry: dict[str, type] = {}
_instances: dict[str, StrategyBase] = {}


def register(cls):
    """装饰器: 注册策略类"""
    _registry[cls.name] = cls
    logger.info(f"Strategy registered: {cls.name} ({cls.display_name})")
    return cls


def get(name: str) -> Optional[type]:
    """获取策略类"""
    return _registry.get(name)


def list_all() -> list[type]:
    return list(_registry.values())


def create(name: str, config: dict = None) -> Optional[StrategyBase]:
    """创建策略实例"""
    cls = _registry.get(name)
    if not cls:
        logger.warning(f"Strategy '{name}' not found")
        return None
    instance = cls(config)
    _instances[name] = instance
    return instance


def get_instance(name: str) -> Optional[StrategyBase]:
    return _instances.get(name)


def get_all_instances() -> list[StrategyBase]:
    return list(_instances.values())


def get_active_instances() -> list[StrategyBase]:
    return [s for s in _instances.values() if s.enabled]
