from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from app.broker_import import BrokerImportReconciliationReport
from app.manual_fills import ManualFill
from app.session_risk import LiveSessionRiskUsageReport
from core.models import Side


SESSION_CLOSEOUT_NOTE = (
    "end-of-day closeout checks gate whether closed manual pairs can be counted as "
    "cost-basis reduction evidence; they do not infer fills, route orders, or claim profitability"
)


@dataclass(frozen=True)
class SessionCloseoutCheck:
    check: str
    status: str
    detail: str
    operator_action: str

    def as_dict(self) -> dict[str, str]:
        return {
            "check": self.check,
            "status": self.status,
            "detail": self.detail,
            "operator_action": self.operator_action,
        }


@dataclass(frozen=True)
class SessionCloseoutPairAttribution:
    pair_id: str
    status: str
    buy_qty: int
    sell_qty: int
    fill_count: int
    broker_matched_count: int
    net_cash_after_fees_slippage: float
    countable: bool
    blocking_reason: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "pair_id": self.pair_id,
            "status": self.status,
            "buy_qty": self.buy_qty,
            "sell_qty": self.sell_qty,
            "fill_count": self.fill_count,
            "broker_matched_count": self.broker_matched_count,
            "net_cash_after_fees_slippage": self.net_cash_after_fees_slippage,
            "countable": self.countable,
            "blocking_reason": self.blocking_reason,
        }


@dataclass(frozen=True)
class SessionCloseoutReport:
    status: str
    summary: str
    symbol: str
    session_date: str
    manual_fill_count: int
    closed_pair_count: int
    open_pair_count: int
    net_position_delta_qty: int
    broker_reconciliation_status: str
    risk_usage_status: str
    countable_cost_basis_reduction: float
    countable: bool
    checks: tuple[SessionCloseoutCheck, ...]
    pair_attributions: tuple[SessionCloseoutPairAttribution, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "summary": self.summary,
            "symbol": self.symbol,
            "session_date": self.session_date,
            "manual_fill_count": self.manual_fill_count,
            "closed_pair_count": self.closed_pair_count,
            "open_pair_count": self.open_pair_count,
            "net_position_delta_qty": self.net_position_delta_qty,
            "broker_reconciliation_status": self.broker_reconciliation_status,
            "risk_usage_status": self.risk_usage_status,
            "countable_cost_basis_reduction": self.countable_cost_basis_reduction,
            "countable": self.countable,
            "checks": [check.as_dict() for check in self.checks],
            "pair_attributions": [pair.as_dict() for pair in self.pair_attributions],
            "capability_note": SESSION_CLOSEOUT_NOTE,
        }


def build_session_closeout_report(
    symbol: str,
    manual_fills: Iterable[ManualFill],
    broker_reconciliation: BrokerImportReconciliationReport,
    risk_usage: LiveSessionRiskUsageReport,
    session_date: str | None = None,
) -> SessionCloseoutReport:
    date_text = _date_text(str(session_date or risk_usage.session_date or ""))
    fills = [fill for fill in manual_fills if fill.symbol == symbol and (not date_text or _date_text(fill.ts) == date_text)]
    pair_rows = _pair_rows(fills)
    matched_manual_fill_ids = _matched_manual_fill_ids(broker_reconciliation)
    closed_pairs = [row for row in pair_rows if row["closed"]]
    open_pairs = [row for row in pair_rows if not row["closed"]]
    net_delta = sum(_signed_qty(fill) for fill in fills)

    checks = (
        _manual_pair_check(len(fills), len(closed_pairs), len(open_pairs)),
        _broker_reconciliation_check(len(fills), broker_reconciliation),
        _inventory_restoration_check(net_delta, len(open_pairs), risk_usage.open_pair_count),
        _risk_breach_check(risk_usage),
    )
    status = _aggregate_status(check.status for check in checks)
    countable = status == "OK" and bool(closed_pairs)
    gross_reduction = round(sum(float(row["net_cash"]) for row in closed_pairs), 4) if countable else 0.0
    pair_attributions = tuple(_pair_attribution(row, matched_manual_fill_ids, countable and row["closed"]) for row in pair_rows)
    return SessionCloseoutReport(
        status=status,
        summary=_summary(status, symbol, date_text, len(closed_pairs), len(open_pairs), gross_reduction, countable),
        symbol=symbol,
        session_date=date_text,
        manual_fill_count=len(fills),
        closed_pair_count=len(closed_pairs),
        open_pair_count=len(open_pairs),
        net_position_delta_qty=int(net_delta),
        broker_reconciliation_status=broker_reconciliation.status,
        risk_usage_status=risk_usage.status,
        countable_cost_basis_reduction=gross_reduction,
        countable=countable,
        checks=checks,
        pair_attributions=pair_attributions,
    )


