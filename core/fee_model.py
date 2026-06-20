from __future__ import annotations

from dataclasses import dataclass

from core.models import Side


@dataclass(frozen=True)
class FeeConfig:
    buy_commission_rate: float = 0.00025
    sell_commission_rate: float = 0.00025
    min_commission: float = 5.0
    stamp_tax_rate: float = 0.0005
    transfer_fee_rate: float = 0.00001
    other_fee_rate: float = 0.0
    buy_slippage_rate: float = 0.0001
    sell_slippage_rate: float = 0.0001


@dataclass(frozen=True)
class FeeBreakdown:
    commission: float
    stamp_tax: float
    transfer_fee: float
    other_fee: float
    slippage: float

    @property
    def total_fees(self) -> float:
        return self.commission + self.stamp_tax + self.transfer_fee + self.other_fee


class FeeModel:
    def __init__(self, config: FeeConfig | None = None) -> None:
        self.config = config or FeeConfig()

    def calculate(self, side: Side, price: float, qty: int) -> FeeBreakdown:
        if price <= 0:
            raise ValueError("price must be positive")
        if qty <= 0:
            raise ValueError("qty must be positive")

        gross = price * qty
        commission_rate = (
            self.config.buy_commission_rate
            if side is Side.BUY
            else self.config.sell_commission_rate
        )
        commission = max(gross * commission_rate, self.config.min_commission)
        stamp_tax = gross * self.config.stamp_tax_rate if side is Side.SELL else 0.0
        transfer_fee = gross * self.config.transfer_fee_rate
        other_fee = gross * self.config.other_fee_rate
        slippage_rate = (
            self.config.buy_slippage_rate
            if side is Side.BUY
            else self.config.sell_slippage_rate
        )
        slippage = gross * slippage_rate
        return FeeBreakdown(
            commission=commission,
            stamp_tax=stamp_tax,
            transfer_fee=transfer_fee,
            other_fee=other_fee,
            slippage=slippage,
        )
