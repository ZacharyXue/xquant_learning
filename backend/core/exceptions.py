class XTQuantError(Exception):
    """xtquant 量化交易系统基础异常"""


class ConfigError(XTQuantError):
    """配置错误"""


class TradeError(XTQuantError):
    """交易错误"""


class StrategyError(XTQuantError):
    """策略错误"""


class DatabaseError(XTQuantError):
    """数据库错误"""


class GRPCError(XTQuantError):
    """gRPC 通信错误"""


class RiskLimitError(TradeError):
    """风控限制"""
