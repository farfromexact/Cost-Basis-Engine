from datetime import datetime

from app.broker_import import BrokerFillExportRow, reconcile_manual_fills_with_broker_export
from app.execution_journal import build_execution_journal_report
from app.execution_sensitivity import build_execution_sensitivity_report
from app.manual_fills import make_manual_fill
from app.order_ticket import build_pre_trade_order_ticket
from app.position_reconciliation import BrokerPositionSnapshot
from app.post_trade_review import build_post_trade_review_report, review_pair_id_from_ticket
from app.session_risk import build_live_session_risk_usage_report
from core.fee_model import FeeModel
from research.trigger_engine import ActionType, FeatureSnapshot, RegimeType, RulesConfig, SideCandidate, TradeIntent


def test_execution_journal_links_clean_signal_to_confirmed_fill_chain() -> None:
    intent = _intent(ActionType.TRIGGER_SELL_TO_BUY, SideCandidate.SELL_TO_BUY, qty=1000)
    ticket = build_pre_trade_order_ticket(intent, _broker(), FeeModel(), RulesConfig())
    sensitivity = build_execution_sensitivity_report(intent)
    pair_id = review_pair_id_from_ticket(ticket)
    fill = make_manual_fill(ticket.symbol, pair_id, ticket.side, ticket.qty, ticket.limit_price, ts="2026-06-20 10:01:00", fees=ticket.estimated_fees, slippage=ticket.estimated_slippage)
    post_trade = build_post_trade_review_report(ticket, sensitivity, [fill])
    broker_report = reconcile_manual_fills_with_broker_export([fill], [_broker_fill_from_manual(fill)], symbol=ticket.symbol)
    risk_usage = build_live_session_risk_usage_report(ticket.symbol, [fill], 20000, ticket.limit_price, "balanced", "2026-06-20", "2026-06-20 10:02:00")

    report = build_execution_journal_report(intent, ticket, [fill], post_trade, broker_report, risk_usage)

    assert report.status == "OK"
    assert report.ticket_status == "OK"
    assert report.post_trade_status == "OK"
    assert report.broker_reconciliation_status == "OK"
    assert report.risk_usage_status == "OK"
    assert [item.stage for item in report.items] == ["signal", "pre_trade_ticket", "manual_fill", "broker_reconciliation", "post_trade_review", "risk_usage"]


def test_execution_journal_warns_when_actionable_ticket_has_no_fill_or_broker_match() -> None:
    intent = _intent(ActionType.TRIGGER_SELL_TO_BUY, SideCandidate.SELL_TO_BUY, qty=1000)
    ticket = build_pre_trade_order_ticket(intent, _broker(), FeeModel(), RulesConfig())
    sensitivity = build_execution_sensitivity_report(intent)
    post_trade = build_post_trade_review_report(ticket, sensitivity, [])
    broker_report = reconcile_manual_fills_with_broker_export([], [], symbol=ticket.symbol)
    risk_usage = build_live_session_risk_usage_report(ticket.symbol, [], 20000, ticket.limit_price, "balanced", "2026-06-20", "2026-06-20 10:02:00")

    report = build_execution_journal_report(intent, ticket, [], post_trade, broker_report, risk_usage)

    assert report.status == "WARN"
    assert any(item.stage == "manual_fill" and item.status == "WARN" for item in report.items)
    assert any(item.stage == "post_trade_review" and item.status == "WARN" for item in report.items)


def test_execution_journal_blocks_when_risk_usage_is_blocked() -> None:
    intent = _intent(ActionType.TRIGGER_SELL_TO_BUY, SideCandidate.SELL_TO_BUY, qty=1200)
    ticket = build_pre_trade_order_ticket(intent, _broker(), FeeModel(), RulesConfig())
    sensitivity = build_execution_sensitivity_report(intent)
    pair_id = review_pair_id_from_ticket(ticket)
    fill = make_manual_fill(ticket.symbol, pair_id, ticket.side, ticket.qty, ticket.limit_price, ts="2026-06-20 10:00:00")
    post_trade = build_post_trade_review_report(ticket, sensitivity, [fill])
    broker_report = reconcile_manual_fills_with_broker_export([fill], [_broker_fill_from_manual(fill)], symbol=ticket.symbol)
    risk_usage = build_live_session_risk_usage_report(ticket.symbol, [fill], 10000, ticket.limit_price, "defensive", "2026-06-20", "2026-06-20 10:40:00")

    report = build_execution_journal_report(intent, ticket, [fill], post_trade, broker_report, risk_usage)

    assert report.status == "BLOCKED"
    assert any(item.stage == "risk_usage" and item.status == "BLOCKED" for item in report.items)