def _pair_rows(fills: list[ManualFill]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for fill in fills:
        bucket = grouped.setdefault(fill.pair_id, {"buy_qty": 0, "sell_qty": 0, "net_cash": 0.0, "fills": []})
        bucket["fills"].append(fill)
        if fill.side is Side.BUY:
            bucket["buy_qty"] += fill.qty
        else:
            bucket["sell_qty"] += fill.qty
        bucket["net_cash"] += fill.cash_delta
    rows = []
    for pair_id, bucket in grouped.items():
        buy_qty = int(bucket["buy_qty"])
        sell_qty = int(bucket["sell_qty"])
        rows.append(
            {
                "pair_id": pair_id,
                "buy_qty": buy_qty,
                "sell_qty": sell_qty,
                "closed": buy_qty == sell_qty and buy_qty > 0,
                "net_cash": round(float(bucket["net_cash"]), 4),
                "fills": tuple(bucket["fills"]),
            }
        )
    return rows


def _matched_manual_fill_ids(report: BrokerImportReconciliationReport) -> set[str]:
    return {item.manual_fill_id for item in report.items if item.status == "MATCHED" and item.manual_fill_id}


def _pair_attribution(row: dict[str, Any], matched_manual_fill_ids: set[str], session_countable: bool) -> SessionCloseoutPairAttribution:
    fills = tuple(row["fills"])
    matched_count = sum(1 for fill in fills if fill.fill_id in matched_manual_fill_ids)
    fill_count = len(fills)
    closed = bool(row["closed"])
    broker_matched = matched_count == fill_count and fill_count > 0
    countable = bool(session_countable and closed and broker_matched)
    if not closed:
        status = "BLOCKED"
        reason = "Pair is not balanced; buy and sell quantities differ."
    elif not broker_matched:
        status = "BLOCKED"
        reason = f"Broker reconciliation matched {matched_count}/{fill_count} fill(s)."
    elif countable:
        status = "COUNTABLE"
        reason = "Pair is closed, broker-matched, and included in countable closeout reduction."
    else:
        status = "READY"
        reason = "Pair is closed and broker-matched, but session-level closeout gates are not countable."
    return SessionCloseoutPairAttribution(
        pair_id=str(row["pair_id"]),
        status=status,
        buy_qty=int(row["buy_qty"]),
        sell_qty=int(row["sell_qty"]),
        fill_count=fill_count,
        broker_matched_count=matched_count,
        net_cash_after_fees_slippage=round(float(row["net_cash"]), 4),
        countable=countable,
        blocking_reason=reason,
    )


def _manual_pair_check(manual_count: int, closed_pair_count: int, open_pair_count: int) -> SessionCloseoutCheck:
    if manual_count == 0:
        return SessionCloseoutCheck(
            "manual_closed_pairs",
            "NO_ACTION",
            "No manual fills exist for this symbol/session, so no cost-basis reduction can be counted.",
            "Record broker-confirmed manual fills before closeout accounting.",
        )
    if open_pair_count > 0:
        return SessionCloseoutCheck(
            "manual_closed_pairs",
            "BLOCKED",
            f"Manual fills include {open_pair_count} open pair(s); closed pairs={closed_pair_count}.",
            "Close or restore every manual pair before counting cost-basis reduction.",
        )
    if closed_pair_count <= 0:
        return SessionCloseoutCheck(
            "manual_closed_pairs",
            "BLOCKED",
            "Manual fills exist but no balanced buy/sell pair is closed.",
            "Reconcile pair ids and both legs before closeout accounting.",
        )
    return SessionCloseoutCheck(
        "manual_closed_pairs",
        "OK",
        f"All manual pair ids are balanced; closed pairs={closed_pair_count}.",
        "Continue to broker reconciliation and risk checks.",
    )


def _broker_reconciliation_check(manual_count: int, report: BrokerImportReconciliationReport) -> SessionCloseoutCheck:
    if manual_count == 0:
        return SessionCloseoutCheck(
            "broker_reconciliation",
            "NO_ACTION",
            "No manual fills require broker reconciliation for closeout.",
            "No action required unless broker fills exist.",
        )
    if report.status != "OK" or report.matched_count < manual_count:
        return SessionCloseoutCheck(
            "broker_reconciliation",
            "BLOCKED",
            f"Broker reconciliation status={report.status}; matched {report.matched_count}/{manual_count} manual fill(s).",
            "Match every manual fill to a broker-confirmed export row before counting cost-basis reduction.",
        )
    return SessionCloseoutCheck(
        "broker_reconciliation",
        "OK",
        f"Broker reconciliation matched all {manual_count} manual fill(s).",
        "No action required.",
    )


def _inventory_restoration_check(net_delta: int, open_pair_count: int, risk_open_pair_count: int) -> SessionCloseoutCheck:
    if net_delta != 0 or open_pair_count != 0 or risk_open_pair_count != 0:
        return SessionCloseoutCheck(
            "inventory_restored",
            "BLOCKED",
            f"Net session quantity delta={net_delta}; manual open pairs={open_pair_count}; risk open pairs={risk_open_pair_count}.",
            "Restore target inventory and close all same-day pair exposure before counting cost-basis reduction.",
        )
    return SessionCloseoutCheck(
        "inventory_restored",
        "OK",
        "Manual fills restore target inventory for the session; no open pair exposure remains.",
        "No action required.",
    )


def _risk_breach_check(report: LiveSessionRiskUsageReport) -> SessionCloseoutCheck:
    blocked_metrics = [check.metric for check in report.checks if check.status == "BLOCKED"]
    if report.status == "BLOCKED" or blocked_metrics:
        return SessionCloseoutCheck(
            "risk_breaches",
            "BLOCKED",
            f"Risk usage status={report.status}; blocked metrics={', '.join(blocked_metrics) or 'aggregate'}.",
            "Resolve risk-limit breaches before treating the session as closed out.",
        )
    if report.status == "WARN":
        return SessionCloseoutCheck(
            "risk_breaches",
            "WARN",
            "Risk usage has warnings but no hard breach.",
            "Review warning metrics before final end-of-day signoff.",
        )
    return SessionCloseoutCheck(
        "risk_breaches",
        "OK",
        "No risk-limit breach is open at closeout.",
        "No action required.",
    )


def _aggregate_status(statuses) -> str:
    status_set = set(statuses)
    if "BLOCKED" in status_set:
        return "BLOCKED"
    if "WARN" in status_set:
        return "WARN"
    if status_set == {"NO_ACTION"} or "NO_ACTION" in status_set:
        return "NO_ACTION"
    return "OK"


def _summary(status: str, symbol: str, session_date: str, closed_pairs: int, open_pairs: int, reduction: float, countable: bool) -> str:
    prefix = f"End-of-day closeout for {symbol} on {session_date}: closed pairs {closed_pairs}, open pairs {open_pairs}."
    if countable:
        return prefix + f" Countable cost-basis reduction after fees/slippage is {reduction:.2f}."
    if status == "BLOCKED":
        return prefix + " Blocked: do not count cost-basis reduction until every closeout gate passes."
    if status == "WARN":
        return prefix + " Warning: review closeout warnings before final signoff; no reduction is counted yet."
    return prefix + " No countable cost-basis reduction for this session."


def _signed_qty(fill: ManualFill) -> int:
    return fill.qty if fill.side is Side.BUY else -fill.qty


def _date_text(value: str) -> str:
    text = str(value or "").strip()
    return text[:10]