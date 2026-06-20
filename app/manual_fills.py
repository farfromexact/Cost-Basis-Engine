from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from core.models import Side


DEFAULT_MANUAL_FILLS_PATH = Path(".runtime") / "manual_fills.json"
MANUAL_FILL_NOTE = "Manual fill only; no fills are inferred from signals, chart markers, or lifecycle states."


@dataclass(frozen=True)
class ManualFill:
    fill_id: str
    symbol: str
    pair_id: str
    side: Side
    qty: int
    price: float
    ts: str
    fees: float = 0.0
    slippage: float = 0.0
    source: str = "manual"
    note: str = MANUAL_FILL_NOTE
    recorded_at: str = ""

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ManualFill":
        return cls(
            fill_id=str(payload["fill_id"]),
            symbol=str(payload["symbol"]),
            pair_id=str(payload["pair_id"]),
            side=Side(str(payload["side"]).upper()),
            qty=_positive_int(payload["qty"], "qty"),
            price=_positive_float(payload["price"], "price"),
            ts=str(payload["ts"]),
            fees=_non_negative_float(payload.get("fees", 0.0), "fees"),
            slippage=_non_negative_float(payload.get("slippage", 0.0), "slippage"),
            source=str(payload.get("source") or "manual"),
            note=str(payload.get("note") or MANUAL_FILL_NOTE),
            recorded_at=str(payload.get("recorded_at") or ""),
        )

    def __post_init__(self) -> None:
        _positive_int(self.qty, "qty")
        _positive_float(self.price, "price")
        _non_negative_float(self.fees, "fees")
        _non_negative_float(self.slippage, "slippage")
        if self.source != "manual":
            raise ValueError("manual fill recorder only accepts source='manual'")

    def as_dict(self) -> dict[str, Any]:
        return {
            "fill_id": self.fill_id,
            "symbol": self.symbol,
            "pair_id": self.pair_id,
            "side": self.side.value,
            "qty": self.qty,
            "price": self.price,
            "ts": self.ts,
            "fees": self.fees,
            "slippage": self.slippage,
            "source": self.source,
            "note": self.note,
            "recorded_at": self.recorded_at,
        }

    @property
    def cash_delta(self) -> float:
        gross = self.qty * self.price
        if self.side is Side.SELL:
            return gross - self.fees - self.slippage
        return -gross - self.fees - self.slippage


@dataclass(frozen=True)
class ChecklistItem:
    step: str
    status: str
    detail: str

    def as_dict(self) -> dict[str, str]:
        return {"step": self.step, "status": self.status, "detail": self.detail}


@dataclass(frozen=True)
class ExecutionChecklist:
    pair_id: str
    status: str
    items: list[ChecklistItem]
    note: str = MANUAL_FILL_NOTE

    def as_dict(self) -> dict[str, Any]:
        return {
            "pair_id": self.pair_id,
            "status": self.status,
            "items": [item.as_dict() for item in self.items],
            "note": self.note,
        }


def default_manual_fills_path() -> Path:
    override = os.getenv("CBE_MANUAL_FILLS_PATH")
    return Path(override) if override else DEFAULT_MANUAL_FILLS_PATH


