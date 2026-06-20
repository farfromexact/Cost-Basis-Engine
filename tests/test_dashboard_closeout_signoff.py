from app.broker_import import reconcile_manual_fills_with_broker_export
from app.closeout_signoff import build_closeout_signoff_preview
from app.dashboard import _build_closeout_signoff_preview_table
from app.session_closeout import build_session_closeout_report
from app.session_risk import build_live_session_risk_usage_report


def test_dashboard_flattens_closeout_signoff_preview_checks() -> None:
    reconciliation = reconcile_manual_fills_with_broker_export([], [], symbol="603236")
    risk = build_live_session_risk_usage_report("603236", [], 10000, 10.0, "balanced", "2026-06-20", "2026-06-20 15:00:00")
    closeout = build_session_closeout_report("603236", [], reconciliation, risk, "2026-06-20")
    preview = build_closeout_signoff_preview(closeout)

    table = _build_closeout_signoff_preview_table(preview)

    assert list(table["check"]) == ["closeout_gate", "review_token"]
    assert table.iloc[0]["status"] == "OK"
    assert table.iloc[1]["status"] == "REVIEW_REQUIRED"
