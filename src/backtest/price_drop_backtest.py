import pandas as pd
import numpy as np
import yaml
import os
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
from utils.logger import get_logger

_logger = get_logger("backtest")

class PriceDropBacktest:
    def __init__(self, config_path="config/stock_config.yaml"):
        """
        初始化回测系统
        
        参数:
        config_path: 配置文件路径
        """
        self.config_path = config_path
        self.config = self._load_config()
        
        # 初始化回测数据
        self.stock_data = {}
        self.benchmark_data = None
        
        # 初始化账户状态
        self.initial_capital = self.config.get('trading', {}).get('initial_capital', 1000000)
        self.capital = self.initial_capital
        self.positions = {}
        self.base_prices = {}
        
        # 交易记录
        self.trade_logs = []
        
        # 回测结果
        self.backtest_results = None
        
        _logger.info("回测系统初始化完成")
    
    def _load_config(self):
        """
        加载配置文件
        """
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            _logger.info(f"成功加载配置文件: {self.config_path}")
            return config
        except Exception as e:
            _logger.error(f"加载配置文件失败: {str(e)}")
            return {}
    
    def load_historical_data(self):
        """
        加载历史数据
        注：这里使用模拟数据，实际应用中应从QMT获取历史数据
        """
        from src.common.trader import Trader
        from src.common.stocks import get_stock_price_manager
        
        # 初始化交易器和价格管理器
        trader = Trader()
        price_manager = get_stock_price_manager(trader=trader)
        
        # 获取配置的回测日期范围
        start_date = self.config.get('backtest', {}).get('start_date', '20240101')
        end_date = self.config.get('backtest', {}).get('end_date', '20240630')
        
        # 加载每只股票的历史数据
        stocks = self.config.get('stocks', {})
        for stock_code in stocks:
            _logger.info(f"加载股票 {stock_code} 的历史数据")
            
            # 获取日线数据
            klines = price_manager.get_history_klines(
                stock_code=stock_code,
                period='1d',
                start_time=f"{start_date}000000",
                end_time=f"{end_date}235959"
            )
            
            if klines:
                # 转换为DataFrame
                df = pd.DataFrame(klines)
                df['time'] = pd.to_datetime(df['time'])
                df.set_index('time', inplace=True)
                self.stock_data[stock_code] = df
                
                # 初始化基准价格为第一个交易日的收盘价
                if not self.stock_data[stock_code].empty:
                    self.base_prices[stock_code] = self.stock_data[stock_code].iloc[0]['close']
            else:
                _logger.warn(f"无法获取股票 {stock_code} 的历史数据，使用模拟数据")
                # 生成模拟数据
                self.stock_data[stock_code] = self._generate_mock_data(start_date, end_date, stock_code)
                self.base_prices[stock_code] = self.stock_data[stock_code].iloc[0]['close']
        
        # 加载基准指数数据
        benchmark = self.config.get('backtest', {}).get('benchmark', '000001.SH')
        _logger.info(f"加载基准指数 {benchmark} 的历史数据")
        
        # 实际应用中应从QMT获取基准指数数据
        # 这里使用模拟数据
        self.benchmark_data = self._generate_mock_data(start_date, end_date, benchmark)
    
    def _generate_mock_data(self, start_date, end_date, symbol):
        """
        生成模拟的股票历史数据
        """
        # 转换日期格式
        start = datetime.strptime(start_date, '%Y%m%d')
        end = datetime.strptime(end_date, '%Y%m%d')
        
        # 生成日期范围
        date_range = pd.date_range(start=start, end=end, freq='B')  # B表示工作日
        
        # 随机种子，确保同一股票的模拟数据相同
        np.random.seed(hash(symbol) % 1000)
        
        # 生成模拟数据
        base_price = 10 + np.random.rand() * 90  # 随机初始价格
        
        # 生成价格序列 (随机游走)
        returns = np.random.normal(0, 0.02, len(date_range))
        prices = base_price * np.exp(np.cumsum(returns))
        
        # 创建DataFrame
        df = pd.DataFrame({
            'open': prices,
            'close': prices * (1 + np.random.normal(0, 0.01, len(date_range))),
            'high': prices * (1 + np.random.uniform(0, 0.03, len(date_range))),
            'low': prices * (1 - np.random.uniform(0, 0.03, len(date_range))),
            'volume': np.random.randint(100000, 10000000, len(date_range))
        }, index=date_range)
        
        # 确保high >= open/close，low <= open/close
        df['high'] = df[['high', 'open', 'close']].max(axis=1)
        df['low'] = df[['low', 'open', 'close']].min(axis=1)
        
        return df
    
    def run_backtest(self):
        """
        运行回测
        """
        _logger.info("开始回测")
        
        # 确保数据已加载
        if not self.stock_data:
            self.load_historical_data()
        
        # 获取所有交易日
        all_dates = set()
        for stock_code, df in self.stock_data.items():
            all_dates.update(df.index)
        all_dates = sorted(list(all_dates))
        
        # 初始化结果DataFrame
        results = []
        
        # 遍历每个交易日
        for date in all_dates:
            daily_results = {'date': date}
            
            # 检查每只股票
            stocks = self.config.get('stocks', {})
            for stock_code, drop_threshold in stocks.items():
                # 检查该股票当天是否有交易数据
                if stock_code not in self.stock_data or date not in self.stock_data[stock_code].index:
                    continue
                
                # 获取当天的价格数据
                daily_data = self.stock_data[stock_code].loc[date]
                close_price = daily_data['close']
                
                # 更新持仓价值
                if stock_code in self.positions and self.positions[stock_code] > 0:
                    daily_results[f'{stock_code}_value'] = self.positions[stock_code] * close_price
                else:
                    daily_results[f'{stock_code}_value'] = 0
                
                # 检查是否需要买入
                if self._check_buy_condition(stock_code, close_price, drop_threshold):
                    self._backtest_buy(stock_code, close_price, date, drop_threshold)
            
            # 计算总资产
            positions_value = sum(daily_results.get(f'{stock_code}_value', 0) for stock_code in stocks)
            daily_results['cash'] = self.capital
            daily_results['total_assets'] = self.capital + positions_value
            daily_results['return_rate'] = (daily_results['total_assets'] / self.initial_capital - 1) * 100
            
            # 记录基准收益率
            if self.benchmark_data is not None and date in self.benchmark_data.index:
                daily_results['benchmark_close'] = self.benchmark_data.loc[date]['close']
                daily_results['benchmark_return'] = (
                    daily_results['benchmark_close'] / self.benchmark_data.iloc[0]['close'] - 1
                ) * 100
            
            results.append(daily_results)
        
        # 转换为DataFrame
        self.backtest_results = pd.DataFrame(results)
        self.backtest_results.set_index('date', inplace=True)
        
        _logger.info("回测完成")
        self._print_backtest_summary()
        
        return self.backtest_results
    
    def _check_buy_condition(self, stock_code, current_price, drop_threshold):
        """
        检查买入条件
        """
        # 检查基准价格是否已设置
        if stock_code not in self.base_prices:
            self.base_prices[stock_code] = current_price
            return False
        
        # 计算价格变化比例
        price_change_ratio = (current_price - self.base_prices[stock_code]) / self.base_prices[stock_code]
        
        # 检查是否下跌超过阈值
        if price_change_ratio <= -drop_threshold:
            return True
        
        return False
    
    def _backtest_buy(self, stock_code, price, date, drop_threshold):
        """
        回测中的买入操作
        """
        max_position = self.config.get('trading', {}).get('max_position_per_stock', 10000)
        order_volume = self.config.get('trading', {}).get('order_volume', 100)
        
        # 计算需要的资金
        required_funds = price * order_volume
        
        # 检查是否有足够资金
        if self.capital < required_funds:
            _logger.debug(f"[{date}] 资金不足，无法买入 {stock_code}")
            return
        
        # 执行买入
        self.capital -= required_funds
        if stock_code not in self.positions:
            self.positions[stock_code] = 0
        self.positions[stock_code] += order_volume
        
        # 重置基准价格
        self.base_prices[stock_code] = price
        
        # 记录交易
        self.trade_logs.append({
            'date': date,
            'stock_code': stock_code,
            'action': 'BUY',
            'price': price,
            'volume': order_volume,
            'amount': required_funds,
            'reason': f"下跌{drop_threshold*100}%"
        })
        
        _logger.info(f"[{date}] 买入 {stock_code}，价格: {price}, 数量: {order_volume}, 金额: {required_funds}")
    
    def _print_backtest_summary(self):
        """
        打印回测总结
        """
        if self.backtest_results is None or self.backtest_results.empty:
            _logger.warning("没有回测结果可以展示")
            return
        
        # 计算统计指标
        start_value = self.initial_capital
        end_value = self.backtest_results.iloc[-1]['total_assets']
        total_return = (end_value - start_value) / start_value * 100
        
        # 计算年化收益率
        days = (self.backtest_results.index[-1] - self.backtest_results.index[0]).days
        annual_return = ((1 + total_return/100) ** (365/days) - 1) * 100 if days > 0 else 0
        
        # 计算最大回撤
        cumulative = self.backtest_results['total_assets'] / start_value
        running_max = cumulative.cummax()
        drawdown = (cumulative - running_max) / running_max * 100
        max_drawdown = drawdown.min()
        
        # 计算夏普比率 (假设无风险利率为3%)
        daily_returns = self.backtest_results['total_assets'].pct_change().dropna()
        sharpe_ratio = (daily_returns.mean() - 0.03/252) / daily_returns.std() * np.sqrt(252) if daily_returns.std() > 0 else 0
        
        # 打印总结
        summary = f"""
        ============== 回测总结 ==============
        初始资金: {start_value:.2f}
        最终资金: {end_value:.2f}
        总收益率: {total_return:.2f}%
        年化收益率: {annual_return:.2f}%
        最大回撤: {max_drawdown:.2f}%
        夏普比率: {sharpe_ratio:.2f}
        交易次数: {len(self.trade_logs)}
        回测周期: {self.backtest_results.index[0].strftime('%Y-%m-%d')} 至 {self.backtest_results.index[-1].strftime('%Y-%m-%d')}
        =====================================
        """
        
        _logger.info(summary)
        print(summary)
    
    # 在文件顶部导入matplotlib的位置，添加以下代码
    import matplotlib.pyplot as plt
    # 设置matplotlib支持中文显示
    plt.rcParams['font.sans-serif'] = ['SimHei']  # 用黑体显示中文
    plt.rcParams['axes.unicode_minus'] = False  # 正常显示负号
    
    # 修改plot_results方法
    def plot_results(self):
        """
        绘制回测结果图表
        """
        # 设置matplotlib支持中文显示（方法内再次设置确保生效）
        plt.rcParams['font.sans-serif'] = ['SimHei']
        plt.rcParams['axes.unicode_minus'] = False
        
        if self.backtest_results is None or self.backtest_results.empty:
            _logger.warning("没有回测结果可以绘制")
            return
        
        plt.figure(figsize=(15, 10))
        
        # 绘制收益率曲线
        plt.subplot(2, 1, 1)
        plt.plot(self.backtest_results.index, self.backtest_results['return_rate'], label='策略收益率(%)')
        if 'benchmark_return' in self.backtest_results.columns:
            plt.plot(self.backtest_results.index, self.backtest_results['benchmark_return'], label='基准收益率(%)')
        plt.title('收益率对比')
        plt.legend()
        plt.grid(True)
        
        # 绘制资产曲线
        plt.subplot(2, 1, 2)
        plt.plot(self.backtest_results.index, self.backtest_results['total_assets'], label='总资产')
        plt.plot(self.backtest_results.index, self.backtest_results['cash'], label='现金')
        
        # 绘制各股票持仓价值
        stocks = self.config.get('stocks', {})
        for stock_code in stocks:
            if f'{stock_code}_value' in self.backtest_results.columns:
                plt.plot(self.backtest_results.index, self.backtest_results[f'{stock_code}_value'], label=f'{stock_code}持仓')
        
        plt.title('资产配置变化')
        plt.legend()
        plt.grid(True)
        
        plt.tight_layout()
        plt.savefig('backtest_results.png')
        plt.show()
        
        _logger.info("回测结果图表已保存为 backtest_results.png")

if __name__ == "__main__":
    backtest = PriceDropBacktest()
    results = backtest.run_backtest()
    backtest.plot_results()