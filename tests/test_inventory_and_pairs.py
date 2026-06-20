from datetime import datetime

import pytest

from core.inventory_ledger import InventoryLedger
from core.models import Fill, Side
from core.pair_state_machine import PairBook


def fill(side: Side, qty: int, price: float, pair_id: str | None = None) -> Fill:
    return Fill(
        ts=datetime(2026, 1, 2, 9, 31),
        side=side,
        qty=qty,
        price=price,
        fees=1.0,
        slippage=0.5,
        reason="test",
        pair_id=pair_id,
    )


def test_today_bought_quantity_is_not_sellable_same_day() -> None:
    ledger = InventoryLedger(target_qty=1000, settled_sellable_qty=1000)
    ledger.apply_fill(fill(Side.BUY, 100, 10.0))

    assert ledger.today_bought_locked_qty == 100
    assert ledger.available_to_sell == 1000


def test_cannot_sell_more_than_settled_sellable_quantity() -> None:
    ledger = InventoryLedger(target_qty=1000, settled_sellable_qty=100)

    with pytest.raises(ValueError):
        ledger.apply_fill(fill(Side.SELL, 200, 10.0))


def test_first_leg_updates_inventory_state() -> None:
    ledger = InventoryLedger(target_qty=1000, settled_sellable_qty=1000)
    ledger.apply_fill(fill(Side.SELL, 100, 10.1))

    assert ledger.settled_sellable_qty == 900
    assert ledger.current_total_qty == 900
    assert ledger.cash_available > 0


def test_second_leg_closes_pair_and_realizes_net_pnl() -> None:
    pair_book = PairBook()
    sell = fill(Side.SELL, 100, 10.1, pair_id="SB-1")
    pair_book.open_sell_then_buy(sell, planned_buy_price=10.0, latest_buy_time="14:50")

    buy = fill(Side.BUY, 100, 9.9, pair_id="SB-1")
    closed = pair_book.close_pair("SB-1", buy)

    assert closed.is_closed
    assert closed.realized_net_pnl() > 0


def test_unclosed_pair_does_not_count_as_realized_reduction() -> None:
    pair_book = PairBook()
    sell = fill(Side.SELL, 100, 10.1, pair_id="SB-1")
    pair = pair_book.open_sell_then_buy(sell, planned_buy_price=10.0, latest_buy_time="14:50")

    assert pair.realized_net_pnl() == 0.0
