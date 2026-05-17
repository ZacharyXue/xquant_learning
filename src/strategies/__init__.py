from .bonus_stocks import BonusStocksPolicy

# 只有 bonus_stocks 策略生效
all_strategies = {
    "bonus_stocks": BonusStocksPolicy,
}
