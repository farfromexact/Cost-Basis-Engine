from __future__ import annotations

import csv
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from app.manual_fills import ManualFill
from core.models import Side


DEFAULT_BROKER_FILL_EXPORT_PATH = Path(".runtime") / "broker_fills.csv"
BROKER_IMPORT_NOTE = (
    "broker import is reconciliation scaffolding only; imported rows are not written "
    "to manual fills and do not create realized PnL or cost-basis claims"
)
BROKER_FILL_PROMOTION_REVIEW_TOKEN = "APPROVE_BROKER_FILL_PROMOTION"


@dataclass(frozen=True)
class BrokerFillExportRow:
    broker_fill_id: str
    symbol: str
    side: Side
    qty: int
    price: float
    ts: str
    fees: float = 0.0
    slippage: float = 0.0
    order_id: str = ""
    pair_id: str = ""
    status: str = "FILLED"
    source: str = "broker_export"

    @classmethod
    def from_dict(cls, payload: dict[str, Any], row_number: int | None = None) -> "BrokerFillExportRow":
        symbol = _required_text(payload, ("symbol", "ticker", "security_code"), "symbol", row_number)
        side = Side(_required_text(payload, ("side", "direction", "buy_sell"), "side", row_number).upper())
        qty = _positive_int(_required_value(payload, ("qty", "quantity", "filled_qty", "volume"), "qty", row_number), "qty", row_number)
        price = _positive_float(_required_value(payload, ("price", "fill_price", "avg_price"), "price", row_number), "price", row_number)
        ts = _required_text(payload, ("ts", "timestamp", "trade_time", "fill_time"), "ts", row_number)
        broker_fill_id = _optional_text(payload, ("broker_fill_id", "fill_id", "execution_id", "exec_id"))
        if not broker_fill_id:
            broker_fill_id = _synthetic_broker_fill_id(symbol, side.value, qty, price, ts, row_number)
        return cls(
            broker_fill_id=broker_fill_id,
            symbol=symbol,
            side=side,
            qty=qty,
            price=price,
            ts=ts,
            fees=_non_negative_float(_optional_value(payload, ("fees", "fee", "commission"), 0.0), "fees", row_number),
            slippage=_non_negative_float(_optional_value(payload, ("slippage", "price_impact"), 0.0), "slippage", row_number),
            order_id=_optional_text(payload, ("order_id", "broker_order_id", "entrust_id")),
            pair_id=_optional_text(payload, ("pair_id", "manual_pair_id")),
            status=(_optional_text(payload, ("status", "fill_status")) or "FILLED").upper(),
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "broker_fill_id": self.broker_fill_id,
            "symbol": self.symbol,
            "side": self.side.value,
            "qty": self.qty,
            "price": self.price,
            "ts": self.ts,
            "fees": self.fees,
            "slippage": self.slippage,
            "order_id": self.order_id,
            "pair_id": self.pair_id,
            "status": self.status,
            "source": self.source,
        }

    @property
    def match_key(self) -> tuple[str, str, int, float, str]:
        return _match_key(self.symbol, self.side, self.qty, self.price, self.ts)


@dataclass(frozen=True)
class BrokerFillReconciliationItem:
    match_key: str
    status: str
    broker_fill_id: str
    manual_fill_id: str
    symbol: str
    side: str
    qty: int
    price: float
    ts: str
    detail: str
    operator_action: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "match_key": self.match_key,
            "status": self.status,
            "broker_fill_id": self.broker_fill_id,
            "manual_fill_id": self.manual_fill_id,
            "symbol": self.symbol,
            "side": self.side,
            "qty": self.qty,
            "price": self.price,
            "ts": self.ts,
            "detail": self.detail,
            "operator_action": self.operator_action,
        }


@dataclass(frozen=True)
class BrokerImportReconciliationReport:
    status: str
    summary: str
    symbol: str
    broker_fill_count: int
    manual_fill_count: int
    matched_count: int
    broker_only_count: int
    manual_only_count: int
    ambiguous_count: int
    items: tuple[BrokerFillReconciliationItem, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "summary": self.summary,
            "symbol": self.symbol,
            "broker_fill_count": self.broker_fill_count,
            "manual_fill_count": self.manual_fill_count,
            "matched_count": self.matched_count,
            "broker_only_count": self.broker_only_count,
            "manual_only_count": self.manual_only_count,
            "ambiguous_count": self.ambiguous_count,
            "items": [item.as_dict() for item in self.items],
            "capability_note": BROKER_IMPORT_NOTE,
        }


