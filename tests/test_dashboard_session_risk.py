from app.dashboard import _build_live_session_risk_usage_table
from app.session_risk import LiveSessionRiskUsageCheck, LiveSessionRiskUsageReport


def test_dashboard_live_session_risk_usage_table_flattens_checks() -> None:
    report = LiveSessionRiskUsageReport(
        status="WARN",
        summary="usage near limit",
        symbol="603236",
        session_date="2026-06-20",
        preset_id="defensive",
        preset_label="Defensive",
        target_qty=10000,
        reference_price=10.0,
        manual_fill_count=1,
        gross_turnover_qty=900,
        gross_turnover_notional=9000.0,
        net_position_delta_qty=-900,
        open_pair_count=1,
        open_pair_qty=900,
        open_pair_notional=9000.0,
        max_open_pair_age_minutes=12.0,
        checks=(
            LiveSessionRiskUsageCheck("daily_turnover_qty", "WARN", 900.0, 1000.0, 0.9, "near", "avoid new turnover"),
        ),
    )

    table = _build_live_session_risk_usage_table(report)

    assert list(table.columns) == ["metric", "status", "used", "limit", "usage_ratio", "detail", "operator_action"]
    assert table.iloc[0]["metric"] == "daily_turnover_qty"
    assert table.iloc[0]["usage_ratio"] == 0.9