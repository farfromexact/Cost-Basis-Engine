from datetime import datetime

from app.execution_sensitivity import ExecutionSensitivityReport, build_execution_sensitivity_report
from app.manual_fills import make_manual_fill
from app.order_ticket import build_pre_trade_order_ticket
from app.position_reconciliation import BrokerPositionSnapshot
from app.post_trade_review import build_post_trade_review_report, review_pair_id_from_ticket
from core.fee_model import FeeModel
from research.trigger_engine import ActionType, FeatureSnapshot, RegimeType, RulesConfig, SideCandidate, TradeIntent


def test_post_trade_review_passes_matching_manual_fill() -> None:
    ticket, sensitivity = _ticket_and_sensitivity()
    pair_id = review_pair_id_from_ticket(ticket)
    fill = make_manual_fill(
        ticket.symbol,
        pair_id,
        ticket.side,
        ticket.qty,
        ticket.limit_price,
        ts="2026-06-20 10:01:00",
        fees=ticket.estimated_fees,
        slippage=ticket.estimated_slippage,
    )

    report = build_post_trade_review_report(ticket, sensitivity, [fill])

    assert report.status == "OK"
    assert report.pair_id == pair_id
    assert report.fill_qty == ticket.qty
    assert any(check.check == "quantity" and check.status == "OK" for check in report.checks)


def test_post_trade_review_warns_on_partial_adverse_fill() -> None:
    ticket, sensitivity = _ticket_and_sensitivity()
    pair_id = review_pair_id_from_ticket(ticket)
    fill = make_manual_fill(
        ticket.symbol,
        pair_id,
        ticket.side,
        ticket.qty - 100,
        ticket.limit_price - 0.05,
        ts="2026-06-20 10:01:00",
        fees=ticket.estimated_fees,
        slippage=ticket.estimated_slippage,
    )

    report = build_post_trade_review_report(ticket, sensitivity, [fill])

    assert report.status == "WARN"
    assert any(check.check == "quantity" and check.status == "WARN" for check in report.checks)
    assert any(check.check == "price_vs_ticket" and check.status == "WARN" for check in report.checks)


def test_post_trade_review_blocks_overfill_against_ticket() -> None:
    ticket, sensitivity = _ticket_and_sensitivity()
    pair_id = review_pair_id_from_ticket(ticket)
    fill = make_manual_fill(ticket.symbol, pair_id, ticket.side, ticket.qty + 100, ticket.limit_price, ts="2026-06-20 10:01:00")

    report = build_post_trade_review_report(ticket, sensitivity, [fill])

    assert report.status == "BLOCKED"
    assert any(check.check == "quantity" and check.status == "BLOCKED" for check in report.checks)


def test_post_trade_review_requires_manual_fill_before_review() -> None:
    ticket, sensitivity = _ticket_and_sensitivity()

    report = build_post_trade_review_report(ticket, sensitivity, [])

    assert report.status == "NO_FILL"
    assert report.fill_qty == 0
    assert report.checks[0].status == "NO_FILL"


def test_post_trade_review_blocks_when_sensitivity_was_blocked() -> None:
    ticket, _ = _ticket_and_sensitivity()
    blocked_sensitivity = ExecutionSensitivityReport(
        status="BLOCKED",
        summary="edge exhausted",
        symbol=ticket.symbol,
        side=ticket.side,
        qty=ticket.qty,
        reference_price=ticket.limit_price,
        baseline_net_edge=0.0,
        worst_net_edge=-1.0,
        bands=(),
    )
    pair_id = review_pair_id_from_ticket(ticket)
    fill = make_manual_fill(ticket.symbol, pair_id, ticket.side, ticket.qty, ticket.limit_price, ts="2026-06-20 10:01:00")

    report = build_post_trade_review_report(ticket, blocked_sensitivity, [fill])

    assert report.status == "BLOCKED"
    assert any(check.check == "execution_sensitivity" and check.status == "BLOCKED" for check in report.checks)


def _ticket_and_sensitivity():
    intent = _intent(ActionType.TRIGGER_SELL_TO_BUY, SideCandidate.SELL_TO_BUY, qty=1000)
    broker = BrokerPositionSnapshot("A-share / Eastmoney", "603236", 151400, 120000, 15100, cash_available=100000.0)
    ticket = build_pre_trade_order_ticket(intent, broker, FeeModel(), RulesConfig())
    sensitivity = build_execution_sensitivity_report(intent)
    return ticket, sensitivity


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