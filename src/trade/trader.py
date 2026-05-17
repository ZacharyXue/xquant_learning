import sys
import time

from datetime import datetime

from xtquant.xttrader import XtQuantTrader, XtQuantTraderCallback
from xtquant.xttype import StockAccount
from xtquant import xtconstant

from utils.logger import get_logger

_logger = get_logger("get_trader")

class Trader:
    def __init__( self, path: str, account_id: str, logger=_logger):
        self.init_trader(
            path=path,
            account_id=account_id,
            logger=logger
        )

        self.asset = None
        self.stocks_info = {}
        self.logger = logger

    def __del__(self):
        self.xt_trader.stop()

    def init_trader(
            self,
            path: str, 
            account_id: str, 
            logger=_logger
        ):
        session_id = int(time.time())
        xt_trader = XtQuantTrader(path, session_id)
        callback = MyXtQuantTraderCallback(trader=self, logger=logger)
        xt_trader.register_callback(callback)
        xt_trader.start()

        connect_result = xt_trader.connect()
        logger.info(f"connect to path {path} result: {connect_result}")

        account = StockAccount(account_id)
        subscribe_result = xt_trader.subscribe(account)
        if subscribe_result != 0:
            logger.error(f"subscribe account {account_id} error: {subscribe_result}")
            raise Exception(f"subscribe account {account_id} error: {subscribe_result}")
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
            stock_code=ins,
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
            stock_code=ins,
            order_type=xtconstant.STOCK_SELL,
            order_volume=volume,
            price_type=price_type,
            price=price,
            strategy_name=strategy_name,
            order_remark=order_remark
        )
        return async_seq
    
    def cancel_order_stock(self, order_id):
        """
        撤销股票订单
        args:
            order_id: 订单ID
        """
        self.logger.info(f"cancel order {order_id}")
        async_seq = self.xt_trader.cancel_order_stock_async(
            account=self.account,
            order_id=order_id
        )
        return async_seq
    
    def get_asset(self):
        """
        获取资产
        """
        asset = self.xt_trader.query_stock_asset(self.account)
        self.asset = asset
        return asset
    
    def get_stock_position(self, ins):
        """
        获取股票持仓
        args:
            ins: 股票代码
        returns:
            position: 股票持仓 obj, (account_id, stock_code, volume)
        """
        position = self.xt_trader.query_stock_position(self.account, ins)
        self.stocks_info[ins] = position
        return position
    
    def get_all_stock_positions(self):
        """
        获取所有股票持仓
        """
        positions = self.xt_trader.query_stock_positions(self.account)
        self.stocks_info = {pos.stock_code: pos for pos in positions}
        return positions
    
    def get_unfilled_orders(self):
        """
        查询所有未成交订单（可撤销的订单）
        returns:
            orders: 未成交订单列表
        """
        orders = self.xt_trader.query_stock_orders(self.account, cancelable_only=True)
        return orders

    def cancel_unfilled_orders(self):
        """
        取消所有未成交订单
        returns:
            canceled_count: 取消的订单数量
        """
        orders = self.get_unfilled_orders()
        canceled_count = 0
        for order in orders:
            try:
                self.cancel_order_stock(order.order_id)
                canceled_count += 1
                self.logger.info(f"已取消未成交订单: {order.order_id}")
            except Exception as e:
                self.logger.error(f"取消订单失败 {order.order_id}: {e}")
        self.logger.info(f"共取消 {canceled_count} 个未成交订单")
        return canceled_count

    def update_account_info(self):
        """
        更新账户信息
        """
        try:
            asset = self.get_asset()
        except Exception as e:
            self.logger.error(f"get asset error: {e}")
            return
        try:
            positions = self.get_all_stock_positions()
        except Exception as e:
            self.logger.error(f"get all stock positions error: {e}")
            return
        self.logger.info(f"asset: {asset}")
        self.logger.info(f"positions: {positions}")
    
class MyXtQuantTraderCallback(XtQuantTraderCallback):
    def __init__(self, trader: Trader, logger=_logger):
        super().__init__()
        self.trader = trader
        self.logger = logger

    def on_disconnected(self):
        """
        连接断开
        :return:
        """
        self.logger.info(datetime.datetime.now(), '连接断开回调')

    def on_stock_order(self, order):
        """
        委托回报推送
        :param order: XtOrder对象
        :return:
        """
        self.logger.info(datetime.datetime.now(), '委托回调', order.order_remark)

    def on_stock_trade(self, trade):
        """
        成交变动推送
        :param trade: XtTrade对象
        :return:
        """
        self.trader.update_account_info()
        self.logger.info('成交', f"{trade.stock_code=}", f"{trade.trade_price=}", f"{trade.trade_volume=}")

    def on_order_error(self, order_error):
        """
        委托失败推送
        :param order_error:XtOrderError 对象
        :return:
        """
        # print("on order_error callback")
        # print(order_error.order_id, order_error.error_id, order_error.error_msg)
        self.logger.info(f"委托报错回调 {order_error.order_remark} {order_error.error_msg}")

    def on_cancel_error(self, cancel_error):
        """
        撤单失败推送
        :param cancel_error: XtCancelError 对象
        :return:
        """
        self.logger.info(datetime.now(), sys._getframe().f_code.co_name)

    def on_order_stock_async_response(self, response):
        """
        异步下单回报推送
        :param response: XtOrderResponse 对象
        :return:
        """
        self.logger.info(f"异步委托回调 {response.order_remark}")

    def on_cancel_order_stock_async_response(self, response):
        """
        :param response: XtCancelOrderResponse 对象
        :return:
        """
        self.logger.info(datetime.now(), sys._getframe().f_code.co_name)

    def on_account_status(self, status):
        """
        :param response: XtAccountStatus 对象
        :return:
        """
        self.logger.info(datetime.now(), sys._getframe().f_code.co_name)