@dataclass(frozen=True)
class BrokerFillPromotionPreview:
    status: str
    summary: str
    broker_fill_id: str
    pair_id: str
    manual_fill_id: str
    symbol: str
    side: str
    qty: int
    price: float
    ts: str
    checks: tuple[BrokerFillReconciliationItem, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "summary": self.summary,
            "broker_fill_id": self.broker_fill_id,
            "pair_id": self.pair_id,
            "manual_fill_id": self.manual_fill_id,
            "symbol": self.symbol,
            "side": self.side,
            "qty": self.qty,
            "price": self.price,
            "ts": self.ts,
            "checks": [check.as_dict() for check in self.checks],
            "required_review_token": BROKER_FILL_PROMOTION_REVIEW_TOKEN,
            "capability_note": "promotion preview only unless the exact review token is supplied",
        }


def build_broker_fill_promotion_preview(
    manual_fills: Iterable[ManualFill],
    broker_fills: Iterable[BrokerFillExportRow],
    broker_fill_id: str,
    pair_id: str | None,
    review_token: str | None = None,
) -> BrokerFillPromotionPreview:
    broker_rows = [fill for fill in broker_fills if fill.broker_fill_id == broker_fill_id]
    manual_rows = list(manual_fills)
    empty_broker = BrokerFillExportRow(
        broker_fill_id=broker_fill_id,
        symbol="",
        side=Side.BUY,
        qty=1,
        price=1.0,
        ts="",
    )
    broker_fill = broker_rows[0] if broker_rows else empty_broker
    manual_fill_id = _manual_fill_id_from_broker(broker_fill, pair_id or "")
    checks: list[BrokerFillReconciliationItem] = []

    if len(broker_rows) != 1:
        checks.append(_promotion_check("broker_fill_id", "BLOCKED", broker_fill, pair_id or "", f"Expected exactly one broker fill id {broker_fill_id}; found {len(broker_rows)}.", "Resolve broker export identity before promotion."))
    if not pair_id:
        checks.append(_promotion_check("pair_assignment", "BLOCKED", broker_fill, pair_id or "", "No pair_id was supplied for the broker fill.", "Assign the fill to an explicit strategy pair before promotion."))
    if broker_rows and _manual_key_exists(manual_rows, broker_fill.match_key):
        checks.append(_promotion_check("manual_duplicate", "BLOCKED", broker_fill, pair_id or "", "A manual fill already exists with the same symbol/side/qty/price/timestamp key.", "Do not promote a duplicate broker row."))
    if broker_rows and any(fill.fill_id == manual_fill_id for fill in manual_rows):
        checks.append(_promotion_check("manual_fill_id", "BLOCKED", broker_fill, pair_id or "", f"Manual fill id {manual_fill_id} already exists.", "Use the existing manual fill or resolve duplicate ids."))
    if review_token != BROKER_FILL_PROMOTION_REVIEW_TOKEN:
        checks.append(_promotion_check("review_token", "REVIEW_REQUIRED", broker_fill, pair_id or "", "Exact broker-fill promotion review token has not been supplied.", "Preview only; supply the token after checking pair assignment."))

    hard_block = any(check.status == "BLOCKED" for check in checks)
    if hard_block:
        status = "BLOCKED"
    elif any(check.status == "REVIEW_REQUIRED" for check in checks):
        status = "REVIEW_REQUIRED"
    else:
        status = "READY"
        checks.append(_promotion_check("ready", "OK", broker_fill, pair_id or "", "Broker fill is broker-only, pair-assigned, and review token is valid.", "Promotion can write one manual fill."))
    return BrokerFillPromotionPreview(
        status=status,
        summary=_promotion_summary(status, broker_fill_id, pair_id or ""),
        broker_fill_id=broker_fill_id,
        pair_id=pair_id or "",
        manual_fill_id=manual_fill_id,
        symbol=broker_fill.symbol,
        side=broker_fill.side.value,
        qty=broker_fill.qty,
        price=broker_fill.price,
        ts=broker_fill.ts,
        checks=tuple(checks),
    )


