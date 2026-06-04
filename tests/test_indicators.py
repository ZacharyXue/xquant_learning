import pytest
from engine.indicators import calc_rsi, calc_ma, calc_ema, calc_bias, calc_open_change, round_to_lot


class TestRSI:
    def test_rsi_basic(self):
        prices = [10.0, 10.5, 10.3, 10.8, 10.6, 10.9, 11.0, 10.7,
                  11.2, 11.5, 11.3, 11.8, 12.0, 11.9, 12.2]
        rsi = calc_rsi(prices, period=14)
        assert 0 <= rsi <= 100

    def test_rsi_insufficient_data(self):
        assert calc_rsi([10.0, 10.5], period=14) == 50.0

    def test_rsi_all_up(self):
        prices = [float(i) for i in range(20)]
        assert calc_rsi(prices, 14) == 100.0

    def test_rsi_all_down(self):
        prices = [float(20 - i) for i in range(20)]
        assert calc_rsi(prices, 14) == 0.0


class TestMA:
    def test_ma_basic(self):
        assert calc_ma([10.0, 11.0, 12.0, 13.0, 14.0], 3) == 13.0

    def test_ma_insufficient(self):
        assert calc_ma([10.0, 11.0], 5) == 10.5


class TestBias:
    def test_bias_positive(self):
        assert calc_bias(11.0, 10.0) == 0.1

    def test_bias_negative(self):
        assert calc_bias(9.0, 10.0) == -0.1

    def test_bias_zero_ma(self):
        assert calc_bias(10.0, 0.0) == 0.0


class TestOpenChange:
    def test_positive(self):
        assert calc_open_change(10.1, 10.0) == pytest.approx(0.01)
    def test_zero_close(self):
        assert calc_open_change(10.0, 0.0) == 0.0


class TestRoundToLot:
    def test_round(self):
        assert round_to_lot(550, 100) == 500
        assert round_to_lot(0, 100) == 0
        assert round_to_lot(99, 100) == 0
