"""
    当日大跌买入策略
     当股票价格相对前一日收盘下跌超过一定阈值时，购买股票
    
    TODO:
        - [ ] 记录 30/90日价格（最低、最高、开盘、收盘） 买入记录 持仓
        - [ ] 支持控制仓位决定是否购买（总仓位，每月买入次数）
        - [ ] 尾盘买入+买入状态查询（当前只能检查是否下单成功）
        - [ ] 支持回测技术指标
        - [ ] 支持下跌幅度测算
        - [ ] 买入/交易成功 记录成交 微信提醒
        - [x] 支持下跌回升后/收盘时买入
"""
from datetime import datetime

from utils.logger import get_logger
from utils.config import Config

_logger = get_logger("buy_on_dips")

class _StockConfig:
    def __init__(self, stock_config: dict):
        self.code = stock_config['code']
        self.name = stock_config['name']
        self.threshold = stock_config['threshold']
        self.order_volume = stock_config['order_volume']

class BuyOnDipsConfig(Config):
    def __init__(self, config_path: str = None, base_config: Config = None):
        if base_config:
            self.config = base_config.config
            self.logger = base_config.logger
            self.stocks = base_config.stocks
        else:
            super().__init__(config_path, _logger)
        
        # 获取策略特定的配置
        self.policy_config = self.config['strategy']['buy_on_dips']
        self.stocks = self.get_stock_config()

    def get_stock_config(self):
        ret_dict = {}
        for stock in self.policy_config['stocks']:
            ret_dict[stock['code']] = _StockConfig(stock)
        return ret_dict
    
    @classmethod
    def init_config(cls, config: Config):
        return cls(base_config=config)
    
class BuyOnDipsPolicy:
    def __init__(self, config: Config):
        self.config = BuyOnDipsConfig.init_config(config)
        self.logger = _logger
        self.stocks = self.config.stocks
        self.bm_prices = {}   # 记录上一日收盘价/上次买入价格，用于决定当前是否买入
        self.low_prices = {}  # 记录触发交易信号价格，等待回升或收盘时买入

    def __call__(self, data: dict) -> dict:
        """
        购买在低位的股票

        return {
            stock_code: order_volume
        }
        """
        now = datetime.now()
        # 当前不参与集合竞价
        # 9:30-14:55 正常交易时间
        if (now.hour < 9 or (now.hour == 9 and now.minute < 30)) or \
           (now.hour > 14 or (now.hour == 14 and now.minute >= 55)):
            self.logger.debug(f"{now} 不在正常交易时间")
            return
        buy_dict = {}
        for stock, stock_data in data.items():
            if "lastPrice" not in stock_data or "lastClose" not in stock_data:
                continue

            if stock not in self.stocks:
                continue
            if stock not in self.bm_prices:
                self.bm_prices[stock] = stock_data['lastClose']
                continue
                
            current_price = stock_data['lastPrice']
            pre_price = self.bm_prices[stock]
            
            if current_price <= 0 or pre_price <= 0:
                continue
                
            ratio = current_price / pre_price
            self.logger.debug(f"{now} 最新价 股票 {stock} 最新价 {current_price} 基准价 {pre_price} 价差 {ratio}")
            
            # 检查是否满足买入条件
            if ratio < self.stocks[stock].threshold:
                # 触发交易信号，记录当前价格
                if not (now.hour == 14 and now.minute > 45):
                    if stock not in self.low_prices:  
                        self.low_prices[stock] = current_price
                        self.logger.debug(f"最新价 触发交易信号 {stock} 最新价 {current_price} 初始化基准价 {self.low_prices[stock]} 价差 {(current_price - self.low_prices[stock]) / self.low_prices[stock]}")
                        continue
                    elif stock in self.low_prices and (current_price - self.low_prices[stock]) < max(0.002, self.low_prices[stock] * 0.001):
                        self.low_prices[stock] = current_price
                        self.logger.debug(f"最新价 触发交易信号 {stock} 最新价 {current_price} 更新基准价 {self.low_prices[stock]} 价差 {(current_price - self.low_prices[stock]) / self.low_prices[stock]}")
                        continue

                self.logger.info(f"{now} 最新价 买入 {stock} {self.stocks[stock].order_volume}股")
                self.logger.debug(f"{now} 最新价 符合买入条件 {stock} 最新价 {current_price} 基准价 {self.low_prices[stock]} 价差 {(current_price - self.low_prices[stock]) / self.low_prices[stock]}")
                buy_dict[stock] = {
                    "stock_code": stock,
                    "type": "buy",
                    "volume": self.stocks[stock].order_volume,
                    "price": 0
                }
                self.bm_prices[stock] = current_price
                del self.low_prices[stock]           

        self.logger.debug(f"{now} 最新价 符合买入条件的股票 {buy_dict}")
        return buy_dict
