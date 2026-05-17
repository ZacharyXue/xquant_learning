import grpc
import time
import threading
from concurrent import futures
from datetime import datetime, date

from utils.logger import get_logger
from trade.config import Config
from trade.trader import Trader
import trade_grpc.trade_service_pb2 as trade_service_pb2
import trade_grpc.trade_service_pb2_grpc as trade_service_pb2_grpc

_logger = get_logger("grpc_trade_server")

class TradeServiceServicer(trade_service_pb2_grpc.TradeServiceServicer):
    """交易服务实现"""
    
    def __init__(self, config_path="config/stock_config.yaml", logger=_logger):
        """
        初始化交易服务
        :param config_path: 配置文件路径
        """
        self.config_path = config_path
        self.config = None
        self.trader = None
        self.running = True
        self.logger = logger

        # 标记当天是否已执行过取消操作
        self._canceled_today = False
        self._last_cancel_date = None

        # 初始化交易器
        self._initialize_trader()

        # 启动定时取消未成交订单线程
        self._start_cancel_unfilled_orders_timer()

        self.logger.info("gRPC交易服务初始化完成")
    
    def _initialize_trader(self):
        """初始化交易器"""
        try:
            # 加载配置文件
            self.config = Config(self.config_path, self.logger)
            self.logger.info("配置文件加载成功")

            # 初始化交易器
            self.trader = Trader(
                logger=_logger,
                path = self.config.qmt_path,
                account_id = self.config.account_id
            )
            self.logger.info("交易器初始化完成")
        except Exception as e:
            self.logger.error(f"初始化交易器失败: {e}")
            import traceback
            self.logger.error(traceback.format_exc())

    def _start_cancel_unfilled_orders_timer(self):
        """启动定时取消未成交订单线程"""
        def check_and_cancel():
            while self.running:
                now = datetime.now()
                today = now.date()

                # 检查是否跨越了新的交易日
                if self._last_cancel_date != today:
                    self._canceled_today = False
                    self._last_cancel_date = today

                # 检查是否在 14:50 之后
                if now.hour > 14 or (now.hour == 14 and now.minute >= 50):
                    if not self._canceled_today:
                        self._cancel_unfilled_orders()
                        self._canceled_today = True

                time.sleep(60)  # 每分钟检查一次

        thread = threading.Thread(target=check_and_cancel, daemon=True)
        thread.start()
        self.logger.info("定时取消未成交订单线程已启动")

    def _cancel_unfilled_orders(self):
        """取消所有未成交订单"""
        if not self.trader:
            self.logger.warning("交易器未初始化，无法取消订单")
            return

        try:
            count = self.trader.cancel_unfilled_orders()
            self.logger.info(f"定时任务：已取消 {count} 个未成交订单")
        except Exception as e:
            self.logger.error(f"取消未成交订单失败: {e}")
    
    def BuyStock(self, request, context):
        """
        买入股票
        """
        try:
            self.logger.info(f"接收到买入请求: {request.stock_code} {request.volume}股，价格: {request.price}")

            if not self.trader:
                self.logger.error("交易器未初始化")
                return trade_service_pb2.TradeResponse(
                    success=False,
                    error="交易器未初始化"
                )

            if not request.price:
                async_seq = self.trader.buy_stock(
                    ins=request.stock_code, 
                    volume=request.volume, 
                    price=request.price
                )
            else:
                from xtquant import xtconstant

                async_seq = self.trader.buy_stock(
                    ins=request.stock_code, 
                    volume=request.volume, 
                    price_type=xtconstant.FIX_PRICE,
                    price=request.price
                )

            self.logger.info(f"买入 {request.stock_code} {request.volume}股，异步序列: {async_seq}")
            
            return trade_service_pb2.TradeResponse(
                success=True,
                async_seq=async_seq
            )
            
        except Exception as e:
            self.logger.error(f"买入操作失败: {e}")
            return trade_service_pb2.TradeResponse(
                success=False,
                error=str(e)
            )
    
    def SellStock(self, request, context):
        """
        卖出股票
        """
        try:
            self.logger.info(f"接收到卖出请求: {request.stock_code} {request.volume}股，价格: {request.price}")

            if not self.trader:
                self.logger.error("交易器未初始化")
                return trade_service_pb2.TradeResponse(
                    success=False,
                    error="交易器未初始化"
                )
            
            if not request.price:
                async_seq = self.trader.sell_stock(
                    stock_code=request.stock_code,
                    volume=request.volume,
                    price=request.price
                )
            else:
                from xtquant import xtconstant
                async_seq = self.trader.sell_stock(
                    stock_code=request.stock_code,
                    volume=request.volume,
                    price_type=xtconstant.FIX_PRICE,
                    price=request.price
                )
            self.logger.info(f"卖出 {request.stock_code} {request.volume}股，异步序列: {async_seq}")
            
            return trade_service_pb2.TradeResponse(
                success=True,
                async_seq=async_seq
            )
           
        except Exception as e:
            self.logger.error(f"卖出操作失败: {e}")
            return trade_service_pb2.TradeResponse(
                success=False,
                error=str(e)
            )
    
    def CancelStock(self, request, context):
        """
        撤销股票订单
        """
        try:
            self.logger.info(f"接收到撤单请求: 订单ID {request.order_id}")

            if not self.trader:
                self.logger.error("交易器未初始化")
                return trade_service_pb2.TradeResponse(
                    success=False,
                    error="交易器未初始化"
                )
            
            async_seq = self.trader.cancel_order_stock(
                order_id=request.order_id
            )
            self.logger.info(f"撤销订单 {request.order_id}，异步序列: {async_seq}")
            
            return trade_service_pb2.TradeResponse(
                success=True,
                async_seq=async_seq
            )
        except Exception as e:
            self.logger.error(f"撤销订单操作失败: {e}")
            return trade_service_pb2.TradeResponse(
                success=False,
                error=str(e)
            )
    
    def TestConnection(self, request, context):
        """
        测试连接
        """
        self.logger.info(f"接收到连接测试请求: {request.message}")
        
        return trade_service_pb2.TestResponse(
            status="connected",
            message="连接正常",
            timestamp=int(time.time())
        )
    
    def Shutdown(self, request, context):
        """
        关闭服务
        """
        self.logger.info("接收到关闭服务请求")
        self.running = False
        
        return trade_service_pb2.ShutdownResponse(
            success=True,
            message="服务正在关闭"
        )