def load_manual_fills(path: str | Path | None = None) -> list[ManualFill]:
    fill_path = Path(path) if path is not None else default_manual_fills_path()
    if not fill_path.exists():
        return []
    try:
        payload = json.loads(fill_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid manual fills JSON: {fill_path}") from exc
    if not isinstance(payload, list):
        raise ValueError(f"Manual fills file must contain a JSON list: {fill_path}")
    return [ManualFill.from_dict(item) for item in payload]


def save_manual_fills(fills: list[ManualFill], path: str | Path | None = None) -> Path:
    fill_path = Path(path) if path is not None else default_manual_fills_path()
    fill_path.parent.mkdir(parents=True, exist_ok=True)
    fill_path.write_text(
        json.dumps([fill.as_dict() for fill in fills], ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return fill_path


def record_manual_fill(fill: ManualFill, path: str | Path | None = None) -> Path:
    fills = load_manual_fills(path)
    if any(existing.fill_id == fill.fill_id for existing in fills):
        raise ValueError(f"duplicate manual fill id: {fill.fill_id}")
    fills.append(fill)
    return save_manual_fills(fills, path)


def make_manual_fill(
    symbol: str,
    pair_id: str,
    side: str | Side,
    qty: int,
    price: float,
    ts: str | None = None,
    fees: float = 0.0,
    slippage: float = 0.0,
    note: str = MANUAL_FILL_NOTE,
) -> ManualFill:
    timestamp = ts or datetime.now().isoformat(timespec="seconds")
    normalized_side = side if isinstance(side, Side) else Side(str(side).upper())
    fill_id = f"manual-{_safe_id(symbol)}-{_safe_id(pair_id)}-{normalized_side.value}-{timestamp.replace(':', '').replace(' ', 'T')}"
    return ManualFill(
        fill_id=fill_id,
        symbol=symbol,
        pair_id=pair_id,
        side=normalized_side,
        qty=qty,
        price=price,
        ts=timestamp,
        fees=fees,
        slippage=slippage,
        note=note,
        recorded_at=datetime.now().isoformat(timespec="seconds"),
    )


def manual_pair_id(symbol: str, open_pair_side: str | None, open_pair_price: float | None, open_pair_qty: int | None) -> str:
    side = (open_pair_side or "NONE").upper()
    price_text = f"{float(open_pair_price or 0):.4f}".replace(".", "p")
    qty_text = str(int(open_pair_qty or 0))
    return f"{_safe_id(symbol)}-{side}-{price_text}-{qty_text}"


def expected_open_side(open_pair_side: str | None) -> Side | None:
    side = (open_pair_side or "").upper()
    if side == "SB":
        return Side.SELL
    if side == "BS":
        return Side.BUY
    return None


def expected_close_side(open_pair_side: str | None) -> Side | None:
    side = (open_pair_side or "").upper()
    if side == "SB":
        return Side.BUY
    if side == "BS":
        return Side.SELL
    return None


def expected_next_fill_side(open_pair_side: str | None, fills: list[ManualFill], pair_id: str) -> Side | None:
    if _matching_fill(fills, pair_id, expected_close_side(open_pair_side)):
        return None
    if _matching_fill(fills, pair_id, expected_open_side(open_pair_side)):
        return expected_close_side(open_pair_side)
    return expected_open_side(open_pair_side)


def fills_for_pair(fills: list[ManualFill], pair_id: str) -> list[ManualFill]:
    return [fill for fill in fills if fill.pair_id == pair_id]


def build_execution_checklist(
    symbol: str,
    open_pair_side: str | None,
    open_pair_price: float | None,
    open_pair_qty: int | None,
    fills: list[ManualFill],
) -> ExecutionChecklist:
    pair_id = manual_pair_id(symbol, open_pair_side, open_pair_price, open_pair_qty)
    if not open_pair_side:
        return ExecutionChecklist(
            pair_id=pair_id,
            status="NO_OPEN_PAIR",
            items=[ChecklistItem("Select open pair", "WAITING", "No open pair is currently selected.")],
        )

    open_side = expected_open_side(open_pair_side)
    close_side = expected_close_side(open_pair_side)
    open_fill = _matching_fill(fills, pair_id, open_side)
    close_fill = _matching_fill(fills, pair_id, close_side)
    pair_fills = fills_for_pair(fills, pair_id)

    if close_fill:
        status = "MANUAL_CLOSE_RECORDED"
    elif open_fill:
        status = "AWAITING_MANUAL_CLOSE_FILL"
    else:
        status = "MISSING_MANUAL_OPEN_FILL"

    return ExecutionChecklist(
        pair_id=pair_id,
        status=status,
        items=[
            ChecklistItem(
                "Confirm open-pair context",
                "DONE",
                f"{open_pair_side} pair {pair_id}; qty={int(open_pair_qty or 0)}, first price={float(open_pair_price or 0):.4f}.",
            ),
            ChecklistItem(
                "Record first-leg fill manually",
                "DONE" if open_fill else "REQUIRED",
                _fill_detail(open_fill) if open_fill else f"Expected manual {open_side.value if open_side else 'UNKNOWN'} fill; signals do not count.",
            ),
            ChecklistItem(
                "Wait for close/restore decision",
                "INFO",
                "Use TradeIntent and lifecycle markers as decision support only; do not infer execution.",
            ),
            ChecklistItem(
                "Record close/restore fill manually",
                "DONE" if close_fill else "REQUIRED",
                _fill_detail(close_fill) if close_fill else f"Expected manual {close_side.value if close_side else 'UNKNOWN'} fill before any close/PnL claim.",
            ),
            ChecklistItem(
                "Verify fees, slippage, and inventory restoration",
                "DONE" if close_fill and len(pair_fills) >= 2 else "BLOCKED",
                "Both manual legs are recorded." if close_fill and len(pair_fills) >= 2 else "Cost-basis reduction is unverified until both manual legs and costs are recorded.",
            ),
        ],
    )


def _matching_fill(fills: list[ManualFill], pair_id: str, side: Side | None) -> ManualFill | None:
    if side is None:
        return None
    for fill in fills:
        if fill.pair_id == pair_id and fill.side is side:
            return fill
    return None


def _fill_detail(fill: ManualFill | None) -> str:
    if fill is None:
        return "Missing manual fill."
    return f"{fill.side.value} {fill.qty} @ {fill.price:.4f}; fees={fill.fees:.4f}; slippage={fill.slippage:.4f}; ts={fill.ts}."


def _safe_id(value: str) -> str:
    return "".join(char if char.isalnum() else "_" for char in str(value)).strip("_") or "unknown"


def _positive_int(value: Any, name: str) -> int:
    number = int(value)
    if number <= 0:
        raise ValueError(f"{name} must be positive")
    return number


def _positive_float(value: Any, name: str) -> float:
    number = float(value)
    if number <= 0:
        raise ValueError(f"{name} must be positive")
    return number


def _non_negative_float(value: Any, name: str) -> float:
    number = float(value)
    if number < 0:
        raise ValueError(f"{name} must be non-negative")
    return number
