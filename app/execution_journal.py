from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from app.broker_import import BrokerImportReconciliationReport
from app.manual_fills import ManualFill
from app.order_ticket import PreTradeOrderTicket
from app.post_trade_review import PostTradeReviewReport
from app.session_risk import LiveSessionRiskUsageReport
from research.trigger_engine import TradeIntent


EXECUTION_JOURNAL_NOTE = (
    "execution journal is a session audit trail only; it links signal, ticket, manual "
    "fills, broker reconciliation, post-trade review, and risk usage without routing "
    "orders or inferring fills"
)
EXECUTION_JOURNAL_STORAGE_NOTE = "persisted execution journal snapshot for end-of-day review only"


def default_execution_journal_dir() -> Path:
    return Path(".runtime") / "execution_journals"


@dataclass(frozen=True)
class ExecutionJournalItem:
    stage: str
    status: str
    artifact: str
    reference: str
    detail: str
    operator_action: str

    def as_dict(self) -> dict[str, str]:
        return {
            "stage": self.stage,
            "status": self.status,
            "artifact": self.artifact,
            "reference": self.reference,
            "detail": self.detail,
            "operator_action": self.operator_action,
        }


@dataclass(frozen=True)
class ExecutionJournalReport:
    status: str
    summary: str
    journal_id: str
    symbol: str
    timestamp: str
    action_type: str
    ticket_status: str
    post_trade_status: str
    broker_reconciliation_status: str
    risk_usage_status: str
    manual_fill_count: int
    broker_matched_count: int
    items: tuple[ExecutionJournalItem, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "summary": self.summary,
            "journal_id": self.journal_id,
            "symbol": self.symbol,
            "timestamp": self.timestamp,
            "action_type": self.action_type,
            "ticket_status": self.ticket_status,
            "post_trade_status": self.post_trade_status,
            "broker_reconciliation_status": self.broker_reconciliation_status,
            "risk_usage_status": self.risk_usage_status,
            "manual_fill_count": self.manual_fill_count,
            "broker_matched_count": self.broker_matched_count,
            "items": [item.as_dict() for item in self.items],
            "capability_note": EXECUTION_JOURNAL_NOTE,
        }


def build_execution_journal_report(
    intent: TradeIntent,
    ticket: PreTradeOrderTicket,
    manual_fills: Iterable[ManualFill],
    post_trade_review: PostTradeReviewReport,
    broker_reconciliation: BrokerImportReconciliationReport,
    risk_usage: LiveSessionRiskUsageReport,
) -> ExecutionJournalReport:
    manual_fills_list = list(manual_fills)
    items = (
        _signal_item(intent),
        _ticket_item(ticket),
        _manual_fill_item(ticket, manual_fills_list, post_trade_review),
        _broker_reconciliation_item(broker_reconciliation),
        _post_trade_item(post_trade_review),
        _risk_usage_item(risk_usage),
    )
    status = _aggregate_status(item.status for item in items)
    return ExecutionJournalReport(
        status=status,
        summary=_summary(status, intent.symbol, intent.action_type.value, len(manual_fills_list), broker_reconciliation.matched_count),
        journal_id=_journal_id(intent.symbol, intent.timestamp),
        symbol=intent.symbol,
        timestamp=str(intent.timestamp),
        action_type=intent.action_type.value,
        ticket_status=ticket.status,
        post_trade_status=post_trade_review.status,
        broker_reconciliation_status=broker_reconciliation.status,
        risk_usage_status=risk_usage.status,
        manual_fill_count=len(manual_fills_list),
        broker_matched_count=broker_reconciliation.matched_count,
        items=items,
    )


