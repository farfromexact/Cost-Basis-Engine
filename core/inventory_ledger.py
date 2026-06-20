from __future__ import annotations

from dataclasses import dataclass, field

from core.models import Fill, InventorySnapshot, Side


@dataclass
class InventoryLedger:
    target_qty: int
    settled_sellable_qty: int
    cash_available: float = 0.0
    today_bought_locked_qty: int = 0
    reserved_qty: int = 0
    pending_order_qty: int = 0
    snapshots: list[InventorySnapshot] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.target_qty < 0 or self.settled_sellable_qty < 0:
            raise ValueError("inventory quantities cannot be negative")
        self.record_snapshot_ts = None

    @property
    def current_total_qty(self) -> int:
        return self.settled_sellable_qty + self.today_bought_locked_qty

    @property
    def available_to_sell(self) -> int:
        return max(0, self.settled_sellable_qty - self.reserved_qty - self.pending_order_qty)

    def apply_fill(self, fill: Fill) -> None:
        if fill.side is Side.SELL:
            if fill.qty > self.available_to_sell:
                raise ValueError("cannot sell more than settled sellable quantity")
            self.settled_sellable_qty -= fill.qty
        else:
            self.today_bought_locked_qty += fill.qty
        self.cash_available += fill.cash_delta
        self.record_snapshot(fill.ts)

    def record_snapshot(self, ts) -> None:
        snapshot = InventorySnapshot(
            ts=ts,
            current_total_qty=self.current_total_qty,
            settled_sellable_qty=self.settled_sellable_qty,
            today_bought_locked_qty=self.today_bought_locked_qty,
            cash=self.cash_available,
        )
        if self.snapshots and self.snapshots[-1].ts == ts:
            self.snapshots[-1] = snapshot
            return
        self.snapshots.append(
            snapshot
        )

    def settle_new_day(self) -> None:
        self.settled_sellable_qty += self.today_bought_locked_qty
        self.today_bought_locked_qty = 0
