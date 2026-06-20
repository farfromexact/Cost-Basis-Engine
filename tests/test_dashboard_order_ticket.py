from datetime import datetime

from app.dashboard import _build_pre_trade_order_ticket_table
from app.order_ticket import build_pre_trade_order_ticket
from app.position_reconciliation import BrokerPositionSnapshot
from core.fee_model import FeeModel
from research.trigger_engine import ActionType, FeatureSnapshot, RegimeType, RulesConfig, SideCandidate, TradeIntent


def test_dashboard_pre_trade_order_ticket_table_contains_operator_actions() -> None:
    intent = _intent(ActionType.TRIGGER_SELL_TO_BUY, SideCandidate.SELL_TO_BUY, qty=1000)
    broker = BrokerPositionSnapshot("A-share / Eastmoney", "603236", 151400, 151400, 15100, cash_available=100000.0)
    ticket = build_pre_trade_order_ticket(intent, broker, FeeModel(), RulesConfig())

    table = _build_pre_trade_order_ticket_table(ticket)

    assert list(table.columns) == ["check", "status", "detail", "operator_action"]
    assert "broker_sellable_qty" in set(table["check"])
    assert "fee_slippage" in set(table["check"])


def _intent(action: ActionType, side: SideCandidate, qty: int) -> TradeIntent:
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
        estimated_gross_edge=1000.0,
        estimated_fee=20.0,
        estimated_slippage=10.0,
        estimated_net_edge=970.0,
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