def _signal_item(intent: TradeIntent) -> ExecutionJournalItem:
    action = intent.action_type.value
    if action.startswith("TRIGGER_"):
        status = "OK"
        action_text = "Review the ticket and broker screen before any order entry."
        detail = f"Actionable signal {action} at {intent.timestamp}; suggested qty {intent.suggested_qty}."
    elif action.startswith("WATCH_"):
        status = "WARN"
        action_text = "Keep watching; do not treat watch state as an executable order."
        detail = f"Watch-only signal {action}; suggested qty {intent.suggested_qty}."
    elif action in {"MANAGE_OPEN_PAIR", "FORCE_CLOSE_OR_RESTORE"}:
        status = "WARN"
        action_text = "Prioritize managing existing pair state before adding new exposure."
        detail = f"Open-pair management action {action}; no new first-leg ticket should be inferred."
    else:
        status = "NO_ACTION"
        action_text = "No execution journal action is required unless a broker/manual fill exists."
        detail = f"Signal action is {action}; no actionable first-leg signal is active."
    return ExecutionJournalItem("signal", status, "TradeIntent", intent.action_type.value, detail, action_text)


def _ticket_item(ticket: PreTradeOrderTicket) -> ExecutionJournalItem:
    status = _normalized_status(ticket.status)
    return ExecutionJournalItem(
        "pre_trade_ticket",
        status,
        "PreTradeOrderTicket",
        f"{ticket.side} {ticket.qty} @ {ticket.limit_price:.4f}",
        ticket.summary,
        _ticket_action(status),
    )


def _manual_fill_item(ticket: PreTradeOrderTicket, manual_fills: list[ManualFill], post_trade_review: PostTradeReviewReport) -> ExecutionJournalItem:
    if ticket.qty <= 0 or ticket.side == "NONE":
        return ExecutionJournalItem(
            "manual_fill",
            "NO_ACTION",
            "ManualFill",
            "none",
            "No actionable ticket is active, so no manual fill is expected for this signal.",
            "Do not record a fill unless it exists on the broker screen.",
        )
    if post_trade_review.fill_qty > 0:
        return ExecutionJournalItem(
            "manual_fill",
            "OK",
            "ManualFill",
            post_trade_review.pair_id,
            f"Manual fill quantity {post_trade_review.fill_qty} is linked to post-trade review pair {post_trade_review.pair_id}.",
            "Continue with broker reconciliation and post-trade review checks.",
        )
    related = [fill for fill in manual_fills if fill.symbol == ticket.symbol]
    detail = f"No manual fill is linked to ticket pair {post_trade_review.pair_id}; symbol-level manual fill rows available: {len(related)}."
    return ExecutionJournalItem("manual_fill", "WARN", "ManualFill", post_trade_review.pair_id, detail, "Record broker-confirmed fill before relying on execution review.")


def _broker_reconciliation_item(report: BrokerImportReconciliationReport) -> ExecutionJournalItem:
    status = _normalized_status(report.status)
    if report.status == "NO_DATA":
        status = "NO_DATA"
    return ExecutionJournalItem(
        "broker_reconciliation",
        status,
        "BrokerImportReconciliationReport",
        report.symbol,
        report.summary,
        _broker_action(status),
    )


def _post_trade_item(report: PostTradeReviewReport) -> ExecutionJournalItem:
    status = _normalized_status(report.status)
    return ExecutionJournalItem(
        "post_trade_review",
        status,
        "PostTradeReviewReport",
        report.pair_id or "none",
        report.summary,
        _post_trade_action(status),
    )


def _risk_usage_item(report: LiveSessionRiskUsageReport) -> ExecutionJournalItem:
    status = _normalized_status(report.status)
    return ExecutionJournalItem(
        "risk_usage",
        status,
        "LiveSessionRiskUsageReport",
        f"{report.preset_id}:{report.session_date}",
        report.summary,
        _risk_action(status),
    )


def _normalized_status(status: str) -> str:
    if status in {"OK", "BLOCKED", "WARN", "NO_ACTION", "NO_DATA"}:
        return status
    if status in {"NO_FILL", "MANUAL_ONLY", "BROKER_ONLY", "AMBIGUOUS"}:
        return "WARN"
    return "WARN"


def _aggregate_status(statuses) -> str:
    status_set = set(statuses)
    if "BLOCKED" in status_set:
        return "BLOCKED"
    if "WARN" in status_set:
        return "WARN"
    return "OK"


