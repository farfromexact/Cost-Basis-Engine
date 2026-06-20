from app.dashboard import _build_execution_journal_table
from app.execution_journal import ExecutionJournalItem, ExecutionJournalReport


def test_dashboard_execution_journal_table_flattens_items() -> None:
    report = ExecutionJournalReport(
        status="WARN",
        summary="review required",
        journal_id="journal-603236-20260620T100000",
        symbol="603236",
        timestamp="2026-06-20T10:00:00",
        action_type="TRIGGER_SELL_TO_BUY",
        ticket_status="OK",
        post_trade_status="NO_FILL",
        broker_reconciliation_status="NO_DATA",
        risk_usage_status="OK",
        manual_fill_count=0,
        broker_matched_count=0,
        items=(
            ExecutionJournalItem("signal", "OK", "TradeIntent", "TRIGGER_SELL_TO_BUY", "signal ok", "review ticket"),
            ExecutionJournalItem("post_trade_review", "WARN", "PostTradeReviewReport", "pair", "missing fill", "record fill"),
        ),
    )

    table = _build_execution_journal_table(report)

    assert list(table.columns) == ["stage", "status", "artifact", "reference", "detail", "operator_action"]
    assert list(table["stage"]) == ["signal", "post_trade_review"]

def test_dashboard_execution_journal_history_table_flattens_records() -> None:
    from app.dashboard import build_execution_journal_history_table

    rows = build_execution_journal_history_table([
        {
            "saved_at": "2026-06-20T15:01:00",
            "journal_id": "journal-1",
            "symbol": "603236",
            "timestamp": "2026-06-20T15:00:00",
            "status": "WARN",
            "action_type": "NO_TRADE",
            "manual_fill_count": 0,
            "broker_matched_count": 0,
            "path": ".runtime/execution_journals/journal-1.json",
        }
    ])

    assert rows == [
        {
            "saved_at": "2026-06-20T15:01:00",
            "journal_id": "journal-1",
            "symbol": "603236",
            "timestamp": "2026-06-20T15:00:00",
            "status": "WARN",
            "action_type": "NO_TRADE",
            "manual_fill_count": 0,
            "broker_matched_count": 0,
            "path": ".runtime/execution_journals/journal-1.json",
        }
    ]
