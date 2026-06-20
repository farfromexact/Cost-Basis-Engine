from app.manual_fills import make_manual_fill, manual_pair_id
from app.session_risk import build_live_session_risk_usage_report


def test_live_session_risk_usage_counts_closed_pair_turnover_at_limit_as_warning() -> None:
    pair_id = manual_pair_id("603236", "SB", 10.0, 500)
    fills = [
        make_manual_fill("603236", pair_id, "SELL", 500, 10.0, ts="2026-06-20 10:00:00", fees=1.0),
        make_manual_fill("603236", pair_id, "BUY", 500, 9.9, ts="2026-06-20 10:05:00", fees=1.0),
    ]

    report = build_live_session_risk_usage_report(
        "603236",
        fills,
        target_qty=10000,
        reference_price=10.0,
        preset_id="defensive",
        session_date="2026-06-20",
        as_of="2026-06-20 10:06:00",
    )

    assert report.status == "WARN"
    assert report.gross_turnover_qty == 1000
    assert report.open_pair_count == 0
    assert any(check.metric == "daily_turnover_qty" and check.status == "WARN" for check in report.checks)
    assert any(check.metric == "same_day_capital_at_risk" and check.status == "OK" for check in report.checks)


def test_live_session_risk_usage_blocks_turnover_above_preset_limit() -> None:
    pair_id = manual_pair_id("603236", "SB", 10.0, 600)
    fills = [
        make_manual_fill("603236", pair_id, "SELL", 600, 10.0, ts="2026-06-20 10:00:00"),
        make_manual_fill("603236", pair_id, "BUY", 600, 9.9, ts="2026-06-20 10:05:00"),
    ]

    report = build_live_session_risk_usage_report("603236", fills, 10000, 10.0, "defensive", "2026-06-20")

    assert report.status == "BLOCKED"
    assert any(check.metric == "daily_turnover_qty" and check.status == "BLOCKED" for check in report.checks)


def test_live_session_risk_usage_blocks_open_capital_at_risk_and_age() -> None:
    pair_id = manual_pair_id("603236", "SB", 10.0, 600)
    fills = [make_manual_fill("603236", pair_id, "SELL", 600, 10.0, ts="2026-06-20 10:00:00")]

    report = build_live_session_risk_usage_report(
        "603236",
        fills,
        target_qty=10000,
        reference_price=10.0,
        preset_id="defensive",
        session_date="2026-06-20",
        as_of="2026-06-20 10:40:00",
    )

    assert report.status == "BLOCKED"
    assert report.open_pair_qty == 600
    assert report.open_pair_notional == 6000.0
    assert report.max_open_pair_age_minutes == 40.0
    assert any(check.metric == "same_day_capital_at_risk" and check.status == "BLOCKED" for check in report.checks)
    assert any(check.metric == "max_open_pair_age_minutes" and check.status == "BLOCKED" for check in report.checks)


def test_live_session_risk_usage_filters_to_session_date_and_symbol() -> None:
    pair_id = manual_pair_id("603236", "SB", 10.0, 100)
    fills = [
        make_manual_fill("603236", pair_id, "SELL", 100, 10.0, ts="2026-06-19 10:00:00"),
        make_manual_fill("000001", pair_id, "SELL", 100, 10.0, ts="2026-06-20 10:00:00"),
    ]

    report = build_live_session_risk_usage_report("603236", fills, 10000, 10.0, "balanced", "2026-06-20")

    assert report.manual_fill_count == 0
    assert report.gross_turnover_qty == 0
    assert report.status == "OK"