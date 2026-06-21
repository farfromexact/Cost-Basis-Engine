from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from app.session_closeout import SessionCloseoutReport


END_OF_DAY_REVIEW_NOTE = (
    "compact end-of-day review compares the current closeout gate with recent persisted "
    "execution journals; it is audit navigation only and does not create accounting events"
)


@dataclass(frozen=True)
class EndOfDayReviewRow:
    item: str
    status: str
    detail: str
    operator_action: str

    def as_dict(self) -> dict[str, str]:
        return {
            "item": self.item,
            "status": self.status,
            "detail": self.detail,
            "operator_action": self.operator_action,
        }


@dataclass(frozen=True)
class EndOfDayReviewReport:
    status: str
    summary: str
    symbol: str
    session_date: str
    closeout_status: str
    closeout_countable: bool
    countable_cost_basis_reduction: float
    recent_journal_count: int
    latest_journal_id: str
    latest_journal_status: str
    blocked_journal_count: int
    warning_journal_count: int
    rows: tuple[EndOfDayReviewRow, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "summary": self.summary,
            "symbol": self.symbol,
            "session_date": self.session_date,
            "closeout_status": self.closeout_status,
            "closeout_countable": self.closeout_countable,
            "countable_cost_basis_reduction": self.countable_cost_basis_reduction,
            "recent_journal_count": self.recent_journal_count,
            "latest_journal_id": self.latest_journal_id,
            "latest_journal_status": self.latest_journal_status,
            "blocked_journal_count": self.blocked_journal_count,
            "warning_journal_count": self.warning_journal_count,
            "rows": [row.as_dict() for row in self.rows],
            "capability_note": END_OF_DAY_REVIEW_NOTE,
        }


def build_end_of_day_review_report(
    closeout: SessionCloseoutReport,
    recent_journals: Iterable[dict[str, Any]],
) -> EndOfDayReviewReport:
    journals = list(recent_journals)
    latest = journals[0] if journals else {}
    blocked = [row for row in journals if row.get("status") == "BLOCKED"]
    warnings = [row for row in journals if row.get("status") == "WARN"]
    rows = (
        _closeout_row(closeout),
        _latest_journal_row(latest),
        _journal_history_row(journals, blocked, warnings),
    )
    status = _aggregate_status(closeout.status, latest.get("status", ""), bool(blocked), bool(warnings))
    return EndOfDayReviewReport(
        status=status,
        summary=_summary(status, closeout, journals, blocked, warnings),
        symbol=closeout.symbol,
        session_date=closeout.session_date,
        closeout_status=closeout.status,
        closeout_countable=closeout.countable,
        countable_cost_basis_reduction=closeout.countable_cost_basis_reduction,
        recent_journal_count=len(journals),
        latest_journal_id=str(latest.get("journal_id", "")),
        latest_journal_status=str(latest.get("status", "")),
        blocked_journal_count=len(blocked),
        warning_journal_count=len(warnings),
        rows=rows,
    )


def build_end_of_day_review_table(report: EndOfDayReviewReport) -> list[dict[str, str]]:
    return [row.as_dict() for row in report.rows]


def _closeout_row(closeout: SessionCloseoutReport) -> EndOfDayReviewRow:
    if closeout.status == "OK" and closeout.countable:
        return EndOfDayReviewRow(
            "current_closeout",
            "OK",
            f"Closeout is countable; reduction={closeout.countable_cost_basis_reduction:.2f}; closed pairs={closeout.closed_pair_count}.",
            "Proceed to final manual signoff only after broker statement review.",
        )
    if closeout.status == "BLOCKED":
        return EndOfDayReviewRow(
            "current_closeout",
            "BLOCKED",
            closeout.summary,
            "Resolve closeout blockers before counting cost-basis reduction.",
        )
    if closeout.status == "WARN":
        return EndOfDayReviewRow("current_closeout", "WARN", closeout.summary, "Review warnings before final signoff.")
    return EndOfDayReviewRow("current_closeout", closeout.status, closeout.summary, "No cost-basis reduction is countable from this closeout state.")


def _latest_journal_row(latest: dict[str, Any]) -> EndOfDayReviewRow:
    if not latest:
        return EndOfDayReviewRow(
            "latest_persisted_journal",
            "NO_DATA",
            "No persisted journal was found for this symbol.",
            "Run trigger/dashboard once during the session to persist an audit trail.",
        )
    status = str(latest.get("status", "")) or "NO_DATA"
    detail = f"Latest journal {latest.get('journal_id', '')} saved at {latest.get('saved_at', '')}; status={status}; timestamp={latest.get('timestamp', '')}."
    if status == "BLOCKED":
        action = "Open the persisted journal and resolve blocked audit stages."
    elif status == "WARN":
        action = "Review warning stages before closeout signoff."
    else:
        action = "Use as supporting audit context; closeout gates remain authoritative."
    return EndOfDayReviewRow("latest_persisted_journal", status, detail, action)


def _journal_history_row(journals: list[dict[str, Any]], blocked: list[dict[str, Any]], warnings: list[dict[str, Any]]) -> EndOfDayReviewRow:
    if not journals:
        return EndOfDayReviewRow("recent_journal_history", "NO_DATA", "No recent persisted journals are available.", "Persist journals before relying on cross-session review.")
    if blocked:
        return EndOfDayReviewRow(
            "recent_journal_history",
            "BLOCKED",
            f"Recent journals={len(journals)}; blocked={len(blocked)}; warnings={len(warnings)}.",
            "Investigate blocked journal snapshots before final closeout.",
        )
    if warnings:
        return EndOfDayReviewRow(
            "recent_journal_history",
            "WARN",
            f"Recent journals={len(journals)}; blocked=0; warnings={len(warnings)}.",
            "Review warning journal snapshots before final closeout.",
        )
    return EndOfDayReviewRow("recent_journal_history", "OK", f"Recent journals={len(journals)}; blocked=0; warnings=0.", "No action required.")


def _aggregate_status(closeout_status: str, latest_status: str, has_blocked_journal: bool, has_warning_journal: bool) -> str:
    if closeout_status == "BLOCKED" or latest_status == "BLOCKED" or has_blocked_journal:
        return "BLOCKED"
    if closeout_status == "WARN" or latest_status == "WARN" or has_warning_journal:
        return "WARN"
    if closeout_status == "OK":
        return "OK"
    return "NO_ACTION"


def _summary(status: str, closeout: SessionCloseoutReport, journals: list[dict[str, Any]], blocked: list[dict[str, Any]], warnings: list[dict[str, Any]]) -> str:
    base = f"End-of-day review for {closeout.symbol} on {closeout.session_date}: closeout={closeout.status}, recent journals={len(journals)}."
    if status == "OK":
        return base + f" Current closeout is countable at {closeout.countable_cost_basis_reduction:.2f}; use broker statement for final signoff."
    if status == "BLOCKED":
        return base + f" Blocked journals={len(blocked)}; warnings={len(warnings)}; do not count reduction until resolved."
    if status == "WARN":
        if closeout.status == "WARN":
            return base + f" Current closeout has warnings; journal warnings={len(warnings)}; review before final signoff."
        return base + f" Warnings={len(warnings)}; review before final signoff."
    return base + " No countable closeout action is active."
