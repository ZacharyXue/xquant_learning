"""
统一配置管理

从 config/app.yaml 加载，支持环境变量覆盖。
敏感值 (qmt_path, account_id) 从环境变量读取，不写入文件。
"""

import os
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field

import yaml


PROJECT_ROOT = Path(__file__).parent.parent.parent


@dataclass
class AppConfig:
    host: str = "0.0.0.0"
    port: int = 8000


@dataclass
class DatabaseConfig:
    host: str = "127.0.0.1"
    port: int = 5432
    user: str = "postgres"
    password: str = "postgres"
    db: str = "xtquant"

    @property
    def url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.user}:{self.password}"
            f"@{self.host}:{self.port}/{self.db}"
        )

    @property
    def sync_url(self) -> str:
        return (
            f"postgresql+psycopg2://{self.user}:{self.password}"
            f"@{self.host}:{self.port}/{self.db}"
        )


@dataclass
class GRPCConfig:
    host: str = "localhost"
    port: int = 50051


@dataclass
class TradeConfig:
    qmt_path: str = ""
    account_id: str = ""
    mode: str = "real"
    max_position_per_stock: int = 10000
    initial_capital: float = 100000.0
    sim_initial_capital: float = 100000.0

    def __post_init__(self):
        self.qmt_path = os.getenv("XTQUANT_QMT_PATH", self.qmt_path)
        self.account_id = os.getenv("XTQUANT_ACCOUNT_ID", self.account_id)


@dataclass
class FeeConfig:
    commission_rate: float = 0.00025
    stamp_tax_rate: float = 0.001
    transfer_fee_rate: float = 0.00002
    min_commission: float = 5.0


@dataclass
class SlippageConfig:
    rate: float = 0.001
    mode: str = "fixed_rate"


@dataclass
class TradingHoursConfig:
    start: str = "09:30"
    end: str = "14:55"
    cancel_unfilled_at: str = "14:50"


@dataclass
class Settings:
    app: AppConfig = field(default_factory=AppConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    grpc: GRPCConfig = field(default_factory=GRPCConfig)
    trade: TradeConfig = field(default_factory=TradeConfig)
    fee: FeeConfig = field(default_factory=FeeConfig)
    slippage: SlippageConfig = field(default_factory=SlippageConfig)
    trading_hours: TradingHoursConfig = field(default_factory=TradingHoursConfig)

    @classmethod
    def from_yaml(cls, path: Optional[Path] = None) -> "Settings":
        if path is None:
            path = PROJECT_ROOT / "config" / "app.yaml"

        data: dict = {}
        if path.exists():
            with open(path, encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}

        settings = cls()

        if "app" in data:
            settings.app = AppConfig(**data["app"])
        if "database" in data:
            settings.database = DatabaseConfig(**data["database"])
        if "grpc" in data:
            settings.grpc = GRPCConfig(**data["grpc"])
        if "trade" in data:
            settings.trade = TradeConfig(**data["trade"])
        if "fee" in data:
            settings.fee = FeeConfig(**data["fee"])
        if "slippage" in data:
            settings.slippage = SlippageConfig(**data["slippage"])
        if "trading_hours" in data:
            settings.trading_hours = TradingHoursConfig(**data["trading_hours"])

        return settings


settings = Settings.from_yaml()
