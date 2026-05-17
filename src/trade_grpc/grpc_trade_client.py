import grpc
import time

from utils.logger import get_logger
import trade_grpc.trade_service_pb2 as trade_service_pb2
import trade_grpc.trade_service_pb2_grpc as trade_service_pb2_grpc

_logger = get_logger("grpc_trade_client")

class GRPCTradeClient:
    """gRPC交易客户端"""
    
    def __init__(self, host='localhost', port=50051):
        """
        初始化gRPC交易客户端
        :param host: 服务器主机地址
        :param port: 服务器端口号
        """
        self.host = host
        self.port = port
        self.channel = None
        self.stub = None
        self.connected = False
        
        _logger.info("gRPC交易客户端初始化完成")
    
    def connect(self):
        """连接到gRPC服务器"""
        try:
            server_address = f'{self.host}:{self.port}'
            self.channel = grpc.insecure_channel(server_address)
            self.stub = trade_service_pb2_grpc.TradeServiceStub(self.channel)
            self.connected = True
            
            _logger.info(f"已连接到gRPC服务器 {server_address}")
            return True
        except Exception as e:
            _logger.error(f"连接到gRPC服务器失败: {e}")
            return False
    
    def test_connection(self):
        """测试连接"""
        if not self.connected:
            _logger.error("未建立连接")
            return False
        
        try:
            _logger.info("开始测试连接通信...")
            
            # 创建测试请求
            request = trade_service_pb2.TestRequest(
                message="连接测试",
                timestamp=int(time.time())
            )
            
            # 发送测试请求
            response = self.stub.TestConnection(request)
            
            _logger.info(f"连接通信测试成功: {response.message}")
            return True
        except Exception as e:
            _logger.error(f"连接通信测试失败: {e}")
            return False
    
    def buy_stock(self, stock_code, volume, price=0.0):
        """
        买入股票
        :param stock_code: 股票代码
        :param volume: 数量
        :param price: 价格
        """
        if not self.connected:
            _logger.error("未建立连接")
            return {"success": False, "error": "未建立连接"}
        
        try:
            _logger.info(f"发送买入请求: {stock_code} {volume}股，价格: {price}")
            
            # 创建买入请求
            request = trade_service_pb2.BuyRequest(
                stock_code=stock_code,
                volume=volume,
                price=price
            )
            
            # 发送买入请求
            response = self.stub.BuyStock(request)
            
            result = {
                "success": response.success,
                "async_seq": response.async_seq if response.success else None,
                "error": response.error if not response.success else None
            }
            
            if result["success"]:
                _logger.info(f"买入 {stock_code} {volume}股 成功，异步序列: {result['async_seq']}")
            else:
                _logger.error(f"买入 {stock_code} {volume}股 失败: {result['error']}")
            
            return result
        except Exception as e:
            _logger.error(f"发送买入请求时发生错误: {e}")
            return {"success": False, "error": str(e)}
    
    def sell_stock(self, stock_code, volume, price=0.0):
        """
        卖出股票
        :param stock_code: 股票代码
        :param volume: 数量
        :param price: 价格
        """
        if not self.connected:
            _logger.error("未建立连接")
            return {"success": False, "error": "未建立连接"}
        
        try:
            _logger.info(f"发送卖出请求: {stock_code} {volume}股，价格: {price}")
            
            # 创建卖出请求
            request = trade_service_pb2.SellRequest(
                stock_code=stock_code,
                volume=volume,
                price=price
            )
            
            # 发送卖出请求
            response = self.stub.SellStock(request)
            
            result = {
                "success": response.success,
                "async_seq": response.async_seq if response.success else None,
                "error": response.error if not response.success else None
            }
            
            if result["success"]:
                _logger.info(f"卖出 {stock_code} {volume}股 成功，异步序列: {result['async_seq']}")
            else:
                _logger.error(f"卖出 {stock_code} {volume}股 失败: {result['error']}")
            
            return result
        except Exception as e:
            _logger.error(f"发送卖出请求时发生错误: {e}")
            return {"success": False, "error": str(e)}
    
    def shutdown_server(self):
        """关闭服务器"""
        if not self.connected:
            _logger.error("未建立连接")
            return False
        
        try:
            _logger.info("发送关闭服务器请求...")
            
            # 创建关闭请求
            request = trade_service_pb2.ShutdownRequest()
            
            # 发送关闭请求
            response = self.stub.Shutdown(request)
            
            if response.success:
                _logger.info("服务器关闭请求发送成功")
            else:
                _logger.error(f"服务器关闭请求发送失败: {response.message}")
            
            return response.success
        except Exception as e:
            _logger.error(f"发送关闭服务器请求时发生错误: {e}")
            return False
    
    def close(self):
        """关闭连接"""
        if self.channel:
            self.channel.close()
            self.connected = False
            _logger.info("gRPC客户端连接已关闭")

def main():
    """主程序入口（用于测试）"""
    import argparse
    
    parser = argparse.ArgumentParser(description='gRPC交易客户端测试')
    parser.add_argument('--host', type=str, default='localhost',
                        help='服务器主机地址')
    parser.add_argument('--port', type=int, default=50051,
                        help='服务器端口号')
    
    args = parser.parse_args()
    
    # 创建客户端
    client = GRPCTradeClient(args.host, args.port)
    
    try:
        # 连接到服务器
        if not client.connect():
            _logger.error("无法连接到服务器")
            return
        
        # 测试连接
        if not client.test_connection():
            _logger.error("连接测试失败")
            return
        
        # 测试买入操作
        result = client.buy_stock("SH600000", 100, 12.5)
        _logger.info(f"买入测试结果: {result}")
        
        # 测试卖出操作
        result = client.sell_stock("SH600000", 100, 13.0)
        _logger.info(f"卖出测试结果: {result}")
        
    except KeyboardInterrupt:
        _logger.info("接收到中断信号")
    finally:
        client.close()

if __name__ == "__main__":
    main()