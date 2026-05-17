import yaml

from utils.logger import LogManager


class Config:
    required_fields = ["qmt_path", "account_id"]

    def __init__(self, config_path: str, logger: LogManager):
        with open(config_path, 'r', encoding='utf-8') as file:
            self.config = yaml.safe_load(file)
        self.logger = logger

        # 检查必需字段
        missing = [f for f in self.required_fields if f not in self.config]
        if missing:
            self.logger.error(f"配置文件中缺少: {', '.join(missing)}")
            raise Exception("配置文件无效")

        # 设置配置属性
        for field in self.required_fields:
            setattr(self, field, self.config[field])

        # 加载可选的交易配置
        trading = self.config.get("trading", {})
        self.max_position_per_stock = trading.get("max_position_per_stock", 10000)
        self.initial_capital = trading.get("initial_capital", 100000)
        self.check_interval = trading.get("check_interval", 60)
        self.order_volume = trading.get("order_volume", 100)

        # 加载策略配置
        self.strategies = self.config.get("strategy", {})

        self.logger.info(f"加载配置文件 {config_path} 成功")