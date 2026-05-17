import os
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime
from unittest.mock import Mock
from unittest.mock import MagicMock

plt.rcParams['font.sans-serif'] = ['SimHei', 'Arial Unicode MS', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

def create_mock_grpc_client():
    """创建mock的gRPC客户端"""
    mock_grpc_client = Mock()
    mock_grpc_client.connect.return_value = True
    mock_grpc_client.test_connection.return_value = True
    mock_grpc_client.buy_stock.return_value = True
    mock_grpc_client.sell_stock.return_value = True
    return mock_grpc_client

def create_mock_config(stocks=['159545.SZ']):
    """创建mock配置对象"""
    mock_config = Mock()
    mock_config.stocks = stocks
    
    # 模拟策略配置
    mock_strategy_config = {
        'strategy': {
            'buy_on_dips': {
                'stocks': [
                    {
                        'code': stock,
                        'name': f'测试股票{stock}',
                        'threshold': 0.995,  # 0.2%的跌幅阈值
                        'order_volume': 100
                    } for stock in stocks
                ]
            }
        }
    }
    
    mock_config.config = mock_strategy_config
    return mock_config

def create_mock_time(year=2025, month=11, day=30, hour=10, minute=30):
    from datetime import datetime as dt

    mock_datetime = MagicMock()
    mock_datetime.now.return_value = dt(year, month, day, hour, minute, 0)
    mock_datetime.side_effect = lambda *args, **kw: dt(*args, **kw)
    return mock_datetime


def generate_sample_data():
    """生成单个数据点的测试数据"""
    test_data = {
        '159545.SZ': {
            'time': 1764390600000,
            'lastPrice': 1.484,
            'open': 1.484,
            'high': 1.487,
            'low': 1.478,
            'lastClose': 1.487,
            'amount': 2462200.0,
            'volume': 16626,
            'pvolume': 1662600,
            'stockStatus': 5,
            'openInt': 15,
            'transactionNum': 0,
            'lastSettlementPrice': 1.487,
            'settlementPrice': 0.0,
            'pe': 1.4721000000000002,
            'askPrice': [1.485, 1.486, 1.487, 1.489, 1.5],
            'bidPrice': [1.484, 1.482, 1.481, 1.48, 1.479],
            'askVol': [1235, 50, 2472, 100, 40],
            'bidVol': [30, 63, 134, 54575, 464],
            'volRatio': 0.0,
            'speed1Min': 0.0,
            'speed5Min': 0.0
        }
    }
    return test_data

def generate_day_simulation_data(base_time=1764390600000, stock_code='159545.SZ'):
    """生成一天的模拟数据用于完整测试"""
    simulation_data = []
    
    # 生成9:30-15:00的交易数据，每分钟一条
    for i in range(331):  # 331分钟 = 5小时31分钟
        timestamp = base_time + i * 60000  # 每分钟增加60000毫秒
        
        # 模拟价格变化
        # 基准价格1.487，制造一些波动，其中某些时段价格下跌以触发买入
        if 100 <= i <= 120:  # 在中间时段制造明显下跌
            price_multiplier = 0.99  # 下跌0.4%
        elif 200 <= i <= 220:
            price_multiplier = 0.995  # 下跌0.3%
        else:
            # 正常小幅波动
            price_multiplier = 1.0 + np.random.normal(0, 0.01)
        
        current_price = 1.487 * price_multiplier
        
        data_point = {
            stock_code: {
                'time': timestamp,
                'lastPrice': round(current_price, 3),
                'open': round(current_price, 3),
                'high': round(current_price * 1.001, 3),
                'low': round(current_price * 0.999, 3),
                'lastClose': 1.487,
                'amount': 2462200.0 + np.random.normal(0, 100000),
                'volume': 16626 + int(np.random.normal(0, 1000)),
                'pvolume': 1662600 + int(np.random.normal(0, 10000)),
                'stockStatus': 5,
                'openInt': 15,
                'transactionNum': 0,
                'lastSettlementPrice': 1.487,
                'settlementPrice': 0.0,
                'pe': 1.4721000000000002,
                'askPrice': [round(current_price + 0.001, 3), round(current_price + 0.002, 3), 
                            round(current_price + 0.003, 3), round(current_price + 0.004, 3), 
                            round(current_price + 0.005, 3)],
                'bidPrice': [round(current_price, 3), round(current_price - 0.001, 3), 
                            round(current_price - 0.002, 3), round(current_price - 0.003, 3), 
                            round(current_price - 0.004, 3)],
                'askVol': [1235, 50, 2472, 100, 40],
                'bidVol': [30, 63, 134, 54575, 464],
                'volRatio': 0.0,
                'speed1Min': 0.0,
                'speed5Min': 0.0
            }
        }
        
        simulation_data.append((timestamp, data_point))
    
    return simulation_data

def plot_trade_results(timestamps, prices, trade_events, filename='trade_simulation_result.png'):
    """绘制交易结果图表"""
    test_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'test_outputs')
    if not os.path.exists(test_dir):
        os.makedirs(test_dir)
    filename = os.path.join(test_dir, filename)

    fig, ax = plt.subplots(figsize=(15, 8))
    
    # 转换时间戳为datetime对象用于绘图
    datetime_points = [datetime.fromtimestamp(ts/1000) for ts in timestamps]
    
    # 绘制价格曲线
    ax.plot(datetime_points, prices, label='股票价格', color='blue', linewidth=1)
    
    # 标记交易点
    if trade_events:
        trade_times = [datetime.fromtimestamp(event['timestamp']/1000) for event in trade_events]
        trade_prices = [event['price'] for event in trade_events]
        ax.scatter(trade_times, trade_prices, color='red', s=100, label='买入信号', zorder=5)
        
        # 添加交易标注
        for event in trade_events:
            trade_time = datetime.fromtimestamp(event['timestamp']/1000)
            ax.annotate(f"买入\n{event['volume']}股", 
                       (trade_time, event['price']), 
                       xytext=(0, 20), 
                       textcoords='offset points',
                       ha='center',
                       fontsize=8,
                       bbox=dict(boxstyle='round,pad=0.3', facecolor='yellow', alpha=0.7),
                       arrowprops=dict(arrowstyle='->', connectionstyle='arc3,rad=0'))
    
    ax.set_title('股票价格走势与交易信号标记')
    ax.set_xlabel('时间')
    ax.set_ylabel('价格')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    # 格式化x轴时间显示
    fig.autofmt_xdate()
    
    plt.tight_layout()
    plt.savefig(filename, dpi=300, bbox_inches='tight')
    plt.close()
    
    return filename

def print_trade_statistics(simulation_data, trade_events):
    """打印交易统计信息"""
    print(f"模拟数据点数量: {len(simulation_data)}")
    print(f"交易信号数量: {len(trade_events)}")
    if trade_events:
        avg_trade_price = sum([event['price'] for event in trade_events]) / len(trade_events)
        print(f"平均交易价格: {avg_trade_price:.3f}")