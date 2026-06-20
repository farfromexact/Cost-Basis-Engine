from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from app.position_state import PositionSnapshot


DEFAULT_POSITION_RECONCILIATION_PATH = Path(".runtime") / "position_reconciliation.json"


@dataclass(frozen=True)
class BrokerPositionSnapshot:
    market_source: str
    symbol: str
    total_qty: int
    sellable_qty: int
    purchasable_qty: int
    cash_available: float = 0.0
    source: str = "manual_broker_snapshot"
    as_of: str = ""
    recorded_at: str = ""
    note: str = ""

    def __post_init__(self) -> None:
        if not str(self.market_source).strip():
            raise ValueError("market_source is required")
        if not str(self.symbol).strip():
            raise ValueError("symbol is required")
        _non_negative_int(self.total_qty, "total_qty")
        _non_negative_int(self.sellable_qty, "sellable_qty")
        _non_negative_int(self.purchasable_qty, "purchasable_qty")
        _non_negative_float(self.cash_available, "cash_available")
        if self.sellable_qty > self.total_qty:
            raise ValueError("sellable_qty cannot exceed total_qty")

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "BrokerPositionSnapshot":
        return cls(
            market_source=str(payload.get("market_source") or ""),
            symbol=str(payload.get("symbol") or ""),
            total_qty=_non_negative_int(payload.get("total_qty"), "total_qty"),
            sellable_qty=_non_negative_int(payload.get("sellable_qty"), "sellable_qty"),
            purchasable_qty=_non_negative_int(payload.get("purchasable_qty"), "purchasable_qty"),
            cash_available=_non_negative_float(payload.get("cash_available", 0.0), "cash_available"),
            source=str(payload.get("source") or "manual_broker_snapshot"),
            as_of=str(payload.get("as_of") or ""),
            recorded_at=str(payload.get("recorded_at") or ""),
            note=str(payload.get("note") or ""),
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "market_source": self.market_source,
            "symbol": self.symbol,
            "total_qty": self.total_qty,
            "sellable_qty": self.sellable_qty,
            "purchasable_qty": self.purchasable_qty,
            "cash_available": self.cash_available,
            "source": self.source,
            "as_of": self.as_of,
            "recorded_at": self.recorded_at,
            "note": self.note,
        }


@dataclass(frozen=True)
class ReconciliationItem:
    field: str
    persisted_value: str
    broker_value: str
    delta: str
    status: str
    operator_action: str

    def as_dict(self) -> dict[str, str]:
        return {
            "field": self.field,
            "persisted_value": self.persisted_value,
            "broker_value": self.broker_value,
            "delta": self.delta,
            "status": self.status,
            "operator_action": self.operator_action,
        }


@dataclass(frozen=True)
class PositionReconciliationReport:
    status: str
    summary: str
    persisted_symbol: str
    broker_symbol: str
    broker_as_of: str
    items: tuple[ReconciliationItem, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "summary": self.summary,
            "persisted_symbol": self.persisted_symbol,
            "broker_symbol": self.broker_symbol,
            "broker_as_of": self.broker_as_of,
            "items": [item.as_dict() for item in self.items],
        }


def default_position_reconciliation_path() -> Path:
    override = os.getenv("CBE_POSITION_RECONCILIATION_PATH")
    return Path(override) if override else DEFAULT_POSITION_RECONCILIATION_PATH


def load_broker_position_snapshot(path: str | Path | None = None) -> BrokerPositionSnapshot | None:
    snapshot_path = Path(path) if path is not None else default_position_reconciliation_path()
    if not snapshot_path.exists():
        return None
    try:
        payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid broker reconciliation JSON: {snapshot_path}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"Broker reconciliation must be a JSON object: {snapshot_path}")
    return BrokerPositionSnapshot.from_dict(payload)


def save_broker_position_snapshot(snapshot: BrokerPositionSnapshot, path: str | Path | None = None) -> Path:
    snapshot_path = Path(path) if path is not None else default_position_reconciliation_path()
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    payload = snapshot.as_dict()
    payload["recorded_at"] = datetime.now().isoformat(timespec="seconds")
    snapshot_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return snapshot_path


