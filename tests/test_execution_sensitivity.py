from datetime import datetime

from app.execution_sensitivity import build_execution_sensitivity_report
from research.trigger_engine import ActionType, FeatureSnapshot, RegimeType, SideCandidate, TradeIntent


def test_execution_sensitivity_keeps_positive_edge_across_bands() -> None:
    intent = _intent(gross_edge=1000.0, fee=40.0, slippage=20.0, net_edge=900.0)

    report = build_execution_sensitivity_report(intent)

    assert report.status == "OK"
    assert report.worst_net_edge > 0
    assert [band.label for band in report.bands] == ["base", "worse_fill", "bad_fill", "tail_fill"]
    assert report.bands[-1].stressed_slippage > report.bands[0].stressed_slippage


def test_execution_sensitivity_blocks_when_worse_fill_exhausts_edge() -> None:
    intent = _intent(gross_edge=100.0, fee=30.0, slippage=20.0, net_edge=40.0)

    report = build_execution_sensitivity_report(intent)

    assert report.status == "BLOCKED"
    assert report.worst_net_edge < 0
    assert any(band.status == "BLOCKED" for band in report.bands)


def test_execution_sensitivity_no_action_for_hold_intent() -> None:
    intent = _intent(action=ActionType.NO_TRADE, side=SideCandidate.NONE, qty=0)

    report = build_execution_sensitivity_report(intent)

    assert report.status == "NO_ACTION"
    assert report.bands == ()
    assert report.side == "NONE"


def _intent(
    gross_edge: float = 1000.0,
    fee: float = 40.0,
    slippage: float = 20.0,
    net_edge: float = 900.0,
    action: ActionType = ActionType.TRIGGER_SELL_TO_BUY,
    side: SideCandidate = SideCandidate.SELL_TO_BUY,
    qty: int = 1000,
) -> TradeIntent:
    price = 53.98
    return TradeIntent(
        action_type=action,
        symbol="603236",
        timestamp=datetime(2026, 6, 20, 10, 0).isoformat(),
        side=side,
        suggested_qty=qty,
        suggested_ratio=0.1,
        reference_price=price,
        trigger_price=price,
        expected_reversion_price=price * 0.998,
        invalidation_price=price * 1.01,
        max_wait_minutes=45,
        estimated_gross_edge=gross_edge,
        estimated_fee=fee,
        estimated_slippage=slippage,
        estimated_net_edge=net_edge,
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
