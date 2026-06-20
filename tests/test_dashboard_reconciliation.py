from app.dashboard import _build_position_reconciliation_table
from app.position_reconciliation import BrokerPositionSnapshot, reconcile_position_state
from app.position_state import PositionSnapshot


def test_dashboard_position_reconciliation_table_contains_operator_actions() -> None:
    persisted = PositionSnapshot(symbol="603236", held_qty=151400, settled_sellable_qty=151400, purchasable_qty=15100)
    broker = BrokerPositionSnapshot(
        market_source="A-share / Eastmoney",
        symbol="603236",
        total_qty=151400,
        sellable_qty=100000,
        purchasable_qty=15100,
    )
    report = reconcile_position_state(persisted, broker)

    table = _build_position_reconciliation_table(report)

    assert list(table.columns) == ["field", "persisted_value", "broker_value", "delta", "status", "operator_action"]
    assert "settled_sellable_qty" in set(table["field"])
    assert "BLOCKED" in set(table["status"])