def promote_broker_fill_after_review(
    manual_fills: Iterable[ManualFill],
    broker_fills: Iterable[BrokerFillExportRow],
    broker_fill_id: str,
    pair_id: str,
    review_token: str,
    note: str = "Broker-confirmed fill promoted after operator review.",
) -> ManualFill:
    broker_rows = list(broker_fills)
    preview = build_broker_fill_promotion_preview(manual_fills, broker_rows, broker_fill_id, pair_id, review_token)
    if preview.status != "READY":
        raise ValueError(preview.summary)
    broker_fill = next(fill for fill in broker_rows if fill.broker_fill_id == broker_fill_id)
    return ManualFill(
        fill_id=preview.manual_fill_id,
        symbol=broker_fill.symbol,
        pair_id=pair_id,
        side=broker_fill.side,
        qty=broker_fill.qty,
        price=broker_fill.price,
        ts=broker_fill.ts,
        fees=broker_fill.fees,
        slippage=broker_fill.slippage,
        source="manual",
        note=f"{note} broker_fill_id={broker_fill.broker_fill_id}; order_id={broker_fill.order_id or 'N/A'}",
        recorded_at="",
    )

def default_broker_fill_export_path() -> Path:
    override = os.getenv("CBE_BROKER_FILL_EXPORT_PATH")
    return Path(override) if override else DEFAULT_BROKER_FILL_EXPORT_PATH


def supported_broker_fill_columns() -> tuple[str, ...]:
    return (
        "broker_fill_id",
        "order_id",
        "symbol",
        "side",
        "qty",
        "price",
        "ts",
        "fees",
        "slippage",
        "pair_id",
        "status",
    )


def load_broker_fill_export(path: str | Path) -> list[BrokerFillExportRow]:
    export_path = Path(path)
    if not export_path.exists():
        raise ValueError(f"broker fill export does not exist: {export_path}")
    suffix = export_path.suffix.lower()
    if suffix == ".json":
        return _load_json_export(export_path)
    if suffix in {".csv", ".txt"}:
        return _load_csv_export(export_path)
    raise ValueError(f"unsupported broker fill export extension: {suffix}; use .csv or .json")


def reconcile_manual_fills_with_broker_export(
    manual_fills: Iterable[ManualFill],
    broker_fills: Iterable[BrokerFillExportRow],
    symbol: str | None = None,
) -> BrokerImportReconciliationReport:
    manual_rows = [fill for fill in manual_fills if symbol is None or fill.symbol == symbol]
    broker_rows = [fill for fill in broker_fills if symbol is None or fill.symbol == symbol]
    manual_by_key = _group_by_key((_manual_match_key(fill), fill) for fill in manual_rows)
    broker_by_key = _group_by_key((fill.match_key, fill) for fill in broker_rows)

    items: list[BrokerFillReconciliationItem] = []
    for key in sorted(set(manual_by_key) | set(broker_by_key), key=_key_sort_text):
        manual_matches = manual_by_key.get(key, [])
        broker_matches = broker_by_key.get(key, [])
        items.append(_reconciliation_item(key, manual_matches, broker_matches))

    matched_count = sum(1 for item in items if item.status == "MATCHED")
    broker_only_count = sum(1 for item in items if item.status == "BROKER_ONLY")
    manual_only_count = sum(1 for item in items if item.status == "MANUAL_ONLY")
    ambiguous_count = sum(1 for item in items if item.status == "AMBIGUOUS")
    status = _report_status(items, len(broker_rows), len(manual_rows))
    return BrokerImportReconciliationReport(
        status=status,
        summary=_summary(status, symbol or "ALL", matched_count, broker_only_count, manual_only_count, ambiguous_count),
        symbol=symbol or "ALL",
        broker_fill_count=len(broker_rows),
        manual_fill_count=len(manual_rows),
        matched_count=matched_count,
        broker_only_count=broker_only_count,
        manual_only_count=manual_only_count,
        ambiguous_count=ambiguous_count,
        items=tuple(items),
    )


def _load_json_export(path: Path) -> list[BrokerFillExportRow]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid broker fill JSON: {path}") from exc
    rows = payload.get("fills") if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        raise ValueError("broker fill JSON must be a list or an object with a 'fills' list")
    return [BrokerFillExportRow.from_dict(row, index + 1) for index, row in enumerate(rows)]


