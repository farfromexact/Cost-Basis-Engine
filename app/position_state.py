from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from core.fee_profiles import DEFAULT_A_SHARE_FEE_PROFILE_ID, ZERO_FEE_PROFILE_ID, normalize_fee_profile_id
from research.risk_limits import DEFAULT_RISK_LIMIT_PRESET_ID, risk_limit_preset


DEFAULT_POSITION_STATE_PATH = Path(".runtime") / "position_state.json"


@dataclass(frozen=True)
class PositionSnapshot:
    market_source: str = "A-share / Eastmoney"
    symbol: str = "603236"
    held_qty: int = 151400
    settled_sellable_qty: int = 151400
    purchasable_qty: int = 15100
    max_t_ratio: float = 0.10
    max_single_trade_qty: int | None = None
    risk_limit_preset_id: str = DEFAULT_RISK_LIMIT_PRESET_ID
    fee_profile_id: str = DEFAULT_A_SHARE_FEE_PROFILE_ID
    ignore_fees: bool = False
    open_pair_side: str | None = None
    open_pair_price: float | None = None
    open_pair_qty: int | None = None
    updated_at: str = ""

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "PositionSnapshot":
        open_pair_side = _optional_side(payload.get("open_pair_side"))
        fee_profile_id = payload.get("fee_profile_id")
        ignore_fees = bool(payload.get("ignore_fees", False))
        if not fee_profile_id and ignore_fees:
            fee_profile_id = ZERO_FEE_PROFILE_ID
        return cls(
            market_source=str(payload.get("market_source") or cls.market_source),
            symbol=str(payload.get("symbol") or cls.symbol),
            held_qty=_non_negative_int(payload.get("held_qty"), cls.held_qty),
            settled_sellable_qty=_non_negative_int(payload.get("settled_sellable_qty"), cls.settled_sellable_qty),
            purchasable_qty=_non_negative_int(payload.get("purchasable_qty"), cls.purchasable_qty),
            max_t_ratio=_positive_float(payload.get("max_t_ratio"), cls.max_t_ratio),
            max_single_trade_qty=_optional_non_negative_int(payload.get("max_single_trade_qty")),
            risk_limit_preset_id=risk_limit_preset(payload.get("risk_limit_preset_id")).preset_id,
            fee_profile_id=normalize_fee_profile_id(fee_profile_id or cls.fee_profile_id, payload.get("market_source")),
            ignore_fees=ignore_fees,
            open_pair_side=open_pair_side,
            open_pair_price=_optional_positive_float(payload.get("open_pair_price")),
            open_pair_qty=_optional_non_negative_int(payload.get("open_pair_qty")),
            updated_at=str(payload.get("updated_at") or ""),
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "market_source": self.market_source,
            "symbol": self.symbol,
            "held_qty": self.held_qty,
            "settled_sellable_qty": self.settled_sellable_qty,
            "purchasable_qty": self.purchasable_qty,
            "max_t_ratio": self.max_t_ratio,
            "max_single_trade_qty": self.max_single_trade_qty,
            "risk_limit_preset_id": self.risk_limit_preset_id,
            "fee_profile_id": self.fee_profile_id,
            "ignore_fees": self.ignore_fees,
            "open_pair_side": self.open_pair_side,
            "open_pair_price": self.open_pair_price,
            "open_pair_qty": self.open_pair_qty,
            "updated_at": self.updated_at,
        }


def default_position_state_path() -> Path:
    override = os.getenv("CBE_POSITION_STATE_PATH")
    return Path(override) if override else DEFAULT_POSITION_STATE_PATH


def load_position_snapshot(path: str | Path | None = None) -> PositionSnapshot | None:
    state_path = Path(path) if path is not None else default_position_state_path()
    if not state_path.exists():
        return None
    try:
        payload = json.loads(state_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid position state JSON: {state_path}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"Position state must be a JSON object: {state_path}")
    return PositionSnapshot.from_dict(payload)


def save_position_snapshot(snapshot: PositionSnapshot, path: str | Path | None = None) -> Path:
    state_path = Path(path) if path is not None else default_position_state_path()
    state_path.parent.mkdir(parents=True, exist_ok=True)
    payload = snapshot.as_dict()
    payload["updated_at"] = datetime.now().isoformat(timespec="seconds")
    state_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return state_path


def _optional_side(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip().upper()
    if not text or text == "NONE":
        return None
    if text not in {"SB", "BS"}:
        raise ValueError("open_pair_side must be SB, BS, or None")
    return text


def _non_negative_int(value: Any, default: int) -> int:
    if value is None:
        return default
    number = int(value)
    if number < 0:
        raise ValueError("quantity fields must be non-negative")
    return number


def _optional_non_negative_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    number = int(value)
    if number <= 0:
        return None
    return number


def _positive_float(value: Any, default: float) -> float:
    if value is None:
        return default
    number = float(value)
    if number <= 0:
        raise ValueError("ratio fields must be positive")
    return number


def _optional_positive_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    number = float(value)
    if number <= 0:
        return None
    return number
