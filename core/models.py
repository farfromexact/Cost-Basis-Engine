from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class Side(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class PairStatus(str, Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    EXPIRED = "EXPIRED"


@dataclass(frozen=True)
class MinuteBar:
    ts: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    amount: float

    @property
    def avg_price(self) -> float:
        if self.volume > 0 and self.amount > 0:
            return self.amount / self.volume
        return self.close


@dataclass(frozen=True)
class Order:
    ts: datetime
    side: Side
    qty: int
    price: float
    reason: str
    pair_id: str | None = None


@dataclass(frozen=True)
class Fill:
    ts: datetime
    side: Side
    qty: int
    price: float
    fees: float
    slippage: float
    reason: str
    pair_id: str | None = None

    @property
    def gross_value(self) -> float:
        return self.price * self.qty

    @property
    def cash_delta(self) -> float:
        if self.side is Side.SELL:
            return self.gross_value - self.fees - self.slippage
        return -self.gross_value - self.fees - self.slippage


@dataclass
class InventorySnapshot:
    ts: datetime
    current_total_qty: int
    settled_sellable_qty: int
    today_bought_locked_qty: int
    cash: float


@dataclass
class TradePair:
    pair_id: str
    open_fill: Fill
    planned_buy_price: float
    latest_buy_time: str
    close_fill: Fill | None = None
    status: PairStatus = PairStatus.OPEN
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def qty(self) -> int:
        return self.open_fill.qty

    @property
    def is_closed(self) -> bool:
        return self.status is PairStatus.CLOSED and self.close_fill is not None

    def close(self, fill: Fill) -> None:
        if fill.side is not Side.BUY:
            raise ValueError("S->B pair can only close with a BUY fill")
        if fill.qty != self.open_fill.qty:
            raise ValueError("Closing fill quantity must match opening fill quantity")
        self.close_fill = fill
        self.status = PairStatus.CLOSED

    def realized_net_pnl(self) -> float:
        if not self.is_closed or self.close_fill is None:
            return 0.0
        return self.open_fill.cash_delta + self.close_fill.cash_delta