def _summary(status: str, symbol: str, action_type: str, manual_fill_count: int, broker_matched_count: int) -> str:
    prefix = f"Execution journal for {symbol}: signal {action_type}, manual fills {manual_fill_count}, broker matches {broker_matched_count}."
    if status == "OK":
        return prefix + " Audit chain has no blocking or warning stages."
    if status == "BLOCKED":
        return prefix + " At least one stage is blocked; do not rely on the chain until resolved."
    return prefix + " One or more stages require operator review."


def _journal_id(symbol: str, timestamp: str) -> str:
    safe_symbol = str(symbol).replace(":", "_").replace("/", "_").replace("\\", "_")
    safe_ts = str(timestamp).replace(":", "").replace(" ", "T")[:32]
    return f"journal-{safe_symbol}-{safe_ts}"


def _ticket_action(status: str) -> str:
    if status == "BLOCKED":
        return "Do not place or rely on this ticket until blockers are resolved."
    if status == "WARN":
        return "Resolve ticket warnings before manual order entry."
    if status == "NO_ACTION":
        return "No ticket action required."
    return "No action required."


def _broker_action(status: str) -> str:
    if status == "BLOCKED":
        return "Resolve duplicate or invalid broker/manual reconciliation keys."
    if status == "WARN":
        return "Review unmatched broker/manual rows before treating fills as confirmed."
    if status == "NO_DATA":
        return "Add broker export when broker confirmation is available."
    return "No action required."


def _post_trade_action(status: str) -> str:
    if status == "BLOCKED":
        return "Reconcile post-trade conflicts before updating risk or accounting."
    if status == "WARN":
        return "Review fill quality, costs, and sensitivity warnings."
    if status == "NO_ACTION":
        return "No post-trade action required for this no-action signal."
    if status == "NO_DATA":
        return "Collect required post-trade inputs."
    return "No action required."


def _risk_action(status: str) -> str:
    if status == "BLOCKED":
        return "Stop adding exposure until preset risk usage is back within limits."
    if status == "WARN":
        return "Avoid new first-leg risk unless it reduces existing exposure."
    if status == "NO_DATA":
        return "Record missing risk scale inputs."
    return "No action required."

def save_execution_journal_report(report: ExecutionJournalReport, directory: str | Path | None = None) -> Path:
    journal_dir = Path(directory) if directory is not None else default_execution_journal_dir()
    journal_dir.mkdir(parents=True, exist_ok=True)
    path = journal_dir / f"{_safe_journal_filename(report.journal_id)}.json"
    payload = report.as_dict()
    payload["saved_at"] = datetime.now().isoformat(timespec="seconds")
    payload["storage_note"] = EXECUTION_JOURNAL_STORAGE_NOTE
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return path


def load_execution_journal_records(
    directory: str | Path | None = None,
    symbol: str | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    journal_dir = Path(directory) if directory is not None else default_execution_journal_dir()
    if not journal_dir.exists():
        return []
    records: list[dict[str, Any]] = []
    for path in journal_dir.glob("*.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if symbol and payload.get("symbol") != symbol:
            continue
        payload["path"] = str(path)
        records.append(payload)
    records.sort(key=lambda row: (str(row.get("saved_at", "")), str(row.get("timestamp", "")), str(row.get("journal_id", ""))), reverse=True)
    return records[: max(0, int(limit))]


def build_execution_journal_history_table(records: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for record in records:
        rows.append(
            {
                "saved_at": record.get("saved_at", ""),
                "journal_id": record.get("journal_id", ""),
                "symbol": record.get("symbol", ""),
                "timestamp": record.get("timestamp", ""),
                "status": record.get("status", ""),
                "action_type": record.get("action_type", ""),
                "manual_fill_count": record.get("manual_fill_count", 0),
                "broker_matched_count": record.get("broker_matched_count", 0),
                "path": record.get("path", ""),
            }
        )
    return rows


def _safe_journal_filename(journal_id: str) -> str:
    safe = str(journal_id)
    for char in '<>:"/\\|?*':
        safe = safe.replace(char, "_")
    return safe[:120] or "execution-journal"
