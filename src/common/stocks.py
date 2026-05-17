from common.trader import Trader
from utils.logger import get_logger

_logger = get_logger("stock_price")

class StockPriceManager:
    def __init__(self, trader: Trader = None, logger=_logger):
        """
        初始化股票价格管理器
        
        参数:
        trader: 已初始化的Trader实例，如果为None则创建新实例
        logger: 日志对象
        """
        self.logger = logger
        
        # 如果没有提供trader实例，则创建一个新的
        if trader is None:
            self.trader = Trader()
            self.logger.info("创建了新的Trader实例用于获取股票价格")
        else:
            self.trader = trader
            self.logger.info("使用已提供的Trader实例获取股票价格")
        
        # 直接使用trader中的xt_trader对象
        self.xt_trader = self.trader.xt_trader
    
    def get_last_price(self, stock_code):
        """
        获取股票最新价格
        
        参数:
        stock_code: 股票代码，格式如"SH600000"
        
        返回:
        float: 最新价格，如果失败返回None
        """
        try:
            if not self.xt_trader:
                self.logger.error("交易接口未初始化")
                return None
            
            price = self.xt_trader.get_last_price(stock_code)
            self.logger.info(f"获取股票 {stock_code} 最新价格: {price}")
            return price
        except Exception as e:
            self.logger.error(f"获取股票 {stock_code} 最新价格失败: {str(e)}")
            return None
    
    def get_stock_realtime_quotes(self, stock_code):
        """
        获取股票实时行情
        
        参数:
        stock_code: 股票代码，格式如"SH600000"
        
        返回:
        dict: 包含实时行情数据的字典，如果失败返回None
        """
        try:
            if not self.xt_trader:
                self.logger.error("交易接口未初始化")
                return None
            
            quotes = self.xt_trader.get_stock_realtime_quotes(stock_code)
            self.logger.info(f"获取股票 {stock_code} 实时行情成功")
            return quotes
        except Exception as e:
            self.logger.error(f"获取股票 {stock_code} 实时行情失败: {str(e)}")
            return None
    
    def get_history_klines(self, stock_code, period, start_time, end_time):
        """
        获取股票历史K线数据
        
        参数:
        stock_code: 股票代码，格式如"SH600000"
        period: K线周期，如"1m"(1分钟), "5m"(5分钟), "15m"(15分钟), "30m"(30分钟), "60m"(60分钟), "1d"(日线)
        start_time: 开始时间，格式如"20240101093000"
        end_time: 结束时间，格式如"20240101150000"
        
        返回:
        list: K线数据列表，如果失败返回None
        """
        try:
            if not self.xt_trader:
                self.logger.error("交易接口未初始化")
                return None
            
            klines = self.xt_trader.get_history_klines(stock_code, period, start_time, end_time)
            self.logger.info(f"获取股票 {stock_code} 历史K线数据成功，数据量: {len(klines) if klines else 0}")
            return klines
        except Exception as e:
            self.logger.error(f"获取股票 {stock_code} 历史K线数据失败: {str(e)}")
            return None
    
    def get_order_book(self, stock_code):
        """
        获取股票盘口数据
        
        参数:
        stock_code: 股票代码，格式如"SH600000"
        
        返回:
        dict: 盘口数据字典，如果失败返回None
        """
        try:
            if not self.xt_trader:
                self.logger.error("交易接口未初始化")
                return None
            
            order_book = self.xt_trader.get_order_book(stock_code)
            self.logger.info(f"获取股票 {stock_code} 盘口数据成功")
            return order_book
        except Exception as e:
            self.logger.error(f"获取股票 {stock_code} 盘口数据失败: {str(e)}")
            return None

# 提供一个方便的函数来获取股票价格管理器实例
def get_stock_price_manager(trader=None, logger=_logger):
    """
    获取股票价格管理器实例
    
    参数:
    trader: 已初始化的Trader实例，如果为None则创建新实例
    logger: 日志对象
    
    返回:
    StockPriceManager实例
    """
    return StockPriceManager(trader, logger)

if __name__ == "__main__":
    # 示例用法1：创建新的trader实例
    price_manager1 = get_stock_price_manager()
    last_price1 = price_manager1.get_last_price("SH600000")  # 浦发银行
    print(f"方法1 - 最新价格: {last_price1}")
    
    # 示例用法2：使用已初始化的trader实例
    from src.common.trader import Trader
    my_trader = Trader()
    price_manager2 = get_stock_price_manager(trader=my_trader)
    last_price2 = price_manager2.get_last_price("SH600000")  # 浦发银行
    print(f"方法2 - 最新价格: {last_price2}")