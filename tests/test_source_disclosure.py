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
