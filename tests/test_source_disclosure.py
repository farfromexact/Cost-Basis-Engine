from app.dashboard import _build_source_disclosure_table
from research.source_disclosure import build_data_source_disclosure


def test_eastmoney_disclosure_requires_broker_confirmation() -> None:
    disclosure = build_data_source_disclosure("A-share / Eastmoney")

    assert disclosure.source_name == "Eastmoney public quote endpoint"
    assert disclosure.source_grade == "research feed"
    assert disclosure.broker_confirmed is False
    assert "not broker-confirmed" in disclosure.summary()
    assert {item.topic for item in disclosure.items} >= {"Delay", "Licensing", "A-share sellability", "Broker confirmation"}
    assert any("sellable quantity" in item.operator_action for item in disclosure.items)


def test_yahoo_disclosure_flags_prototype_turnover_and_licensing() -> None:
    disclosure = build_data_source_disclosure("Korea / Yahoo Finance")

    assert disclosure.source_grade == "research/prototype feed"
    assert disclosure.broker_confirmed is False
    assert any(item.topic == "Turnover amount" and item.status == "WARN" for item in disclosure.items)
    assert any("licensed market-data" in item.operator_action for item in disclosure.items)


def test_dashboard_source_disclosure_table_has_operator_actions() -> None:
    disclosure = build_data_source_disclosure("A-share / Eastmoney")

    table = _build_source_disclosure_table(disclosure)

    assert list(table.columns) == ["topic", "status", "detail", "operator_action"]
    assert "Broker confirmation" in set(table["topic"])
    assert set(table["status"]) >= {"WARN", "REQUIRED"}

from datetime import datetime as _status_datetime

from app.dashboard import _should_expand_data_risk_details, _status_strip_payload
from core.models import MinuteBar as _StatusMinuteBar
from research.data_quality import build_data_quality_report as _build_status_data_quality_report
from research.trigger_engine import ActionType as _StatusActionType, RegimeType as _StatusRegimeType, SideCandidate as _StatusSideCandidate, TradeIntent as _StatusTradeIntent


def test_status_strip_warns_for_research_feed_without_broker_confirmation() -> None:
    disclosure = build_data_source_disclosure("A-share / Eastmoney")
    report = _build_status_data_quality_report(
        [_status_bar(_status_datetime(2026, 6, 19, 10, minute % 60)) for minute in range(40)],
        market_source="A-share / Eastmoney",
        now=_status_datetime(2026, 6, 19, 10, 39),
    )

    payload = _status_strip_payload(disclosure, report, _status_intent(_StatusActionType.NO_TRADE))

    assert payload["broker_confirmed"] == "No"
    assert payload["status"] == "WARN"
    assert payload["bars"] == "40"


def test_status_strip_marks_bad_data_bad() -> None:
    disclosure = build_data_source_disclosure("A-share / Eastmoney")
    report = _build_status_data_quality_report([], market_source="A-share / Eastmoney", now=_status_datetime(2026, 6, 19, 10, 0))

    payload = _status_strip_payload(disclosure, report, _status_intent(_StatusActionType.NO_TRADE))

    assert payload["status"] == "BAD"


def test_data_risk_details_expand_for_actionable_unconfirmed_signal() -> None:
    disclosure = build_data_source_disclosure("A-share / Eastmoney")
    report = _build_status_data_quality_report(
        [_status_bar(_status_datetime(2026, 6, 19, 10, minute % 60)) for minute in range(40)],
        market_source="A-share / Eastmoney",
        now=_status_datetime(2026, 6, 19, 10, 39),
    )

    assert _should_expand_data_risk_details(disclosure, report, _status_intent(_StatusActionType.TRIGGER_BUY_TO_SELL)) is True
    assert _should_expand_data_risk_details(disclosure, report, _status_intent(_StatusActionType.NO_TRADE)) is False


def _status_bar(ts: _status_datetime) -> _StatusMinuteBar:
    return _StatusMinuteBar(ts=ts, open=10.0, high=10.1, low=9.9, close=10.0, volume=1000, amount=10_200.0)


def _status_intent(action_type: _StatusActionType) -> _StatusTradeIntent:
    return _StatusTradeIntent(
        action_type=action_type,
        symbol="TEST",
        timestamp="2026-06-19 10:00:00",
        side=_StatusSideCandidate.BUY_TO_SELL if action_type == _StatusActionType.TRIGGER_BUY_TO_SELL else _StatusSideCandidate.NONE,
        suggested_qty=100 if action_type == _StatusActionType.TRIGGER_BUY_TO_SELL else 0,
        suggested_ratio=0.1 if action_type == _StatusActionType.TRIGGER_BUY_TO_SELL else 0.0,
        reference_price=10.0,
        trigger_price=10.0 if action_type == _StatusActionType.TRIGGER_BUY_TO_SELL else None,
        expected_reversion_price=None,
        invalidation_price=None,
        max_wait_minutes=45,
        estimated_gross_edge=0.0,
        estimated_fee=0.0,
        estimated_slippage=0.0,
        estimated_net_edge=0.0,
        expected_cost_reduction_per_share=0.0,
        confidence=80,
        regime_type=_StatusRegimeType.MEAN_REVERTING,
        next_action="test",
    )