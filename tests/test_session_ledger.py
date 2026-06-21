from app.session_closeout import SessionCloseoutPairAttribution, SessionCloseoutReport
from app.session_ledger import build_session_ledger_summary


def test_session_ledger_separates_countable_closeout_reduction() -> None:
    closeout = _closeout(
        status="OK",
        countable=True,
        reduction=17.0,
        pairs=(SessionCloseoutPairAttribution("pair-1", "COUNTABLE", 100, 100, 2, 2, 17.0, True, "ok"),),
    )

    ledger = build_session_ledger_summary(closeout)

    assert ledger.status == "OK"
    assert ledger.realized_countable_reduction == 17.0
    assert ledger.blocked_pair_net_cash == 0.0
    assert ledger.no_action_day is False
    assert ledger.rows[0].category == "COUNTABLE_CLOSEOUT_REDUCTION"
    assert ledger.rows[0].countable is True


def test_session_ledger_keeps_blocked_pair_cash_non_countable() -> None:
    closeout = _closeout(
        status="BLOCKED",
        countable=False,
        reduction=0.0,
        pairs=(SessionCloseoutPairAttribution("pair-2", "BLOCKED", 0, 100, 1, 1, 1000.0, False, "Pair is not balanced."),),
    )

    ledger = build_session_ledger_summary(closeout)

    assert ledger.status == "BLOCKED"
    assert ledger.realized_countable_reduction == 0.0
    assert ledger.blocked_pair_net_cash == 1000.0
    assert ledger.blocked_pair_count == 1
    assert ledger.rows[0].category == "BLOCKED_PAIR_NET_CASH"
    assert ledger.rows[0].countable is False


def test_session_ledger_marks_no_action_day() -> None:
    closeout = _closeout(status="NO_ACTION", countable=False, reduction=0.0, manual_fill_count=0, pairs=())

    ledger = build_session_ledger_summary(closeout)

    assert ledger.status == "NO_ACTION"
    assert ledger.no_action_day is True
    assert ledger.realized_countable_reduction == 0.0
    assert ledger.blocked_pair_net_cash == 0.0
    assert ledger.rows[0].category == "NO_ACTION_DAY"


def _closeout(
    status: str,
    countable: bool,
    reduction: float,
    pairs: tuple[SessionCloseoutPairAttribution, ...],
    manual_fill_count: int = 2,
) -> SessionCloseoutReport:
    return SessionCloseoutReport(
        status=status,
        summary="closeout",
        symbol="603236",
        session_date="2026-06-20",
        manual_fill_count=manual_fill_count,
        closed_pair_count=sum(1 for pair in pairs if pair.buy_qty == pair.sell_qty and pair.buy_qty > 0),
        open_pair_count=sum(1 for pair in pairs if pair.buy_qty != pair.sell_qty),
        net_position_delta_qty=0,
        broker_reconciliation_status="OK",
        risk_usage_status="OK",
        countable_cost_basis_reduction=reduction,
        countable=countable,
        checks=(),
        pair_attributions=pairs,
    )
