from datetime import datetime

from app.order_ticket import build_pre_trade_order_ticket
from app.position_reconciliation import BrokerPositionSnapshot
from core.fee_model import FeeConfig, FeeModel
from research.trigger_engine import (
    ActionType,
    FeatureSnapshot,
    RegimeType,
    RulesConfig,
    SideCandidate,
    TradeIntent,
)


def test_sell_ticket_passes_when_broker_sellable_and_costs_are_confirmed() -> None:
    intent = _intent(ActionType.TRIGGER_SELL_TO_BUY, SideCandidate.SELL_TO_BUY, qty=1000)
    broker = BrokerPositionSnapshot("A-share / Eastmoney", "603236", 151400, 120000, 15100, cash_available=50000.0)

    ticket = build_pre_trade_order_ticket(intent, broker, FeeModel(), RulesConfig())

    assert ticket.status == "OK"
    assert ticket.side == "SELL"
    assert ticket.estimated_fees > 0
    assert any(check.check == "broker_sellable_qty" and check.status == "OK" for check in ticket.checks)


def test_sell_ticket_blocks_when_quantity_exceeds_broker_sellable() -> None:
    intent = _intent(ActionType.TRIGGER_SELL_TO_BUY, SideCandidate.SELL_TO_BUY, qty=1000)
    broker = BrokerPositionSnapshot("A-share / Eastmoney", "603236", 151400, 500, 15100, cash_available=50000.0)

    ticket = build_pre_trade_order_ticket(intent, broker, FeeModel(), RulesConfig())

    assert ticket.status == "BLOCKED"
    assert any(check.check == "broker_sellable_qty" and check.status == "BLOCKED" for check in ticket.checks)


def test_buy_ticket_blocks_when_cash_is_insufficient() -> None:
    intent = _intent(ActionType.TRIGGER_BUY_TO_SELL, SideCandidate.BUY_TO_SELL, qty=1000)
    broker = BrokerPositionSnapshot("A-share / Eastmoney", "603236", 151400, 151400, 2000, cash_available=100.0)

    ticket = build_pre_trade_order_ticket(intent, broker, FeeModel(), RulesConfig())

    assert ticket.status == "BLOCKED"
    assert ticket.cash_required > broker.cash_available
    assert any(check.check == "broker_cash" and check.status == "BLOCKED" for check in ticket.checks)


def test_ticket_warns_near_price_limit_risk_zone() -> None:
    intent = _intent(
        ActionType.TRIGGER_BUY_TO_SELL,
        SideCandidate.BUY_TO_SELL,
        qty=1000,
        feature=_feature(near_upper_limit=True),
    )
    broker = BrokerPositionSnapshot("A-share / Eastmoney", "603236", 151400, 151400, 2000, cash_available=100000.0)

    ticket = build_pre_trade_order_ticket(intent, broker, FeeModel(), RulesConfig())

    assert ticket.status == "WARN"
    assert any(check.check == "price_limit_risk" and check.status == "WARN" for check in ticket.checks)


def test_ticket_blocks_zero_fee_research_profile_for_live_order() -> None:
    intent = _intent(ActionType.TRIGGER_SELL_TO_BUY, SideCandidate.SELL_TO_BUY, qty=1000)
    broker = BrokerPositionSnapshot("A-share / Eastmoney", "603236", 151400, 151400, 15100, cash_available=100000.0)
    zero_fee = FeeModel(FeeConfig(0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0))

    ticket = build_pre_trade_order_ticket(intent, broker, zero_fee, RulesConfig())

    assert ticket.status == "BLOCKED"
    assert any(check.check == "fee_slippage" and check.status == "BLOCKED" for check in ticket.checks)


def test_no_trade_intent_creates_no_action_ticket() -> None:
    intent = _intent(ActionType.NO_TRADE, SideCandidate.NONE, qty=0)

    ticket = build_pre_trade_order_ticket(intent, None, FeeModel(), RulesConfig())

    assert ticket.status == "NO_ACTION"
    assert ticket.side == "NONE"
    assert ticket.checks[0].status == "NO_ACTION"


def _intent(
    action: ActionType,
    side: SideCandidate,
    qty: int,
    feature: FeatureSnapshot | None = None,
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
        estimated_gross_edge=1000.0,
        estimated_fee=20.0,
        estimated_slippage=10.0,
        estimated_net_edge=970.0,
        expected_cost_reduction_per_share=0.1,
        confidence=80,
        regime_type=RegimeType.MEAN_REVERTING,
        feature_snapshot=feature or _feature(),
        next_action="review order ticket",
    )


def _feature(near_upper_limit: bool = False, near_lower_limit: bool = False) -> FeatureSnapshot:
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
        near_upper_limit=near_upper_limit,
        near_lower_limit=near_lower_limit,
    )
