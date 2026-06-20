from core.fee_model import FeeConfig, FeeModel
from core.inventory_ledger import InventoryLedger
from research.replay import replay_sell_then_buy
from research.scenarios import get_scenario
from research.strategies import SellThenBuyBaselineStrategy, SellThenBuyConfig


def cheap_fee_model() -> FeeModel:
    return FeeModel(
        FeeConfig(
            min_commission=0.0,
            buy_commission_rate=0.0,
            sell_commission_rate=0.0,
            stamp_tax_rate=0.0,
            transfer_fee_rate=0.0,
            buy_slippage_rate=0.0,
            sell_slippage_rate=0.0,
        )
    )


def test_mean_revert_scenario_closes_pair_and_restores_inventory() -> None:
    result = replay_sell_then_buy(
        get_scenario("mean_revert"),
        InventoryLedger(target_qty=1000, settled_sellable_qty=1000),
        SellThenBuyBaselineStrategy(SellThenBuyConfig(trade_qty=100, min_amount_ratio=1.0)),
        cheap_fee_model(),
    )

    assert result.metrics.closed_t_net_pnl > 0
    assert result.metrics.ending_quantity_delta == 0
    assert result.metrics.unclosed_pair_rate == 0.0


def test_one_way_up_records_sell_fly_tail_risk() -> None:
    result = replay_sell_then_buy(
        get_scenario("one_way_up"),
        InventoryLedger(target_qty=1000, settled_sellable_qty=1000),
        SellThenBuyBaselineStrategy(SellThenBuyConfig(trade_qty=100, min_amount_ratio=1.0)),
        cheap_fee_model(),
    )

    assert result.metrics.unclosed_pair_rate == 1.0
    assert result.metrics.ending_quantity_delta == -100
    assert result.metrics.missed_upside_tail > 0


def test_low_liquidity_defaults_to_no_trade() -> None:
    result = replay_sell_then_buy(
        get_scenario("low_liquidity"),
        InventoryLedger(target_qty=1000, settled_sellable_qty=1000),
        SellThenBuyBaselineStrategy(SellThenBuyConfig(trade_qty=100, min_amount_ratio=1.05)),
        cheap_fee_model(),
    )

    assert result.metrics.trade_count == 0
    assert result.metrics.excess_pnl_vs_hold == 0


def test_inventory_deviation_duration_counts_minutes_not_only_fills() -> None:
    result = replay_sell_then_buy(
        get_scenario("mean_revert"),
        InventoryLedger(target_qty=1000, settled_sellable_qty=1000),
        SellThenBuyBaselineStrategy(SellThenBuyConfig(trade_qty=100, min_amount_ratio=1.0)),
        cheap_fee_model(),
    )

    assert result.metrics.max_inventory_deviation == 100
    assert result.metrics.max_inventory_deviation_duration > 1


def test_next_minute_fill_avoids_same_bar_future_function() -> None:
    bars = get_scenario("mean_revert")
    result = replay_sell_then_buy(
        bars,
        InventoryLedger(target_qty=1000, settled_sellable_qty=1000),
        SellThenBuyBaselineStrategy(SellThenBuyConfig(trade_qty=100, min_amount_ratio=1.0)),
        cheap_fee_model(),
    )

    first_fill = result.fills[0]
    assert first_fill.ts == bars[3].ts
    assert first_fill.price == bars[3].open


def test_opening_sell_fill_has_pair_id() -> None:
    result = replay_sell_then_buy(
        get_scenario("mean_revert"),
        InventoryLedger(target_qty=1000, settled_sellable_qty=1000),
        SellThenBuyBaselineStrategy(SellThenBuyConfig(trade_qty=100, min_amount_ratio=1.0)),
        cheap_fee_model(),
    )

    assert result.fills[0].pair_id == "SB-0001"


def test_default_fee_model_blocks_weak_edge_trade() -> None:
    result = replay_sell_then_buy(
        get_scenario("mean_revert"),
        InventoryLedger(target_qty=1000, settled_sellable_qty=1000),
        SellThenBuyBaselineStrategy(SellThenBuyConfig(trade_qty=100, min_amount_ratio=1.0)),
    )

    assert result.metrics.trade_count == 0
    assert result.metrics.excess_pnl_vs_hold == 0
