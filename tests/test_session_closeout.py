from app.broker_import import BrokerFillExportRow, reconcile_manual_fills_with_broker_export
from app.manual_fills import make_manual_fill, manual_pair_id
from app.session_closeout import build_session_closeout_report
from app.session_risk import build_live_session_risk_usage_report


def test_session_closeout_counts_reduction_only_after_all_gates_pass() -> None:
    pair_id = manual_pair_id("603236", "SB", 10.0, 100)
    fills = [
        make_manual_fill("603236", pair_id, "SELL", 100, 10.0, ts="2026-06-20 10:00:00", fees=1.0, slippage=0.5),
        make_manual_fill("603236", pair_id, "BUY", 100, 9.8, ts="2026-06-20 10:20:00", fees=1.0, slippage=0.5),
    ]
    broker = [_broker_from_manual(fill, f"bf{idx}") for idx, fill in enumerate(fills)]
    reconciliation = reconcile_manual_fills_with_broker_export(fills, broker, symbol="603236")
    risk = build_live_session_risk_usage_report("603236", fills, 10000, 10.0, "balanced", "2026-06-20", "2026-06-20 15:00:00")

    report = build_session_closeout_report("603236", fills, reconciliation, risk, "2026-06-20")

    assert report.status == "OK"
    assert report.countable is True
    assert report.closed_pair_count == 1
    assert report.open_pair_count == 0
    assert report.net_position_delta_qty == 0
    assert report.countable_cost_basis_reduction == 17.0


def test_session_closeout_blocks_when_broker_reconciliation_is_missing() -> None:
    pair_id = manual_pair_id("603236", "SB", 10.0, 100)
    fills = [
        make_manual_fill("603236", pair_id, "SELL", 100, 10.0, ts="2026-06-20 10:00:00"),
        make_manual_fill("603236", pair_id, "BUY", 100, 9.8, ts="2026-06-20 10:20:00"),
    ]
    reconciliation = reconcile_manual_fills_with_broker_export(fills, [], symbol="603236")
    risk = build_live_session_risk_usage_report("603236", fills, 10000, 10.0, "balanced", "2026-06-20", "2026-06-20 15:00:00")

    report = build_session_closeout_report("603236", fills, reconciliation, risk, "2026-06-20")

    assert report.status == "BLOCKED"
    assert report.countable is False
    assert report.countable_cost_basis_reduction == 0.0
    assert any(check.check == "broker_reconciliation" and check.status == "BLOCKED" for check in report.checks)


def test_session_closeout_blocks_open_inventory_and_risk_breach() -> None:
    pair_id = manual_pair_id("603236", "SB", 10.0, 600)
    fills = [make_manual_fill("603236", pair_id, "SELL", 600, 10.0, ts="2026-06-20 10:00:00")]
    broker = [_broker_from_manual(fills[0], "bf-open")]
    reconciliation = reconcile_manual_fills_with_broker_export(fills, broker, symbol="603236")
    risk = build_live_session_risk_usage_report("603236", fills, 10000, 10.0, "defensive", "2026-06-20", "2026-06-20 10:40:00")

    report = build_session_closeout_report("603236", fills, reconciliation, risk, "2026-06-20")

    assert report.status == "BLOCKED"
    assert report.open_pair_count == 1
    assert report.net_position_delta_qty == -600
    assert any(check.check == "inventory_restored" and check.status == "BLOCKED" for check in report.checks)
    assert any(check.check == "risk_breaches" and check.status == "BLOCKED" for check in report.checks)


def test_session_closeout_no_fills_has_no_countable_reduction() -> None:
    reconciliation = reconcile_manual_fills_with_broker_export([], [], symbol="603236")
    risk = build_live_session_risk_usage_report("603236", [], 10000, 10.0, "balanced", "2026-06-20", "2026-06-20 15:00:00")

    report = build_session_closeout_report("603236", [], reconciliation, risk, "2026-06-20")

    assert report.status == "NO_ACTION"
    assert report.countable is False
    assert report.countable_cost_basis_reduction == 0.0


def _broker_from_manual(fill, broker_fill_id: str) -> BrokerFillExportRow:
    return BrokerFillExportRow(
        broker_fill_id=broker_fill_id,
        symbol=fill.symbol,
        side=fill.side,
        qty=fill.qty,
        price=fill.price,
        ts=fill.ts,
        fees=fill.fees,
        slippage=fill.slippage,
    )

def test_session_closeout_attributes_each_pair_broker_match_and_net_cash() -> None:
    closed_pair = manual_pair_id("603236", "SB", 10.0, 100)
    open_pair = manual_pair_id("603236", "SB", 11.0, 200)
    fills = [
        make_manual_fill("603236", closed_pair, "SELL", 100, 10.0, ts="2026-06-20 10:00:00", fees=1.0, slippage=0.5),
        make_manual_fill("603236", closed_pair, "BUY", 100, 9.8, ts="2026-06-20 10:20:00", fees=1.0, slippage=0.5),
        make_manual_fill("603236", open_pair, "SELL", 200, 11.0, ts="2026-06-20 11:00:00", fees=1.0, slippage=0.5),
    ]
    broker = [_broker_from_manual(fill, f"bf{idx}") for idx, fill in enumerate(fills[:2])]
    reconciliation = reconcile_manual_fills_with_broker_export(fills, broker, symbol="603236")
    risk = build_live_session_risk_usage_report("603236", fills, 10000, 10.0, "balanced", "2026-06-20", "2026-06-20 15:00:00")

    report = build_session_closeout_report("603236", fills, reconciliation, risk, "2026-06-20")
    by_pair = {pair.pair_id: pair for pair in report.pair_attributions}

    assert by_pair[closed_pair].buy_qty == 100
    assert by_pair[closed_pair].sell_qty == 100
    assert by_pair[closed_pair].broker_matched_count == 2
    assert by_pair[closed_pair].net_cash_after_fees_slippage == 17.0
    assert by_pair[closed_pair].countable is False
    assert by_pair[closed_pair].status == "READY"
    assert by_pair[open_pair].status == "BLOCKED"
    assert by_pair[open_pair].broker_matched_count == 0
    assert "not balanced" in by_pair[open_pair].blocking_reason
