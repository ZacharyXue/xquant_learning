import argparse
import signal
import sys
import time
import subprocess
import os

# 添加 src 目录到 Python 路径，确保可以导入 utils
SRC_DIR = os.path.abspath(os.path.dirname(__file__))
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from utils.logger import get_logger
from utils.config import Config
from trade.grpc_trade_server import GRPCTradeServer

_logger = get_logger("trade_executor_grpc")

class TradeExecutorProcess:
    """专为多进程设计的交易执行器（gRPC版本）"""
    def __init__(self, config_path="config/stock_config.yaml", host='localhost', port=50051):
        """
        初始化交易执行器进程（gRPC版本）
        :param config_path: 配置文件路径
        :param host: gRPC服务器主机地址
        :param port: gRPC服务器端口号
        """
        self.config_path = config_path
        self.grpc_server = GRPCTradeServer(host=host, port=port, config_path=config_path, logger=_logger)
        self.running = True
        
        # 注册信号处理器以优雅地关闭进程
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        _logger.info("交易执行器进程(gRPC版本)初始化完成")

    def _signal_handler(self, signum, frame):
        """
        信号处理器，用于优雅地关闭进程
        """
        _logger.info(f"接收到信号 {signum}，准备关闭交易执行器")
        self.terminate()

    def initialize(self):
        """
        初始化交易器
        """
        # gRPC服务器会在启动时自动初始化交易器
        return True

    def terminate(self):
        """
        终止交易执行器
        """
        _logger.info("正在终止交易执行器...")
        self.running = False
        self.grpc_server.stop()

    def run(self):
        """
        运行交易执行器
        """
        if not self.initialize():
            _logger.error("初始化失败，无法启动交易执行器")
            return
            
        _logger.info("交易执行器开始运行")
        try:
            # 启动gRPC服务器
            self.grpc_server.start()
        except KeyboardInterrupt:
            _logger.info("接收到中断信号")
        finally:
            self.shutdown()

    def shutdown(self):
        """
        关闭交易执行器
        """
        _logger.info("正在关闭交易执行器...")
        self.running = False
        # gRPC服务器会自动关闭
        _logger.info("交易执行器已关闭")

def trade_executor_worker(config_path, host, port):
    """交易执行器工作进程函数"""
    executor = TradeExecutorProcess(config_path, host, port)
    executor.run()

class TradeExecutor:
    """原来的TradeExecutor类，用于兼容性（gRPC版本）"""
    def __init__(self, config_path="config/stock_config.yaml"):
        self.config_path = config_path
        
    def run(self):
        """作为独立进程运行"""
        parser = argparse.ArgumentParser(description='股票交易执行器(gRPC版本)')
        parser.add_argument('--config', type=str, default='config/stock_config.yaml',
                            help='配置文件路径')
        parser.add_argument('--host', type=str, default='localhost',
                            help='gRPC服务器主机地址')
        parser.add_argument('--port', type=int, default=50051,
                            help='gRPC服务器端口号')
        
        args = parser.parse_args()
        executor = TradeExecutorProcess(args.config, args.host, args.port)
        executor.run()
        
def main():
    """
    交易执行器主程序入口（用于独立运行，gRPC版本）
    """
    parser = argparse.ArgumentParser(description='股票交易执行器(gRPC版本)')
    parser.add_argument('--config', type=str, default='config/stock_config.yaml',
                        help='配置文件路径')
    parser.add_argument('--host', type=str, default='localhost',
                        help='gRPC服务器主机地址')
    parser.add_argument('--port', type=int, default=50051,
                        help='gRPC服务器端口号')
    
    args = parser.parse_args()
    
    # 创建交易执行器实例
    executor = TradeExecutorProcess(args.config, args.host, args.port)
    
    # 运行交易执行器
    executor.run()

if __name__ == "__main__":
    main()