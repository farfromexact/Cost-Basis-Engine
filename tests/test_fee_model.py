from core.fee_model import FeeConfig, FeeModel
from core.models import Side


def test_minimum_commission_applies_to_buy_and_sell() -> None:
    model = FeeModel(FeeConfig(min_commission=5.0, stamp_tax_rate=0.001))

    buy = model.calculate(Side.BUY, price=10.0, qty=100)
    sell = model.calculate(Side.SELL, price=10.0, qty=100)

    assert buy.commission == 5.0
    assert sell.commission == 5.0


def test_stamp_tax_only_applies_to_sell_side() -> None:
    model = FeeModel(FeeConfig(stamp_tax_rate=0.001))

    buy = model.calculate(Side.BUY, price=10.0, qty=1000)
    sell = model.calculate(Side.SELL, price=10.0, qty=1000)

    assert buy.stamp_tax == 0.0
    assert sell.stamp_tax == 10.0


def test_slippage_is_directional_and_costly() -> None:
    model = FeeModel(FeeConfig(buy_slippage_rate=0.001, sell_slippage_rate=0.002))

    buy = model.calculate(Side.BUY, price=10.0, qty=100)
    sell = model.calculate(Side.SELL, price=10.0, qty=100)

    assert buy.slippage == 1.0
    assert sell.slippage == 2.0
