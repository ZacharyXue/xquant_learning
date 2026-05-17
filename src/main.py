import argparse
from monitor.stock_monitor import StockMonitor
from backtest.price_drop_backtest import PriceDropBacktest
from utils.logger import get_logger

_logger = get_logger("main")

import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def main():
    """
    主程序入口
    """
    parser = argparse.ArgumentParser(description='股票价格监控和回测系统')
    parser.add_argument('--mode', type=str, choices=['monitor', 'backtest'], default='monitor',
                        help='运行模式: monitor(监控模式) 或 backtest(回测模式)')
    parser.add_argument('--config', type=str, default='config/stock_config.yaml',
                        help='配置文件路径')
    
    args = parser.parse_args()
    
    _logger.info(f"启动模式: {args.mode}")
    
    if args.mode == 'monitor':
        # 启动监控模式
        monitor = StockMonitor(config_path=args.config)
        monitor.start_monitoring()
    elif args.mode == 'backtest':
        # 启动回测模式
        backtest = PriceDropBacktest(config_path=args.config)
        results = backtest.run_backtest()
        backtest.plot_results()

if __name__ == "__main__":
    main()