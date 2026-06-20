from datetime import datetime

from app.dashboard import _build_execution_sensitivity_table
from app.execution_sensitivity import build_execution_sensitivity_report
from research.trigger_engine import ActionType, FeatureSnapshot, RegimeType, SideCandidate, TradeIntent


def test_dashboard_execution_sensitivity_table_flattens_bands() -> None:
    report = build_execution_sensitivity_report(_intent())

    table = _build_execution_sensitivity_table(report)

    assert list(table.columns) == [
        "label",
        "slippage_multiplier",
        "extra_adverse_bps",
        "gross_edge",
        "estimated_fee",
        "stressed_slippage",
        "residual_buffer",
        "stressed_net_edge",
        "edge_survival_ratio",
        "status",
    ]
    assert list(table["label"]) == ["base", "worse_fill", "bad_fill", "tail_fill"]
    assert table.iloc[-1]["stressed_slippage"] > table.iloc[0]["stressed_slippage"]


def _intent() -> TradeIntent:
    price = 53.98
    return TradeIntent(
        action_type=ActionType.TRIGGER_SELL_TO_BUY,
        symbol="603236",
        timestamp=datetime(2026, 6, 20, 10, 0).isoformat(),
        side=SideCandidate.SELL_TO_BUY,
        suggested_qty=1000,
        suggested_ratio=0.1,
        reference_price=price,
        trigger_price=price,
        expected_reversion_price=price * 0.998,
        invalidation_price=price * 1.01,
        max_wait_minutes=45,
        estimated_gross_edge=1000.0,
        estimated_fee=40.0,
        estimated_slippage=20.0,
        estimated_net_edge=900.0,
        expected_cost_reduction_per_share=0.1,
        confidence=80,
        regime_type=RegimeType.MEAN_REVERTING,
        feature_snapshot=_feature(),
        next_action="review order ticket",
    )


def _feature() -> FeatureSnapshot:
    return FeatureSnapshot(
        timestamp=datetime(2026, 6, 20, 10, 0).isoformat(),
        price=53.98,
        vwap=53.5,
        anchored_vwap=53.5,
        vwap_deviation=0.008,
        anchored_vwap_deviation=0.008,
        residual_return=0.0,
        time_normalized_zscore=1.5,
        amount_ratio=1.5,
        day_return=0.01,
        day_position=0.6,
        recent_return=0.003,
        recent_high_breaks=1,
        recent_low_breaks=0,
        opening_range_break=None,
        minutes_to_close=180,
        near_upper_limit=False,
        near_lower_limit=False,
    )
