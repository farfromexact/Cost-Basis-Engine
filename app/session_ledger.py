from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.session_closeout import SessionCloseoutPairAttribution, SessionCloseoutReport


SESSION_LEDGER_NOTE = (
    "session ledger is an EOD accounting summary only; countable reduction comes only "
    "from closeout-approved pairs, while blocked pair cash remains non-countable until all gates pass"
)


@dataclass(frozen=True)
class SessionLedgerRow:
    category: str
    status: str
    pair_id: str
    net_cash_after_fees_slippage: float
    countable: bool
    detail: str
    operator_action: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "status": self.status,
            "pair_id": self.pair_id,
            "net_cash_after_fees_slippage": self.net_cash_after_fees_slippage,
            "countable": self.countable,
            "detail": self.detail,
            "operator_action": self.operator_action,
        }


@dataclass(frozen=True)
class SessionLedgerSummary:
    status: str
    summary: str
    symbol: str
    session_date: str
    realized_countable_reduction: float
    blocked_pair_net_cash: float
    no_action_day: bool
    countable_pair_count: int
    blocked_pair_count: int
    row_count: int
    rows: tuple[SessionLedgerRow, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "summary": self.summary,
            "symbol": self.symbol,
            "session_date": self.session_date,
            "realized_countable_reduction": self.realized_countable_reduction,
            "blocked_pair_net_cash": self.blocked_pair_net_cash,
            "no_action_day": self.no_action_day,
            "countable_pair_count": self.countable_pair_count,
            "blocked_pair_count": self.blocked_pair_count,
            "row_count": self.row_count,
            "rows": [row.as_dict() for row in self.rows],
            "capability_note": SESSION_LEDGER_NOTE,
        }


def build_session_ledger_summary(closeout: SessionCloseoutReport) -> SessionLedgerSummary:
    countable_pairs = tuple(pair for pair in closeout.pair_attributions if pair.countable)
    blocked_pairs = tuple(pair for pair in closeout.pair_attributions if not pair.countable)
    no_action_day = closeout.manual_fill_count == 0 and not closeout.pair_attributions
    rows: list[SessionLedgerRow] = []
    rows.extend(_countable_rows(countable_pairs))
    rows.extend(_blocked_rows(blocked_pairs))
    if no_action_day:
        rows.append(
            SessionLedgerRow(
                category="NO_ACTION_DAY",
                status="NO_ACTION",
                pair_id="",
                net_cash_after_fees_slippage=0.0,
                countable=False,
                detail="No manual fills or pair attributions exist for this session.",
                operator_action="No cost-basis reduction is countable for the session.",
            )
        )

    realized = round(float(closeout.countable_cost_basis_reduction if closeout.countable else 0.0), 4)
    blocked_cash = round(sum(pair.net_cash_after_fees_slippage for pair in blocked_pairs), 4)
    status = _ledger_status(closeout, blocked_pairs, no_action_day)
    return SessionLedgerSummary(
        status=status,
        summary=_summary(closeout.symbol, closeout.session_date, realized, blocked_cash, no_action_day, status),
        symbol=closeout.symbol,
        session_date=closeout.session_date,
        realized_countable_reduction=realized,
        blocked_pair_net_cash=blocked_cash,
        no_action_day=no_action_day,
        countable_pair_count=len(countable_pairs),
        blocked_pair_count=len(blocked_pairs),
        row_count=len(rows),
        rows=tuple(rows),
    )


def _countable_rows(pairs: tuple[SessionCloseoutPairAttribution, ...]) -> list[SessionLedgerRow]:
    return [
        SessionLedgerRow(
            category="COUNTABLE_CLOSEOUT_REDUCTION",
            status="COUNTABLE",
            pair_id=pair.pair_id,
            net_cash_after_fees_slippage=pair.net_cash_after_fees_slippage,
            countable=True,
            detail="Pair passed closeout gates and is included in realized countable reduction.",
            operator_action="Include only after final EOD signoff.",
        )
        for pair in pairs
    ]


def _blocked_rows(pairs: tuple[SessionCloseoutPairAttribution, ...]) -> list[SessionLedgerRow]:
    return [
        SessionLedgerRow(
            category="BLOCKED_PAIR_NET_CASH",
            status=pair.status,
            pair_id=pair.pair_id,
            net_cash_after_fees_slippage=pair.net_cash_after_fees_slippage,
            countable=False,
            detail=pair.blocking_reason,
            operator_action="Do not count this cash result until the pair and session closeout gates pass.",
        )
        for pair in pairs
    ]


def _ledger_status(
    closeout: SessionCloseoutReport,
    blocked_pairs: tuple[SessionCloseoutPairAttribution, ...],
    no_action_day: bool,
) -> str:
    if no_action_day:
        return "NO_ACTION"
    if closeout.status == "BLOCKED" or any(pair.status == "BLOCKED" for pair in blocked_pairs):
        return "BLOCKED"
    if closeout.status == "WARN" or blocked_pairs:
        return "WARN"
    if closeout.countable:
        return "OK"
    return closeout.status


def _summary(
    symbol: str,
    session_date: str,
    realized: float,
    blocked_cash: float,
    no_action_day: bool,
    status: str,
) -> str:
    base = (
        f"Session ledger for {symbol} on {session_date}: realized countable reduction {realized:.2f}; "
        f"blocked pair net cash {blocked_cash:.2f}."
    )
    if no_action_day:
        return base + " No-action day: no manual pair cash is countable."
    if status == "OK":
        return base + " Countable rows are separated from non-countable cash."
    if status == "BLOCKED":
        return base + " Blocked rows must not be counted as cost-basis reduction."
    if status == "WARN":
        return base + " Review warning rows before final signoff."
    return base + " No countable closeout reduction is active."
