import time

from xtquant.xttrader import XtQuantTrader
from xtquant.xttype import StockAccount
from xtquant import xtconstant

from utils.logger import get_logger

_logger = get_logger("get_trader")

class Trader:
    def __init__(
            self, 
             path="", 
             account_id="", 
             logger=_logger
        ):
        self.init_trader(
            path=path,
            account_id=account_id,
            logger=logger
        )

        self.logger = logger

    def __del__(self):
        self.xt_trader.stop()

    def init_trader(
            self,
            path="", 
            account_id="", 
            logger=_logger
        ):
        session_id = int(time.time())
        xt_trader = XtQuantTrader(path, session_id)
        xt_trader.start()
        connect_result = xt_trader.connect()
        logger.info(f"connect to path {path} result: {connect_result}")

        account = StockAccount(account_id)
        subscribe_result = xt_trader.subscribe(account)
        logger.info(f"subscribe account {account_id} result: {subscribe_result}")

        self.xt_trader = xt_trader
        self.account = account

    def buy_stock(
            self,
            ins,
            volume,
            price=0,
            price_type=xtconstant.LATEST_PRICE,
            strategy_name="",
            order_remark=""
        ):
        """
        购买股票
        args:
            ins: 股票代码
            volume: 购买数量
            price: 购买价格
            price_type: 价格类型
            strategy_name: 策略名称
            order_remark: 订单备注
        """
        self.logger.info(f"buy stock {ins} {volume} at {price}")
        async_seq = self.xt_trader.order_stock_async(
            account=self.account,
            ins=ins,
            order_type=xtconstant.STOCK_BUY,
            order_volume=volume,
            price_type=price_type,
            price=price,
            strategy_name=strategy_name,
            order_remark=order_remark
        )
        return async_seq
    
    def sell_stock(
            self,
            ins,
            volume,
            price=0,
            price_type=xtconstant.LATEST_PRICE,
            strategy_name="",
            order_remark=""
        ):
        """
        卖出股票
        args:
            ins: 股票代码
            volume: 卖出数量
            price: 卖出价格
            price_type: 价格类型
            strategy_name: 策略名称
            order_remark: 订单备注
        """
        self.logger.info(f"sell stock {ins} {volume} at {price}")
        async_seq = self.xt_trader.order_stock_async(
            account=self.account,
            ins=ins,
            order_type=xtconstant.STOCK_SELL,
            order_volume=volume,
            price_type=price_type,
            price=price,
            strategy_name=strategy_name,
            order_remark=order_remark
        )
        return async_seq