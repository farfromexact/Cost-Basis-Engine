from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class InstrumentRules:
    exchange: str = "SSE_OR_SZSE"
    board: str = "MAIN"
    security_type: str = "A_SHARE_COMMON_STOCK"
    effective_date: date | None = None
    tick_size: float = 0.01
    min_lot_size: int = 100
    price_limit_pct: float = 0.10
    special_treatment: bool = False

    def validate_qty(self, qty: int) -> None:
        if qty <= 0:
            raise ValueError("quantity must be positive")
        if qty % self.min_lot_size != 0:
            raise ValueError(f"quantity must be a multiple of {self.min_lot_size}")

    def validate_price(self, price: float) -> None:
        if price <= 0:
            raise ValueError("price must be positive")
        ticks = round(price / self.tick_size)
        if abs(price - ticks * self.tick_size) > 1e-9:
            raise ValueError(f"price must align to tick size {self.tick_size}")
