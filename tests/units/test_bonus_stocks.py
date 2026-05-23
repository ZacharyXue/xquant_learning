"""
红利ETF定投策略测试

测试策略的各项功能和指标计算
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from src.strategies.strategy_utils import (
    is_trading_time,
    is_investment_day,
    should_skip_log,
    calculate_rsi,
    calculate_ma,
    calculate_bias_rate,
    calculate_open_change_ratio,
    round_to_lot_size,
)
from src.strategies.bonus_stocks import (
    BonusStocksPolicy,
    BonusStocksConfig,
    ETFConfig,
    StrategyParams,
    IndicatorResult,
)


class TestStrategyUtils:
    """策略工具函数测试"""

    def test_is_trading_time(self):
        """测试交易时间判断"""
        # 交易时间内
        assert is_trading_time(datetime(2025, 1, 15, 10, 30)) == True
        assert is_trading_time(datetime(2025, 1, 15, 14, 54)) == True

        # 开盘前
        assert is_trading_time(datetime(2025, 1, 15, 9, 29)) == False
        assert is_trading_time(datetime(2025, 1, 15, 8, 0)) == False

        # 收盘后
        assert is_trading_time(datetime(2025, 1, 15, 14, 55)) == False
        assert is_trading_time(datetime(2025, 1, 15, 15, 0)) == False

    def test_is_investment_day(self):
        """测试定投日判断"""
        # 周三 (weekday = 2)
        assert is_investment_day(datetime(2025, 1, 15), ["Wed"]) == True
        assert is_investment_day(datetime(2025, 1, 15), ["Mon", "Wed"]) == True

        # 周五 (weekday = 4)
        assert is_investment_day(datetime(2025, 1, 17), ["Fri"]) == True

        # 周一 (weekday = 0) - 不在周三周五列表中
        assert is_investment_day(datetime(2025, 1, 13), ["Wed", "Fri"]) == False

    def test_should_skip_log(self):
        """测试日志跳过判断"""
        # 非交易时间应跳过
        assert should_skip_log(datetime(2025, 1, 15, 8, 0)) == True

        # 交易时间内但非定投日
        assert should_skip_log(
            datetime(2025, 1, 13, 10, 30),  # 周一
            ["Wed"]
        ) == True

        # 交易时间内且是定投日
        assert should_skip_log(
            datetime(2025, 1, 15, 10, 30),  # 周三
            ["Wed"]
        ) == False

    def test_calculate_rsi(self):
        """测试RSI计算"""
        # 持续上涨
        rising_prices = [100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114]
        rsi = calculate_rsi(rising_prices)
        assert rsi is not None
        assert rsi > 70  # 超买状态

        # 持续下跌
        falling_prices = [114, 113, 112, 111, 110, 109, 108, 107, 106, 105, 104, 103, 102, 101, 100]
        rsi = calculate_rsi(falling_prices)
        assert rsi is not None
        assert rsi < 30  # 超卖状态

        # 平稳
        stable_prices = [100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100]
        rsi = calculate_rsi(stable_prices)
        assert rsi is not None
        assert 40 < rsi < 60  # 中性状态

        # 数据不足
        short_prices = [100, 101, 102]
        rsi = calculate_rsi(short_prices)
        assert rsi is None

    def test_calculate_ma(self):
        """测试移动平均线计算"""
        prices = [100, 101, 102, 103, 104, 105, 106, 107, 108, 109]

        # 5日均线
        ma5 = calculate_ma(prices, 5)
        assert ma5 == 107.0  # (105+106+107+108+109)/5

        # 10日均线
        ma10 = calculate_ma(prices, 10)
        assert ma10 == 104.5  # (100+101+...+109)/10

        # 数据不足
        ma20 = calculate_ma(prices, 20)
        assert ma20 is None

    def test_calculate_bias_rate(self):
        """测试乖离率计算"""
        # 偏离10%
        bias = calculate_bias_rate(110, 100)
        assert abs(bias - 0.1) < 0.0001

        # 偏离-10%
        bias = calculate_bias_rate(90, 100)
        assert abs(bias - (-0.1)) < 0.0001

        # 零除情况
        bias = calculate_bias_rate(100, 0)
        assert bias == 0.0

    def test_calculate_open_change_ratio(self):
        """测试开盘涨幅计算"""
        # 上涨1%
        change = calculate_open_change_ratio(101, 100)
        assert abs(change - 0.01) < 0.0001

        # 下跌1%
        change = calculate_open_change_ratio(99, 100)
        assert abs(change - (-0.01)) < 0.0001

        # 零除情况
        change = calculate_open_change_ratio(100, 0)
        assert change == 0.0

    def test_round_to_lot_size(self):
        """测试交易单位取整"""
        # 正常情况
        assert round_to_lot_size(150, 100) == 100
        assert round_to_lot_size(250, 100) == 200
        assert round_to_lot_size(100, 100) == 100

        # 边界情况
        assert round_to_lot_size(0, 100) == 0
        assert round_to_lot_size(-100, 100) == 0


class TestBonusStocksPolicy:
    """红利ETF定投策略测试"""

    @pytest.fixture
    def mock_config(self, tmp_path):
        """创建测试配置文件"""
        config_data = {
            "name": "测试红利ETF定投策略",
            "investment": {
                "days": ["Wed"],
                "base_volume": 500,
                "lot_size": 100
            },
            "etfs": [
                {"code": "000001.SH", "name": "测试ETF1"},
                {"code": "000002.SH", "name": "测试ETF2"}
            ],
            "params": {
                "rsi": {
                    "period": 14,
                    "overbought": 70,
                    "oversold": 30,
                    "buy_additional": 100
                },
                "bias": {
                    "ma_period": 250,
                    "upper_threshold": 0.1,
                    "lower_threshold": -0.1,
                    "buy_additional": 100
                },
                "open_change": {
                    "threshold": 0.01
                }
            }
        }
        config_file = tmp_path / "test_config.json"
        import json
        config_file.write_text(json.dumps(config_data, ensure_ascii=False), encoding='utf-8')
        return str(config_file)

    def test_config_loading(self, mock_config):
        """测试配置加载"""
        config = BonusStocksConfig(mock_config)

        assert config.investment_days == ["Wed"]
        assert config.base_volume == 500
        assert config.lot_size == 100
        assert len(config.etfs) == 2
        assert config.etfs[0].code == "000001.SH"

    def test_policy_initialization(self, mock_config):
        """测试策略初始化"""
        policy = BonusStocksPolicy(mock_config)

        assert len(policy.config.etfs) == 2
        assert policy.params.rsi_overbought == 70
        assert policy.params.rsi_oversold == 30

    def test_price_update(self, mock_config):
        """测试价格更新"""
        policy = BonusStocksPolicy(mock_config)

        policy.update_price("000001.SH", 1.0)
        policy.update_price("000001.SH", 1.01)

        assert len(policy.price_history["000001.SH"]) == 2
        assert policy.price_history["000001.SH"][-1] == 1.01

    def test_calculate_indicators_rsi_overbought(self, mock_config):
        """测试RSI超买时不应买入"""
        policy = BonusStocksPolicy(mock_config)

        # 模拟持续上涨的价格（RSI > 70）
        prices = [100 + i for i in range(260)]
        policy.price_history["000001.SH"] = prices

        data = {
            "000001.SH": {
                "lastPrice": 359,
                "open": 358,
                "lastClose": 357
            }
        }

        result = policy.calculate_indicators("000001.SH", data)

        assert result.should_buy == False
        assert "RSI" in result.skip_reason or result.final_volume == 0

    def test_calculate_indicators_rsi_oversold(self, mock_config):
        """测试RSI超卖时应增加买入"""
        policy = BonusStocksPolicy(mock_config)

        # 模拟持续下跌的价格（RSI < 30）
        prices = [400 - i for i in range(260)]
        policy.price_history["000001.SH"] = prices

        data = {
            "000001.SH": {
                "lastPrice": 141,
                "open": 142,
                "lastClose": 143
            }
        }

        result = policy.calculate_indicators("000001.SH", data)

        assert result.rsi is not None
        assert result.rsi < 30
        assert result.additional_volume >= policy.params.rsi_additional

    def test_calculate_indicators_bias_over_threshold(self, mock_config):
        """测试乖离率超过阈值时不应买入"""
        policy = BonusStocksPolicy(mock_config)

        # 模拟足够的价格数据
        prices = [100] * 260
        policy.price_history["000001.SH"] = prices

        # 当前价格比均线高15%（超过10%阈值）
        data = {
            "000001.SH": {
                "lastPrice": 115,
                "open": 114,
                "lastClose": 100
            }
        }

        result = policy.calculate_indicators("000001.SH", data)

        assert result.bias is not None
        assert result.bias > policy.params.bias_upper

    def test_should_invest_today(self, mock_config):
        """测试定投日判断"""
        policy = BonusStocksPolicy(mock_config)

        # 周三 (2025-01-15 是周三)
        wednesday = datetime(2025, 1, 15, 10, 30)
        assert policy.should_invest_today(wednesday) == True

        # 周一 (2025-01-13 是周一)
        monday = datetime(2025, 1, 13, 10, 30)
        assert policy.should_invest_today(monday) == False

    def test_evaluate_and_select(self, mock_config):
        """测试ETF评估和选择"""
        policy = BonusStocksPolicy(mock_config)

        # ETF1: 价格稳定，RSI=50（中性），无乖离率触发
        policy.price_history["000001.SH"] = [100] * 260
        # ETF2: 持续下跌，RSI < 30（超卖）且乖离率 < -10%（超卖）
        # 应该获得 RSI 100股 + 乖离率 100股 = 700股
        policy.price_history["000002.SH"] = [100 - i * 0.1 for i in range(260)]

        data = {
            "000001.SH": {"lastPrice": 100, "open": 100, "lastClose": 100},
            "000002.SH": {"lastPrice": 74, "open": 75, "lastClose": 75}
        }

        best_result, all_results = policy.evaluate_and_select(data)

        # ETF2 应该获得更多份额：基础500 + RSI 100 + 乖离率 100 = 700
        # ETF1: 基础500股
        assert best_result.etf_code == "000002.SH"
        assert best_result.final_volume == 700
        assert all_results["000001.SH"].final_volume == 500

    def test_round_to_lot_size_in_result(self, mock_config):
        """测试最终股数为100的整数倍"""
        policy = BonusStocksPolicy(mock_config)

        # 模拟价格数据
        prices = [100] * 260
        policy.price_history["000001.SH"] = prices

        data = {
            "000001.SH": {
                "lastPrice": 100,
                "open": 100,
                "lastClose": 100
            }
        }

        result = policy.calculate_indicators("000001.SH", data)

        # 最终股数应该是100的整数倍
        assert result.final_volume % 100 == 0

    def test_get_trade_decision_not_investment_day(self, mock_config):
        """测试非定投日不交易"""
        policy = BonusStocksPolicy(mock_config)

        # 设置定投日为周一，模拟周三 (非定投日)
        policy.config.investment_days = ["Mon"]

        data = {"000001.SH": {"lastPrice": 100}}

        # 模拟周三交易时间 (非定投日 -> 应返回 None)
        with patch('src.strategies.bonus_stocks.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2025, 1, 15, 10, 30)  # 周三
            mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)

            decision = policy(data)

            assert decision is None

    def test_get_trade_decision_no_data(self, mock_config):
        """测试数据不足时的交易行为"""
        policy = BonusStocksPolicy(mock_config)

        # 直接设置定投日
        policy.config.investment_days = ["Wed"]

        # 手动测试指标计算（数据不足的情况）
        data = {"000001.SH": {"lastPrice": 100, "open": 100, "lastClose": 100}}
        result = policy.calculate_indicators("000001.SH", data)

        # 当RSI数据不足时，仍应买入基础份额
        assert result.should_buy == True
        assert result.final_volume == 500  # 基础份额


class TestStrategyTiming:
    """策略择时测试"""

    @pytest.fixture
    def mock_config(self, tmp_path):
        """创建测试配置"""
        config_data = {
            "investment": {
                "days": ["Wed", "Fri"],
                "base_volume": 500,
                "lot_size": 100
            },
            "etfs": [{"code": "000001.SH", "name": "测试ETF"}],
            "params": {
                "rsi": {"period": 14, "overbought": 70, "oversold": 30, "buy_additional": 100},
                "bias": {"ma_period": 250, "upper_threshold": 0.1, "lower_threshold": -0.1, "buy_additional": 100},
                "open_change": {"threshold": 0.01}
            }
        }
        config_file = tmp_path / "timing_config.json"
        import json
        config_file.write_text(json.dumps(config_data, ensure_ascii=False), encoding='utf-8')
        return str(config_file)

    def test_different_investment_days(self, mock_config):
        """测试不同定投日"""
        policy = BonusStocksPolicy(mock_config)

        # 周三
        assert policy.should_invest_today(datetime(2025, 1, 15, 10, 0)) == True
        # 周五
        assert policy.should_invest_today(datetime(2025, 1, 17, 10, 0)) == True
        # 周一
        assert policy.should_invest_today(datetime(2025, 1, 13, 10, 0)) == False
        # 周四
        assert policy.should_invest_today(datetime(2025, 1, 16, 10, 0)) == False

    def test_indicator_threshold_scenarios(self, mock_config):
        """测试各种指标阈值场景"""
        policy = BonusStocksPolicy(mock_config)

        # 场景1: RSI刚好在阈值附近
        prices_70 = [100 + i * 0.1 for i in range(260)]
        policy.price_history["000001.SH"] = prices_70
        rsi_70 = calculate_rsi(prices_70, 14)
        assert rsi_70 is not None

        # 场景2: RSI刚好低于超卖阈值
        prices_30 = [100 - i * 0.1 for i in range(260)]
        policy.price_history["000001.SH"] = prices_30
        rsi_30 = calculate_rsi(prices_30, 14)
        assert rsi_30 is not None
        assert rsi_30 < 30


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
