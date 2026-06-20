from app.broker_import import BrokerFillReconciliationItem, BrokerImportReconciliationReport
from app.dashboard import _build_broker_import_reconciliation_table


def test_dashboard_broker_import_reconciliation_table_flattens_items() -> None:
    report = BrokerImportReconciliationReport(
        status="WARN",
        summary="review unmatched",
        symbol="603236",
        broker_fill_count=1,
        manual_fill_count=0,
        matched_count=0,
        broker_only_count=1,
        manual_only_count=0,
        ambiguous_count=0,
        items=(
            BrokerFillReconciliationItem(
                "603236|SELL|100|53.9800|2026-06-20 10:00:00",
                "BROKER_ONLY",
                "bf1",
                "",
                "603236",
                "SELL",
                100,
                53.98,
                "2026-06-20 10:00:00",
                "missing manual fill",
                "review broker row",
            ),
        ),
    )

    table = _build_broker_import_reconciliation_table(report)

    assert list(table.columns) == ["match_key", "status", "broker_fill_id", "manual_fill_id", "symbol", "side", "qty", "price", "ts", "detail", "operator_action"]
    assert table.iloc[0]["status"] == "BROKER_ONLY"