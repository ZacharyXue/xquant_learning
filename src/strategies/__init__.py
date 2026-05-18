from .bonus_stocks import BonusStocksPolicy

# 如果平台可用，同时导出 StrategyBase 兼容类
try:
    from .bonus_stocks import BonusStocksStrategy
except ImportError:
    BonusStocksStrategy = None

# 只有 bonus_stocks 策略生效
all_strategies = {
    "bonus_stocks": BonusStocksPolicy,
}
