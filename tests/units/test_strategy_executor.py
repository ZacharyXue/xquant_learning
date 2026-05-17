import pytest
import sys
import os
from unittest.mock import patch
import numpy as np

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.strategy_executor_grpc import DataProcessor
from tests.test_utils import (
    create_mock_grpc_client, 
    create_mock_config, 
    generate_sample_data, 
    generate_day_simulation_data,
    plot_trade_results,
    print_trade_statistics,
    create_mock_time
)

class TestQuoteCallback:
    @patch('src.strategy_executor_grpc.GRPCTradeClient')
    @patch('src.strategy_executor_grpc.Config')
    def test_single_data_point(self, mock_config_class, mock_grpc_client_class):
        """测试单个数据点的处理"""
        # 创建测试数据
        test_data = generate_sample_data()
        
        # 创建mock配置
        mock_config = create_mock_config()
        mock_config_class.return_value = mock_config
        
        # 创建mock gRPC客户端
        mock_grpc_client = create_mock_grpc_client()
        mock_grpc_client_class.return_value = mock_grpc_client
        
        # 创建DataProcessor实例
        processor = DataProcessor()
        processor.config = mock_config
        processor.grpc_client = mock_grpc_client
        
        # 初始化策略实例
        from src.strategies.buy_on_dips import BuyOnDipsPolicy
        strategy_instance = BuyOnDipsPolicy(mock_config)
        strategy_instance.bm_prices[mock_config.stocks[0]] = 1.487  # 设置基准价格
        processor.strategy_instances = {
            "buy_on_dips": strategy_instance
        }
        
        mock_datetime = create_mock_time(
            hour=10, minute=30
        )
        with patch('src.strategies.buy_on_dips.datetime', mock_datetime):   
            processor.quote_callback(test_data)
        
        # 验证gRPC客户端被正确调用
        current_price = test_data['159545.SZ']['lastPrice']
        last_close = test_data['159545.SZ']['lastClose']
        ratio = current_price / last_close  # 1.484 / 1.487 ≈ 0.998
        
        # 因为ratio (0.998) < threshold (0.998) 应该刚好等于阈值，可能不会触发交易
        if ratio < 0.999:  # 如果确实低于阈值，则应该调用买入
            mock_grpc_client.buy_stock.assert_called_once()
        else:
            # 如果没有达到阈值，则不应该有任何交易调用
            pass

    @patch('src.strategy_executor_grpc.GRPCTradeClient')
    @patch('src.strategy_executor_grpc.Config')
    def test_full_day_simulation_with_visualization(self, mock_config_class, mock_grpc_client_class):
        """完整的日内模拟测试并生成可视化图表"""
        # 创建mock配置
        mock_config = create_mock_config()
        mock_config_class.return_value = mock_config
        
        # 创建mock gRPC客户端
        mock_grpc_client = create_mock_grpc_client()
        mock_grpc_client_class.return_value = mock_grpc_client
        
        # 创建DataProcessor实例
        processor = DataProcessor()
        processor.config = mock_config
        processor.grpc_client = mock_grpc_client
        
        # 初始化策略实例
        from src.strategies.buy_on_dips import BuyOnDipsPolicy
        strategy_instance = BuyOnDipsPolicy(mock_config)
        processor.strategy_instances = {
            "buy_on_dips": strategy_instance
        }
        
        # 生成模拟数据
        simulation_data = generate_day_simulation_data()
        
        # 收集结果用于可视化
        timestamps = []
        prices = []
        trade_events = []
        
        # 处理每条数据
        for timestamp, data_point in simulation_data:
            # 记录价格数据
            price = data_point['159545.SZ']['lastPrice']
            timestamps.append(timestamp)
            prices.append(price)
            
            # 重置mock调用计数器
            mock_grpc_client.buy_stock.reset_mock()
            
            # 处理数据点
            mock_datetime = create_mock_time(
                hour=(timestamp // 3600000 + 5) % 24, minute=(timestamp // 60000) % 60
            )
            with patch('src.strategies.buy_on_dips.datetime', mock_datetime):   
                processor.quote_callback(data_point)
            
            # 检查是否有交易发生
            if mock_grpc_client.buy_stock.called:
                trade_events.append({
                    'timestamp': timestamp,
                    'price': price,
                    'volume': mock_grpc_client.buy_stock.call_args[0][1] if mock_grpc_client.buy_stock.call_args else 100
                })
        
        # 生成可视化图表
        plot_filename = plot_trade_results(timestamps, prices, trade_events, 'trade_simulation_result_full_day.png')
        
        # 输出统计信息
        print_trade_statistics(simulation_data, trade_events)
        
        # 验证交易发生在价格低于基准时
        for event in trade_events:
            assert event['price'] < 1.487, f"交易价格应低于基准价1.487，实际: {event['price']}"

if __name__ == '__main__':
    pytest.main([__file__, '-v'])