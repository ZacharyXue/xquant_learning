import argparse
import datetime
import multiprocessing
import sys
import os
import time
import subprocess

# 添加 src 目录到 Python 路径
SRC_DIR = os.path.abspath(os.path.dirname(__file__))
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

import xtquant.xtdata as xtdata
import xtquant.xtconstant as xtconstant

from utils.logger import get_logger
from utils.config import Config
from trade_grpc.grpc_trade_client import GRPCTradeClient
from strategies import all_strategies

if sys.platform.startswith('win'):
    multiprocessing.set_start_method('spawn', force=True)

_logger = get_logger("strategy_executor_grpc")

# gRPC通信配置
GRPC_HOST = 'localhost'
GRPC_PORT = 50051


class DataProcessor:
    def __init__(self, config_path="config/stock_config.yaml", tgt_strategies:list=[]):
        """
        初始化数据处理器（gRPC版本）
        :param config_path: 配置文件路径
        """
        self.config_path = config_path
        self.config = Config(self.config_path, _logger)
        # 创建gRPC客户端
        self.grpc_client = GRPCTradeClient(host=GRPC_HOST, port=GRPC_PORT)
        
        # 建立连接并测试通信
        if not self._establish_connection():
            _logger.error("无法建立与交易执行器的连接")
            raise ConnectionError("无法建立与交易执行器的连接")
        _logger.info("数据处理器(gRPC版本)初始化完成")

        self.strategy_instances = {}
        for strategy_name, strategy_cls in all_strategies.items():
            if (not tgt_strategies) or (strategy_name in tgt_strategies):
                self.strategy_instances[strategy_name] = strategy_cls(self.config)
                _logger.debug(f"策略 {strategy_name} 初始化完成")

    def _establish_connection(self):
        """
        建立与交易执行器的连接并测试通信
        """
        try:
            # 连接到交易执行器
            if not self.grpc_client.connect():
                _logger.error("连接到交易执行器失败")
                return False
                
            # 测试连接通信
            if not self.grpc_client.test_connection():
                _logger.error("连接通信测试失败")
                return False
                
            return True
        except Exception as e:
            _logger.error(f"建立连接时发生错误: {e}")
            return False
    
    def _merge_trade_instructions(self, trade_dict, curr_trade_dict):
        """
        合并交易指令，实现相同方向累加，不同方向对冲
        
        :param trade_dict: 现有的交易指令字典
        :param curr_trade_dict: 当前策略生成的交易指令字典
        :return: 更新后的交易指令字典
        """
        if not curr_trade_dict:
            return trade_dict
        # 合并交易指令，处理同一证券的多次交易
        for stock, trade_info in curr_trade_dict.items():
            if stock in trade_dict:
                # 如果该证券已有交易指令，需要合并
                existing_trade = trade_dict[stock]
                new_trade_type = trade_info["type"]
                existing_trade_type = existing_trade["type"]
                
                # 相同方向的交易，数量累加
                if new_trade_type == existing_trade_type:
                    existing_trade["volume"] += trade_info["volume"]
                    _logger.debug(f"合并相同方向交易: {stock} {new_trade_type} 累加至 {existing_trade['volume']}")
                else:
                    # 不同方向的交易，进行对冲操作
                    existing_volume = existing_trade["volume"]
                    new_volume = trade_info["volume"]
                    
                    if existing_volume > new_volume:
                        # 原交易量更大，保持原方向，减去新交易量
                        existing_trade["volume"] = existing_volume - new_volume
                        _logger.debug(f"对冲交易: {stock} 原{existing_trade_type} {existing_volume} - 新{new_trade_type} {new_volume} = 剩余{existing_trade['volume']}")
                    elif new_volume > existing_volume:
                        # 新交易量更大，改为新方向，减去原交易量
                        trade_dict[stock]["type"] = new_trade_type
                        trade_dict[stock]["volume"] = new_volume - existing_volume
                        _logger.debug(f"对冲交易: {stock} 原{existing_trade_type} {existing_volume} - 新{new_trade_type} {new_volume} = 剩余{trade_dict[stock]['volume']}")
                    else:
                        # 交易量相等，完全对冲，移除该交易指令
                        del trade_dict[stock]
                        _logger.debug(f"对冲交易: {stock} 原{existing_trade_type} {existing_volume} 与 新{new_trade_type} {new_volume} 完全抵消")
            else:
                # 该证券首次出现交易指令，直接添加
                trade_dict[stock] = trade_info.copy()  # 使用copy避免引用问题
                _logger.debug(f"添加新交易指令: {stock} {trade_info}")
        
        return trade_dict
    
    def _trade_stocks(self, trade_dict):
        for stock, trade_info in trade_dict.items():
            trade_type = trade_info.pop("type")
            if trade_type == "buy":
                volume = trade_info.get("volume", 0)
                price = trade_info.get("price", 0.0)
                result = self.grpc_client.buy_stock(stock, volume, price)
                _logger.debug(f"{stock} - 已发送买入指令 {trade_info}, 结果: {result}")
            elif trade_type == "sell":
                volume = trade_info.get("volume", 0)
                price = trade_info.get("price", 0.0)
                result = self.grpc_client.sell_stock(stock, volume, price)
                _logger.debug(f"{stock} - 已发送卖出指令 {trade_info}, 结果: {result}")
            else:
                _logger.warning(f"{stock} - 未知交易类型 {trade_type}，忽略该指令")

    def quote_callback(self, data):
        """
        行情数据回调函数
        :param data: 行情数据
        """
        _logger.debug(f"获得行情数据：{data}")        

        trade_dict = {}
        for strategy_name, strategy_instance in self.strategy_instances.items():
            curr_trade_dict = strategy_instance(data)
            trade_dict = self._merge_trade_instructions(trade_dict, curr_trade_dict)
        _logger.debug(f"合并后的交易指令 {trade_dict}")

        self._trade_stocks(trade_dict)
        

    def run(self):
        """
        运行数据处理器
        """

        try:
            # 设置行情回调函数
            local_quote_callback = self.quote_callback

            # 收集所有需要订阅的股票代码
            all_stocks = list(self.config.stocks)

            # 如果启用了bonus_stocks策略，添加其ETF列表
            if "bonus_stocks" in self.strategy_instances:
                bonus_config = self.strategy_instances["bonus_stocks"].config
                bonus_etfs = bonus_config.get_etf_codes()
                all_stocks.extend(bonus_etfs)
                _logger.info(f"bonus_stocks 策略将订阅 ETF: {bonus_etfs}")

            # 去重
            all_stocks = list(set(all_stocks))

            # 订阅全推行情
            xtdata.subscribe_whole_quote(all_stocks, callback=local_quote_callback)

            _logger.info(f"数据处理器已启动，开始监听行情数据... 订阅股票: {all_stocks}")

            # 阻塞主线程退出
            try:
                # 这里我们使用一个简单的循环来保持主线程运行
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                _logger.info("接收到中断信号")

        except Exception as e:
            _logger.error(f"运行数据处理器时发生错误: {e}")
        finally:
            # 清理资源
            self.grpc_client.close()
            _logger.info("数据处理器已停止")

def interact():
    """执行后进入repl模式"""
    import code
    code.InteractiveConsole(locals=globals()).interact()

def main():
    """主程序入口"""
    import argparse

    parser = argparse.ArgumentParser(description='策略执行器 (gRPC版本)')
    parser.add_argument('--strategy', type=str, nargs='+', default=[],
                        help='指定要运行的策略，如 buy_on_dips bonus_stocks')
    parser.add_argument('--config', type=str, default='config/stock_config.yaml',
                        help='配置文件路径')

    args = parser.parse_args()

    processor = DataProcessor(config_path=args.config, tgt_strategies=args.strategy)
    processor.run()


if __name__ == "__main__":
    main()