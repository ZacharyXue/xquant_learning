from trade.fees import FeeCalculator


class TestFeeCalculator:
    def _calc(self, **kw):
        defaults = dict(commission_rate=0.00025, stamp_tax_rate=0.001,
                        transfer_fee_rate=0.00002, min_commission=5.0, slippage_rate=0.001)
        defaults.update(kw)
        return FeeCalculator(**defaults)

    def test_buy_cost(self):
        calc = self._calc()
        c = calc.calc_trade_cost(price=10.0, volume=1000, side="buy")
        # amount=10000; commission=max(2.5,5)=5; stamp=0; transfer=0.2; slippage=10
        assert c.commission == 5.0
        assert c.stamp_tax == 0.0
        assert c.transfer_fee == 0.2
        assert c.slippage_cost == 10.0
        assert c.total == 15.2
        assert c.net_amount == 10015.2  # buy pays more

    def test_sell_cost(self):
        calc = self._calc()
        c = calc.calc_trade_cost(price=10.0, volume=1000, side="sell")
        assert c.stamp_tax == 10.0
        assert c.total == 25.2
        assert c.net_amount == 9974.8  # sell receives less

    def test_large_commission(self):
        calc = self._calc(slippage_rate=0.0)
        c = calc.calc_trade_cost(price=10.0, volume=50000, side="buy")
        assert c.commission == 125.0  # 500000 * 0.00025

    def test_slippage_price(self):
        calc = self._calc()
        assert calc.calc_slippage_price(10.0, "buy") == 10.01
        assert calc.calc_slippage_price(10.0, "sell") == 9.99
