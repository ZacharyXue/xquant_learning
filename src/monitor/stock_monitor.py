import time
import yaml
import os
from common.trader import Trader
from common.stocks import get_stock_price_manager
from utils.logger import get_logger

_logger = get_logger("stock_monitor")

class StockMonitor:
    def __init__(self, config_path="config/stock_config.yaml"):
        """
        初始化股票监控器
        
        参数:
        config_path: 配置文件路径
        """
        self.config_path = config_path
        self.config = self._load_config()
        
        # 初始化交易器
        self.trader = Trader()
        
        # 使用交易器实例创建股票价格管理器
        self.price_manager = get_stock_price_manager(trader=self.trader)
        
        # 存储每只股票的基准价格
        self.base_prices = {}
        
        # 存储持仓情况
        self.positions = {}
        
        # 初始资金
        self.capital = self.config.get('trading', {}).get('initial_capital', 1000000)
        
        _logger.info("股票监控器初始化完成")
    
    def _load_config(self):
        """
        加载配置文件
        """
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            _logger.info(f"成功加载配置文件: {self.config_path}")
            return config
        except Exception as e:
            _logger.error(f"加载配置文件失败: {str(e)}")
            return {}
    
    def update_base_prices(self):
        """
        更新基准价格
        """
        stocks = self.config.get('stocks', {})
        for stock_code in stocks:
            price = self.price_manager.get_last_price(stock_code)
            if price:
                self.base_prices[stock_code] = price
                _logger.info(f"更新股票 {stock_code} 基准价格: {price}")
    
    def check_price_drop(self):
        """
        检查股价下跌情况
        """
        stocks = self.config.get('stocks', {})
        for stock_code, drop_threshold in stocks.items():
            current_price = self.price_manager.get_last_price(stock_code)
            if not current_price:
                _logger.warning(f"无法获取股票 {stock_code} 的当前价格")
                continue
            
            if stock_code not in self.base_prices:
                self.base_prices[stock_code] = current_price
                continue
            
            base_price = self.base_prices[stock_code]
            price_change_ratio = (current_price - base_price) / base_price
            
            _logger.debug(f"股票 {stock_code}: 当前价格={current_price}, 基准价格={base_price}, 涨跌幅={price_change_ratio:.4f}")
            
            # 检查是否下跌超过阈值
            if price_change_ratio <= -drop_threshold:
                self._execute_buy_order(stock_code, current_price, drop_threshold)
    
    def _execute_buy_order(self, stock_code, current_price, drop_threshold):
        """
        执行买入订单
        """
        # 检查是否有足够资金
        max_position = self.config.get('trading', {}).get('max_position_per_stock', 10000)
        order_volume = self.config.get('trading', {}).get('order_volume', 100)
        
        # 计算需要的资金
        required_funds = current_price * order_volume
        
        # 检查是否有足够资金
        if self.capital < required_funds:
            _logger.warning(f"资金不足，无法买入 {stock_code}，需要资金: {required_funds}，当前资金: {self.capital}")
            return
        
        # 执行买入
        try:
            async_seq = self.trader.buy_stock(
                ins=stock_code,
                volume=order_volume,
                price=0,  # 使用市价单
                price_type=1,  # 最新价格
                strategy_name="price_drop_strategy",
                order_remark=f"下跌{drop_threshold*100}%买入"
            )
            
            if async_seq > 0:
                # 更新资金和持仓
                self.capital -= required_funds
                if stock_code not in self.positions:
                    self.positions[stock_code] = 0
                self.positions[stock_code] += order_volume
                
                _logger.info(
                    f"买入成功: 股票={stock_code}, 数量={order_volume}, "
                    f"价格={current_price}, 资金变动={-required_funds}, "
                    f"剩余资金={self.capital}"
                )
                
                # 重置基准价格
                self.base_prices[stock_code] = current_price
            else:
                _logger.error(f"买入失败: 股票={stock_code}, 订单序列号={async_seq}")
        except Exception as e:
            _logger.error(f"执行买入订单异常: {str(e)}")
    
    def start_monitoring(self):
        """
        开始监控
        """
        _logger.info("开始监控股票价格")
        
        # 首先更新基准价格
        self.update_base_prices()
        
        check_interval = self.config.get('trading', {}).get('check_interval', 60)
        
        try:
            while True:
                self.check_price_drop()
                time.sleep(check_interval)
        except KeyboardInterrupt:
            _logger.info("监控被用户中断")
        except Exception as e:
            _logger.error(f"监控过程中发生异常: {str(e)}")
        finally:
            _logger.info("监控结束")

if __name__ == "__main__":
    monitor = StockMonitor()
    monitor.start_monitoring()