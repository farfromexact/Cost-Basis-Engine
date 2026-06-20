from __future__ import annotations

from dataclasses import dataclass

from core.accounting import EvaluationMetrics, evaluate
from core.fee_model import FeeModel
from core.inventory_ledger import InventoryLedger
from core.models import Fill, Order, Side, TradePair
from core.pair_state_machine import PairBook
from data.validation import validate_minute_bars
from research.features import build_features
from research.fills import fill_at_next_open
from research.strategies import SellThenBuyBaselineStrategy


@dataclass
class ReplayResult:
    fills: list[Fill]
    closed_pairs: list[TradePair]
    open_pairs: list[TradePair]
    metrics: EvaluationMetrics


def replay_sell_then_buy(
    bars,
    ledger: InventoryLedger,
    strategy: SellThenBuyBaselineStrategy,
    fee_model: FeeModel | None = None,
) -> ReplayResult:
    validate_minute_bars(bars)
    fee_model = fee_model or FeeModel()
    features = build_features(bars)
    pair_book = PairBook()
    fills: list[Fill] = []

    for index, feature in enumerate(features[:-1]):
        ledger.record_snapshot(feature.bar.ts)
        open_pair = pair_book.first_open()
        order = strategy.decide(feature, ledger, open_pair)
        if order is None:
            continue
        if order.side is Side.SELL:
            if not _passes_round_trip_cost_gate(order, strategy, fee_model):
                continue
            order = Order(
                ts=order.ts,
                side=order.side,
                qty=order.qty,
                price=order.price,
                reason=order.reason,
                pair_id=f"SB-{pair_book.next_id:04d}",
            )

        next_bar = bars[index + 1]
        fill = _simulate_next_open_fill(order, next_bar.open, next_bar.ts, fee_model)
        ledger.apply_fill(fill)
        fills.append(fill)
        if fill.side is Side.SELL:
            pair_book.open_sell_then_buy(
                fill,
                planned_buy_price=fill.price * (1.0 + strategy.config.buyback_deviation),
                latest_buy_time=strategy.config.latest_buy_time,
            )
        else:
            if fill.pair_id is None:
                raise ValueError("buy fill must reference an open pair")
            pair_book.close_pair(fill.pair_id, fill)
    ledger.record_snapshot(bars[-1].ts)

    metrics = evaluate(
        ledger=ledger,
        fills=fills,
        closed_pairs=pair_book.closed_pairs,
        open_pairs=pair_book.open_pairs,
        eod_price=bars[-1].close,
    )
    return ReplayResult(
        fills=fills,
        closed_pairs=pair_book.closed_pairs,
        open_pairs=pair_book.open_pairs,
        metrics=metrics,
    )


def _passes_round_trip_cost_gate(
    order: Order,
    strategy: SellThenBuyBaselineStrategy,
    fee_model: FeeModel,
) -> bool:
    planned_buy_price = order.price * (1.0 + strategy.config.buyback_deviation)
    sell_cost = fee_model.calculate(Side.SELL, order.price, order.qty)
    buy_cost = fee_model.calculate(Side.BUY, planned_buy_price, order.qty)
    expected_gross_edge = (order.price - planned_buy_price) * order.qty
    expected_cost = (
        sell_cost.total_fees
        + sell_cost.slippage
        + buy_cost.total_fees
        + buy_cost.slippage
    )
    return expected_gross_edge > expected_cost


def _simulate_next_open_fill(order: Order, next_open: float, fill_ts, fee_model: FeeModel) -> Fill:
    order_at_fill_time = Order(
        ts=order.ts,
        side=order.side,
        qty=order.qty,
        price=next_open,
        reason=order.reason,
        pair_id=order.pair_id,
    )
    return fill_at_next_open(order_at_fill_time, next_open, fee_model, fill_ts=fill_ts)
