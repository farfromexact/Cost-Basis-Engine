from core.fee_model import FeeConfig, FeeModel
from core.models import Side


def test_a_share_buy_cost_uses_official_fees_plus_broker_commission_only_minimum_on_commission() -> None:
    model = FeeModel(FeeConfig(market="A_SHARE", buy_slippage_rate=0.0, sell_slippage_rate=0.0))

    breakdown = model.calculate(Side.BUY, price=10.0, qty=10_000)

    assert round(breakdown.commission, 4) == 10.0
    assert round(breakdown.transfer_fee, 4) == 6.41
    assert breakdown.stamp_tax == 0.0
    assert round(breakdown.total_fees, 4) == 16.41


def test_a_share_sell_cost_includes_stamp_duty() -> None:
    model = FeeModel(FeeConfig(market="A_SHARE", buy_slippage_rate=0.0, sell_slippage_rate=0.0))

    breakdown = model.calculate(Side.SELL, price=10.0, qty=10_000)

    assert round(breakdown.commission, 4) == 10.0
    assert round(breakdown.transfer_fee, 4) == 6.41
    assert round(breakdown.stamp_tax, 4) == 50.0
    assert round(breakdown.total_fees, 4) == 66.41


def test_us_equity_sell_cost_includes_sec_fee_and_finra_taf() -> None:
    model = FeeModel(FeeConfig(market="US_EQUITY", buy_slippage_rate=0.0, sell_slippage_rate=0.0))

    breakdown = model.calculate(Side.SELL, price=100.0, qty=100)

    assert breakdown.commission == 0.0
    assert round(breakdown.other_fee, 6) == round(10_000 * 20.60 / 1_000_000 + 100 * 0.000195, 6)
    assert round(breakdown.total_fees, 6) == round(0.206 + 0.0195, 6)


def test_round_trip_break_even_bps_uses_buy_and_sell_costs() -> None:
    model = FeeModel(FeeConfig(market="A_SHARE", buy_slippage_rate=0.0, sell_slippage_rate=0.0))

    cost = model.estimate_round_trip_cost("A_SHARE", price=10.0, shares=10_000, side="B_TO_S")
    break_even = model.estimate_break_even_bps("A_SHARE", price=10.0, shares=10_000, side="S_TO_B")

    assert round(cost, 4) == 82.82
    assert round(break_even, 3) == 8.282
