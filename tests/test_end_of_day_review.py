from app.end_of_day_review import build_end_of_day_review_report, build_end_of_day_review_table
from app.session_closeout import SessionCloseoutReport


def test_end_of_day_review_is_ok_when_closeout_countable_and_journals_clean() -> None:
    closeout = _closeout(status="OK", countable=True, reduction=17.0)
    journals = [{"journal_id": "j1", "status": "OK", "saved_at": "2026-06-20T15:01:00", "timestamp": "2026-06-20 15:00:00"}]

    report = build_end_of_day_review_report(closeout, journals)

    assert report.status == "OK"
    assert report.closeout_countable is True
    assert report.latest_journal_id == "j1"
    assert report.recent_journal_count == 1
    assert report.blocked_journal_count == 0
    assert build_end_of_day_review_table(report)[0]["item"] == "current_closeout"


def test_end_of_day_review_blocks_when_recent_journal_blocked() -> None:
    closeout = _closeout(status="OK", countable=True, reduction=17.0)
    journals = [
        {"journal_id": "j2", "status": "BLOCKED", "saved_at": "2026-06-20T15:02:00", "timestamp": "2026-06-20 15:00:00"},
        {"journal_id": "j1", "status": "OK", "saved_at": "2026-06-20T15:01:00", "timestamp": "2026-06-20 14:30:00"},
    ]

    report = build_end_of_day_review_report(closeout, journals)

    assert report.status == "BLOCKED"
    assert report.blocked_journal_count == 1
    assert report.latest_journal_status == "BLOCKED"
    assert any(row.status == "BLOCKED" for row in report.rows)


def test_end_of_day_review_no_journals_preserves_no_action_closeout() -> None:
    closeout = _closeout(status="NO_ACTION", countable=False, reduction=0.0)

    report = build_end_of_day_review_report(closeout, [])

    assert report.status == "NO_ACTION"
    assert report.latest_journal_status == ""
    assert report.recent_journal_count == 0
    assert any(row.item == "latest_persisted_journal" and row.status == "NO_DATA" for row in report.rows)


def _closeout(status: str, countable: bool, reduction: float) -> SessionCloseoutReport:
    return SessionCloseoutReport(
        status=status,
        summary="closeout summary",
        symbol="603236",
        session_date="2026-06-20",
        manual_fill_count=2 if countable else 0,
        closed_pair_count=1 if countable else 0,
        open_pair_count=0,
        net_position_delta_qty=0,
        broker_reconciliation_status="OK" if countable else "NO_DATA",
        risk_usage_status="OK",
        countable_cost_basis_reduction=reduction,
        countable=countable,
        checks=(),
    )