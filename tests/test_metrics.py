import numpy as np
import pytest
from backtest.metrics import MetricsCalculator


def test_profitable():
    calc = MetricsCalculator()
    equity = list(np.linspace(100000, 110000, 252))
    r = calc.calculate(equity, 100000)
    assert r["return_rate"] == pytest.approx(0.1, abs=0.02)
    assert r["max_drawdown"] == 0.0
    assert r["sharpe_ratio"] > 0


def test_empty():
    r = MetricsCalculator().calculate([], 100000)
    assert r["return_rate"] == 0.0
