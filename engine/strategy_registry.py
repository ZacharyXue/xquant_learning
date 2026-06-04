"""Strategy registry with @register decorator"""

from engine.strategy_base import StrategyBase

_registry: dict[str, type[StrategyBase]] = {}


def register(cls):
    if not cls.name:
        raise ValueError(f"Strategy class {cls.__name__} must have a 'name'")
    if cls.name in _registry:
        raise ValueError(f"Strategy '{cls.name}' already registered")
    _registry[cls.name] = cls
    return cls


def get(name: str) -> type[StrategyBase] | None:
    return _registry.get(name)


def list_all() -> list[str]:
    return list(_registry.keys())


def create(name: str, config: dict = None) -> StrategyBase:
    cls = get(name)
    if cls is None:
        raise ValueError(f"Strategy '{name}' not found. Available: {list_all()}")
    return cls(config=config)


def clear():
    _registry.clear()
