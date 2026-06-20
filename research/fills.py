from __future__ import annotations

from core.fee_model import FeeModel
from datetime import datetime

from core.models import Fill, Order, Side


def fill_at_next_open(
    order: Order,
    next_open: float,
    fee_model: FeeModel,
    fill_ts: datetime | None = None,
) -> Fill:
    effective_price = next_open
    breakdown = fee_model.calculate(order.side, effective_price, order.qty)
    return Fill(
        ts=fill_ts or order.ts,
        side=order.side,
        qty=order.qty,
        price=effective_price,
        fees=breakdown.total_fees,
        slippage=breakdown.slippage,
        reason=order.reason,
        pair_id=order.pair_id,
    )


def try_limit_fill_on_next_bar(order: Order, next_low: float, next_high: float, fee_model: FeeModel) -> Fill | None:
    if order.side is Side.BUY and next_low <= order.price:
        breakdown = fee_model.calculate(order.side, order.price, order.qty)
    elif order.side is Side.SELL and next_high >= order.price:
        breakdown = fee_model.calculate(order.side, order.price, order.qty)
    else:
        return None
    return Fill(
        ts=order.ts,
        side=order.side,
        qty=order.qty,
        price=order.price,
        fees=breakdown.total_fees,
        slippage=breakdown.slippage,
        reason=order.reason,
        pair_id=order.pair_id,
    )
