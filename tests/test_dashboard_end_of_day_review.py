from app.dashboard import _build_end_of_day_review_table
from app.end_of_day_review import EndOfDayReviewReport, EndOfDayReviewRow


def test_dashboard_end_of_day_review_table_flattens_rows() -> None:
    report = EndOfDayReviewReport(
        status="WARN",
        summary="review",
        symbol="603236",
        session_date="2026-06-20",
        closeout_status="OK",
        closeout_countable=True,
        countable_cost_basis_reduction=17.0,
        recent_journal_count=2,
        latest_journal_id="j2",
        latest_journal_status="WARN",
        blocked_journal_count=0,
        warning_journal_count=1,
        rows=(
            EndOfDayReviewRow("current_closeout", "OK", "ok", "signoff"),
            EndOfDayReviewRow("latest_persisted_journal", "WARN", "warn", "review"),
        ),
    )

    table = _build_end_of_day_review_table(report)

    assert list(table.columns) == ["item", "status", "detail", "operator_action"]
    assert list(table["item"]) == ["current_closeout", "latest_persisted_journal"]