def _load_csv_export(path: Path) -> list[BrokerFillExportRow]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError(f"broker fill CSV has no header: {path}")
        return [BrokerFillExportRow.from_dict(row, index + 2) for index, row in enumerate(reader)]


def _group_by_key(rows) -> dict[tuple[str, str, int, float, str], list[Any]]:
    grouped: dict[tuple[str, str, int, float, str], list[Any]] = {}
    for key, row in rows:
        grouped.setdefault(key, []).append(row)
    return grouped


def _reconciliation_item(
    key: tuple[str, str, int, float, str],
    manual_matches: list[ManualFill],
    broker_matches: list[BrokerFillExportRow],
) -> BrokerFillReconciliationItem:
    symbol, side, qty, price, ts = key
    if len(manual_matches) > 1 or len(broker_matches) > 1:
        return BrokerFillReconciliationItem(
            _key_text(key),
            "AMBIGUOUS",
            ",".join(fill.broker_fill_id for fill in broker_matches),
            ",".join(fill.fill_id for fill in manual_matches),
            symbol,
            side,
            qty,
            price,
            ts,
            "Duplicate manual or broker rows share the same reconciliation key.",
            "Resolve duplicates before importing or trusting this fill set.",
        )
    if manual_matches and broker_matches:
        return BrokerFillReconciliationItem(
            _key_text(key),
            "MATCHED",
            broker_matches[0].broker_fill_id,
            manual_matches[0].fill_id,
            symbol,
            side,
            qty,
            price,
            ts,
            "Manual fill matches a broker-confirmed export row on symbol/side/qty/price/timestamp.",
            "No action required.",
        )
    if broker_matches:
        return BrokerFillReconciliationItem(
            _key_text(key),
            "BROKER_ONLY",
            broker_matches[0].broker_fill_id,
            "",
            symbol,
            side,
            qty,
            price,
            ts,
            "Broker export contains a fill that is not present in manual fills.",
            "Review the broker row and record/import it as a manual fill only after confirming pair context.",
        )
    return BrokerFillReconciliationItem(
        _key_text(key),
        "MANUAL_ONLY",
        "",
        manual_matches[0].fill_id,
        symbol,
        side,
        qty,
        price,
        ts,
        "Manual fill has no matching broker export row.",
        "Verify the broker export date/account or wait for broker confirmation before relying on the fill.",
    )


def _manual_key_exists(manual_fills: list[ManualFill], key: tuple[str, str, int, float, str]) -> bool:
    return any(_manual_match_key(fill) == key for fill in manual_fills)


def _manual_fill_id_from_broker(broker_fill: BrokerFillExportRow, pair_id: str) -> str:
    raw = f"manual-from-broker-{broker_fill.broker_fill_id}-{pair_id}"
    return "".join(char if char.isalnum() or char in {"-", "_"} else "-" for char in raw)[:180]


def _promotion_check(check: str, status: str, broker_fill: BrokerFillExportRow, pair_id: str, detail: str, operator_action: str) -> BrokerFillReconciliationItem:
    return BrokerFillReconciliationItem(
        match_key=check,
        status=status,
        broker_fill_id=broker_fill.broker_fill_id,
        manual_fill_id=_manual_fill_id_from_broker(broker_fill, pair_id),
        symbol=broker_fill.symbol,
        side=broker_fill.side.value,
        qty=broker_fill.qty,
        price=broker_fill.price,
        ts=broker_fill.ts,
        detail=detail,
        operator_action=operator_action,
    )


def _promotion_summary(status: str, broker_fill_id: str, pair_id: str) -> str:
    prefix = f"Broker fill promotion preview for {broker_fill_id} into pair {pair_id or 'UNASSIGNED'}."
    if status == "READY":
        return prefix + " Ready to write one manual fill."
    if status == "BLOCKED":
        return prefix + " Promotion is blocked; resolve checks before writing."
    return prefix + " Review token is required before writing."

