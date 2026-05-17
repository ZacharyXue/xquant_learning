import yaml

from .logger import LogManager

class Config:
    def __init__(self, config_path: str, logger: LogManager):
        with open(config_path, 'r', encoding='utf-8') as file:
            self.config = yaml.safe_load(file)
        self.logger = logger
        self.stocks = self._extract_all_stocks()
        self.logger.info(f"加载配置文件 {config_path} 成功")
        self.logger.info(f"配置为 {self.config=}")
        self.logger.info(f"配置为 {self.stocks=}")

    def _extract_all_stocks(self):
        all_stocks = set()

        if 'strategy' in self.config:
            for strategy_name, strategy_config in self.config['strategy'].items():
                if 'stocks' in strategy_config:
                    for stock in strategy_config['stocks']:
                        if isinstance(stock, str):
                            all_stocks.add(stock)
                        elif isinstance(stock, dict) and 'code' in stock:
                            all_stocks.add(stock['code'])
        
        return all_stocks