def _broker() -> BrokerPositionSnapshot:
    return BrokerPositionSnapshot("A-share / Eastmoney", "603236", 50000, 50000, 10000, cash_available=100000.0)


def _broker_fill_from_manual(fill):
    return BrokerFillExportRow(
        broker_fill_id="bf1",
        symbol=fill.symbol,
        side=fill.side,
        qty=fill.qty,
        price=fill.price,
        ts=fill.ts,
        fees=fill.fees,
        slippage=fill.slippage,
    )


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

def test_execution_journal_persists_and_loads_recent_records(tmp_path) -> None:
    from app.execution_journal import build_execution_journal_history_table, load_execution_journal_records, save_execution_journal_report

    intent = _intent(ActionType.TRIGGER_SELL_TO_BUY, SideCandidate.SELL_TO_BUY, qty=1000)
    ticket = build_pre_trade_order_ticket(intent, _broker(), FeeModel(), RulesConfig())
    sensitivity = build_execution_sensitivity_report(intent)
    pair_id = review_pair_id_from_ticket(ticket)
    fill = make_manual_fill(ticket.symbol, pair_id, ticket.side, ticket.qty, ticket.limit_price, ts="2026-06-20 10:01:00")
    post_trade = build_post_trade_review_report(ticket, sensitivity, [fill])
    broker_report = reconcile_manual_fills_with_broker_export([fill], [_broker_fill_from_manual(fill)], symbol=ticket.symbol)
    risk_usage = build_live_session_risk_usage_report(ticket.symbol, [fill], 20000, ticket.limit_price, "balanced", "2026-06-20", "2026-06-20 10:02:00")
    report = build_execution_journal_report(intent, ticket, [fill], post_trade, broker_report, risk_usage)

    path = save_execution_journal_report(report, tmp_path)
    records = load_execution_journal_records(tmp_path, symbol="603236", limit=5)
    history = build_execution_journal_history_table(records)

    assert path.exists()
    assert path.parent == tmp_path
    assert records[0]["journal_id"] == report.journal_id
    assert records[0]["storage_note"] == "persisted execution journal snapshot for end-of-day review only"
    assert history[0]["status"] == report.status
    assert history[0]["path"] == str(path)


def test_execution_journal_loader_filters_symbol_and_limit(tmp_path) -> None:
    from app.execution_journal import load_execution_journal_records

    base = _intent(ActionType.TRIGGER_SELL_TO_BUY, SideCandidate.SELL_TO_BUY, qty=1000)
    from dataclasses import replace
    other = replace(_intent(ActionType.TRIGGER_SELL_TO_BUY, SideCandidate.SELL_TO_BUY, qty=1000), symbol="000001")
    for intent in (base, other):
        ticket = build_pre_trade_order_ticket(intent, _broker(), FeeModel(), RulesConfig())
        sensitivity = build_execution_sensitivity_report(intent)
        post_trade = build_post_trade_review_report(ticket, sensitivity, [])
        broker_report = reconcile_manual_fills_with_broker_export([], [], symbol=intent.symbol)
        risk_usage = build_live_session_risk_usage_report(intent.symbol, [], 20000, ticket.limit_price, "balanced", "2026-06-20", "2026-06-20 10:02:00")
        report = build_execution_journal_report(intent, ticket, [], post_trade, broker_report, risk_usage)
        from app.execution_journal import save_execution_journal_report
        save_execution_journal_report(report, tmp_path)

    records = load_execution_journal_records(tmp_path, symbol="603236", limit=1)

    assert len(records) == 1
    assert records[0]["symbol"] == "603236"
