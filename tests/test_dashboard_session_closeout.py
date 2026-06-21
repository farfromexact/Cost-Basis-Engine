from app.dashboard import _build_session_closeout_table
from app.session_closeout import SessionCloseoutCheck, SessionCloseoutReport


def test_dashboard_session_closeout_table_flattens_checks() -> None:
    report = SessionCloseoutReport(
        status="BLOCKED",
        summary="blocked",
        symbol="603236",
        session_date="2026-06-20",
        manual_fill_count=1,
        closed_pair_count=0,
        open_pair_count=1,
        net_position_delta_qty=-100,
        broker_reconciliation_status="OK",
        risk_usage_status="BLOCKED",
        countable_cost_basis_reduction=0.0,
        countable=False,
        checks=(
            SessionCloseoutCheck("inventory_restored", "BLOCKED", "open pair", "restore"),
            SessionCloseoutCheck("risk_breaches", "BLOCKED", "risk", "stop"),
        ),
    )

    table = _build_session_closeout_table(report)

    assert list(table.columns) == ["check", "status", "detail", "operator_action"]
    assert list(table["check"]) == ["inventory_restored", "risk_breaches"]

def test_dashboard_session_closeout_pair_table_flattens_attributions() -> None:
    from app.dashboard import _build_session_closeout_pair_table
    from app.session_closeout import SessionCloseoutPairAttribution

    report = SessionCloseoutReport(
        status="OK",
        summary="ok",
        symbol="603236",
        session_date="2026-06-20",
        manual_fill_count=2,
        closed_pair_count=1,
        open_pair_count=0,
        net_position_delta_qty=0,
        broker_reconciliation_status="OK",
        risk_usage_status="OK",
        countable_cost_basis_reduction=17.0,
        countable=True,
        checks=(),
        pair_attributions=(
            SessionCloseoutPairAttribution("pair-1", "COUNTABLE", 100, 100, 2, 2, 17.0, True, "ok"),
        ),
    )

    table = _build_session_closeout_pair_table(report)

    assert list(table.columns) == [
        "pair_id",
        "status",
        "buy_qty",
        "sell_qty",
        "fill_count",
        "broker_matched_count",
        "net_cash_after_fees_slippage",
        "countable",
        "blocking_reason",
    ]
    assert table.iloc[0]["pair_id"] == "pair-1"


def test_dashboard_session_ledger_table_flattens_rows() -> None:
    from app.dashboard import _build_session_ledger_table
    from app.session_closeout import SessionCloseoutPairAttribution
    from app.session_ledger import build_session_ledger_summary

    report = SessionCloseoutReport(
        status="BLOCKED",
        summary="blocked",
        symbol="603236",
        session_date="2026-06-20",
        manual_fill_count=1,
        closed_pair_count=0,
        open_pair_count=1,
        net_position_delta_qty=-100,
        broker_reconciliation_status="OK",
        risk_usage_status="BLOCKED",
        countable_cost_basis_reduction=0.0,
        countable=False,
        checks=(),
        pair_attributions=(
            SessionCloseoutPairAttribution("pair-2", "BLOCKED", 0, 100, 1, 1, 1000.0, False, "open"),
        ),
    )

    table = _build_session_ledger_table(build_session_ledger_summary(report))

    assert list(table.columns) == [
        "category",
        "status",
        "pair_id",
        "net_cash_after_fees_slippage",
        "countable",
        "detail",
        "operator_action",
    ]
    assert table.iloc[0]["category"] == "BLOCKED_PAIR_NET_CASH"