def reconcile_position_state(
    persisted: PositionSnapshot,
    broker: BrokerPositionSnapshot | None,
) -> PositionReconciliationReport:
    if broker is None:
        item = ReconciliationItem(
            field="broker_snapshot",
            persisted_value=persisted.symbol,
            broker_value="missing",
            delta="n/a",
            status="MISSING",
            operator_action="Record a broker-confirmed snapshot before relying on persisted holdings.",
        )
        return PositionReconciliationReport(
            status="MISSING",
            summary="No broker-confirmed/manual snapshot has been recorded for reconciliation.",
            persisted_symbol=persisted.symbol,
            broker_symbol="",
            broker_as_of="",
            items=(item,),
        )

    items = [
        _identity_item("market_source", persisted.market_source, broker.market_source),
        _identity_item("symbol", persisted.symbol, broker.symbol),
        _quantity_item("held_qty", persisted.held_qty, broker.total_qty, "Update held quantity from broker before sizing trades."),
        _quantity_item(
            "settled_sellable_qty",
            persisted.settled_sellable_qty,
            broker.sellable_qty,
            "Update sellable quantity from broker before any sell-first action.",
        ),
        _quantity_item(
            "purchasable_qty",
            persisted.purchasable_qty,
            broker.purchasable_qty,
            "Update purchasable quantity/cash assumptions from broker before any buy-first action.",
        ),
    ]
    status = _worst_status(item.status for item in items)
    if status == "OK":
        summary = "Persisted position state matches the broker/manual snapshot for symbol, market, and tradeable quantities."
    elif status == "BLOCKED":
        summary = "Persisted state overstates or mismatches broker-confirmed constraints; block live action until reconciled."
    else:
        summary = "Persisted state differs from broker/manual snapshot; reconcile before treating sizing as current."
    return PositionReconciliationReport(
        status=status,
        summary=summary,
        persisted_symbol=persisted.symbol,
        broker_symbol=broker.symbol,
        broker_as_of=broker.as_of,
        items=tuple(items),
    )


def _identity_item(field: str, persisted_value: str, broker_value: str) -> ReconciliationItem:
    persisted_text = str(persisted_value)
    broker_text = str(broker_value)
    if persisted_text == broker_text:
        return ReconciliationItem(field, persisted_text, broker_text, "0", "OK", "No action required.")
    return ReconciliationItem(
        field=field,
        persisted_value=persisted_text,
        broker_value=broker_text,
        delta="mismatch",
        status="BLOCKED",
        operator_action="Switch to the broker-confirmed market/symbol before using guidance.",
    )


def _quantity_item(field: str, persisted_qty: int, broker_qty: int, action: str) -> ReconciliationItem:
    delta = int(persisted_qty) - int(broker_qty)
    if delta == 0:
        return ReconciliationItem(field, str(persisted_qty), str(broker_qty), "0", "OK", "No action required.")
    if delta > 0:
        status = "BLOCKED"
        operator_action = action + " Persisted state is higher than broker-confirmed capacity."
    else:
        status = "WARN"
        operator_action = action + " Persisted state is lower than broker-confirmed capacity."
    return ReconciliationItem(field, str(persisted_qty), str(broker_qty), str(delta), status, operator_action)


def _worst_status(statuses) -> str:
    values = set(statuses)
    if "BLOCKED" in values:
        return "BLOCKED"
    if "WARN" in values:
        return "WARN"
    if "MISSING" in values:
        return "MISSING"
    return "OK"


def _non_negative_int(value: Any, field_name: str) -> int:
    if value in (None, ""):
        raise ValueError(f"{field_name} is required")
    number = int(value)
    if number < 0:
        raise ValueError(f"{field_name} must be non-negative")
    return number


def _non_negative_float(value: Any, field_name: str) -> float:
    if value in (None, ""):
        return 0.0
    number = float(value)
    if number < 0:
        raise ValueError(f"{field_name} must be non-negative")
    return number