def _report_status(items: list[BrokerFillReconciliationItem], broker_count: int, manual_count: int) -> str:
    if broker_count == 0 and manual_count == 0:
        return "NO_DATA"
    statuses = {item.status for item in items}
    if "AMBIGUOUS" in statuses:
        return "BLOCKED"
    if "BROKER_ONLY" in statuses or "MANUAL_ONLY" in statuses:
        return "WARN"
    return "OK"


def _summary(status: str, symbol: str, matched: int, broker_only: int, manual_only: int, ambiguous: int) -> str:
    prefix = f"Broker fill reconciliation for {symbol}: matched {matched}, broker-only {broker_only}, manual-only {manual_only}, ambiguous {ambiguous}."
    if status == "OK":
        return prefix + " Manual fills are reconciled to the imported broker export."
    if status == "BLOCKED":
        return prefix + " Duplicate reconciliation keys must be resolved before use."
    if status == "NO_DATA":
        return prefix + " No manual or broker fill rows are available."
    return prefix + " Review unmatched rows before using fills as broker-confirmed execution evidence."


def _manual_match_key(fill: ManualFill) -> tuple[str, str, int, float, str]:
    return _match_key(fill.symbol, fill.side, fill.qty, fill.price, fill.ts)


def _match_key(symbol: str, side: Side, qty: int, price: float, ts: str) -> tuple[str, str, int, float, str]:
    return (str(symbol), side.value, int(qty), round(float(price), 4), _normalize_ts(ts))


def _normalize_ts(value: str) -> str:
    return str(value).strip().replace("T", " ")[:19]


def _key_text(key: tuple[str, str, int, float, str]) -> str:
    symbol, side, qty, price, ts = key
    return f"{symbol}|{side}|{qty}|{price:.4f}|{ts}"


def _key_sort_text(key: tuple[str, str, int, float, str]) -> str:
    return _key_text(key)


def _required_value(payload: dict[str, Any], names: tuple[str, ...], label: str, row_number: int | None) -> Any:
    value = _optional_value(payload, names, None)
    if value in (None, ""):
        where = f" on row {row_number}" if row_number else ""
        raise ValueError(f"broker fill export missing required {label}{where}")
    return value


def _required_text(payload: dict[str, Any], names: tuple[str, ...], label: str, row_number: int | None) -> str:
    return str(_required_value(payload, names, label, row_number)).strip()


def _optional_value(payload: dict[str, Any], names: tuple[str, ...], default: Any = None) -> Any:
    normalized = {str(key).strip().lower(): value for key, value in payload.items()}
    for name in names:
        value = normalized.get(name.lower())
        if value not in (None, ""):
            return value
    return default


def _optional_text(payload: dict[str, Any], names: tuple[str, ...]) -> str:
    value = _optional_value(payload, names, "")
    return str(value).strip() if value not in (None, "") else ""


def _positive_int(value: Any, label: str, row_number: int | None) -> int:
    try:
        parsed = int(float(value))
    except (TypeError, ValueError) as exc:
        where = f" on row {row_number}" if row_number else ""
        raise ValueError(f"broker fill export has invalid {label}{where}: {value}") from exc
    if parsed <= 0:
        where = f" on row {row_number}" if row_number else ""
        raise ValueError(f"broker fill export requires positive {label}{where}: {value}")
    return parsed


def _positive_float(value: Any, label: str, row_number: int | None) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        where = f" on row {row_number}" if row_number else ""
        raise ValueError(f"broker fill export has invalid {label}{where}: {value}") from exc
    if parsed <= 0:
        where = f" on row {row_number}" if row_number else ""
        raise ValueError(f"broker fill export requires positive {label}{where}: {value}")
    return parsed


def _non_negative_float(value: Any, label: str, row_number: int | None) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        where = f" on row {row_number}" if row_number else ""
        raise ValueError(f"broker fill export has invalid {label}{where}: {value}") from exc
    if parsed < 0:
        where = f" on row {row_number}" if row_number else ""
        raise ValueError(f"broker fill export requires non-negative {label}{where}: {value}")
    return parsed


def _synthetic_broker_fill_id(symbol: str, side: str, qty: int, price: float, ts: str, row_number: int | None) -> str:
    suffix = f"row{row_number}" if row_number else "row"
    safe_ts = _normalize_ts(ts).replace(":", "").replace(" ", "T")
    return f"broker-{symbol}-{side}-{qty}-{price:.4f}-{safe_ts}-{suffix}"