class GRPCTradeServer:
    """gRPC交易服务器"""
    
    def __init__(self, host='localhost', port=50051, config_path="config/stock_config.yaml", logger=_logger):
        """
        初始化gRPC交易服务器
        :param host: 服务器主机地址
        :param port: 服务器端口号
        :param config_path: 配置文件路径
        """
        self.host = host
        self.port = port
        self.config_path = config_path
        self.server = None
        self.servicer = None
        self.logger = logger
    
    def start(self):
        """启动gRPC服务器"""
        try:
            # 创建gRPC服务器
            self.server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
            
            # 创建服务实现
            self.servicer = TradeServiceServicer(self.config_path, self.logger)
            
            # 添加服务到服务器
            trade_service_pb2_grpc.add_TradeServiceServicer_to_server(
                self.servicer, self.server
            )
            
            # 绑定端口
            server_address = f'{self.host}:{self.port}'
            self.server.add_insecure_port(server_address)
            
            # 启动服务器
            self.server.start()
            self.logger.info(f"gRPC服务器已启动，监听 {server_address}")
            
            # 等待服务器终止
            self.server.wait_for_termination()
            
        except Exception as e:
            self.logger.error(f"启动gRPC服务器失败: {e}")
    
    def stop(self):
        """停止gRPC服务器"""
        if self.server:
            self.logger.info("正在关闭gRPC服务器...")
            self.server.stop(grace=None)
            self.logger.info("gRPC服务器已关闭")

def main():
    """主程序入口"""
    import argparse
    
    parser = argparse.ArgumentParser(description='gRPC交易服务器')
    parser.add_argument('--config', type=str, default='config/stock_config.yaml',
                        help='配置文件路径')
    parser.add_argument('--host', type=str, default='localhost',
                        help='服务器主机地址')
    parser.add_argument('--port', type=int, default=50051,
                        help='服务器端口号')
    
    args = parser.parse_args()
    
    # 创建并启动gRPC服务器
    grpc_server = GRPCTradeServer(args.host, args.port, args.config)
    
    try:
        grpc_server.start()
    except KeyboardInterrupt:
        grpc_server.logger.info("接收到中断信号")
    finally:
        grpc_server.stop()

if __name__ == "__main__":
    main()