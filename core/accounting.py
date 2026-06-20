from __future__ import annotations

from dataclasses import dataclass

from core.inventory_ledger import InventoryLedger
from core.models import Fill, InventorySnapshot, Side, TradePair


@dataclass(frozen=True)
class EvaluationMetrics:
    closed_t_net_pnl: float
    excess_pnl_vs_hold: float
    ending_quantity_delta: int
    eod_inventory_restoration_rate: float
    unclosed_pair_rate: float
    total_fees: float
    estimated_slippage: float
    turnover: float
    max_inventory_deviation: int
    max_inventory_deviation_duration: int
    missed_upside_tail: float
    added_downside_tail: float
    max_drawdown: float
    trade_count: int
    net_pnl_per_10k_turnover: float

    def as_dict(self) -> dict[str, float | int]:
        return self.__dict__.copy()


def evaluate(
    ledger: InventoryLedger,
    fills: list[Fill],
    closed_pairs: list[TradePair],
    open_pairs: list[TradePair],
    eod_price: float,
) -> EvaluationMetrics:
    closed_t_net_pnl = sum(pair.realized_net_pnl() for pair in closed_pairs)
    ending_quantity_delta = ledger.current_total_qty - ledger.target_qty
    total_pairs = len(closed_pairs) + len(open_pairs)
    unclosed_pair_rate = len(open_pairs) / total_pairs if total_pairs else 0.0
    total_fees = sum(fill.fees for fill in fills)
    estimated_slippage = sum(fill.slippage for fill in fills)
    turnover = sum(fill.gross_value for fill in fills)
    excess_pnl_vs_hold = ledger.cash_available + ending_quantity_delta * eod_price
    restoration = 1.0
    if ledger.target_qty:
        restoration = max(0.0, 1.0 - abs(ending_quantity_delta) / ledger.target_qty)

    max_dev, max_dev_duration = _inventory_deviation(ledger.target_qty, ledger.snapshots)
    missed_upside_tail = sum(
        max(0.0, eod_price - pair.open_fill.price) * pair.qty for pair in open_pairs
    )
    added_downside_tail = 0.0
    max_drawdown = _cash_curve_drawdown(fills)
    net_per_10k = closed_t_net_pnl / turnover * 10000 if turnover else 0.0
    return EvaluationMetrics(
        closed_t_net_pnl=round(closed_t_net_pnl, 6),
        excess_pnl_vs_hold=round(excess_pnl_vs_hold, 6),
        ending_quantity_delta=ending_quantity_delta,
        eod_inventory_restoration_rate=round(restoration, 6),
        unclosed_pair_rate=round(unclosed_pair_rate, 6),
        total_fees=round(total_fees, 6),
        estimated_slippage=round(estimated_slippage, 6),
        turnover=round(turnover, 6),
        max_inventory_deviation=max_dev,
        max_inventory_deviation_duration=max_dev_duration,
        missed_upside_tail=round(missed_upside_tail, 6),
        added_downside_tail=round(added_downside_tail, 6),
        max_drawdown=round(max_drawdown, 6),
        trade_count=len(fills),
        net_pnl_per_10k_turnover=round(net_per_10k, 6),
    )


def _inventory_deviation(
    target_qty: int,
    snapshots: list[InventorySnapshot],
) -> tuple[int, int]:
    max_dev = 0
    current_duration = 0
    max_duration = 0
    for snapshot in snapshots:
        dev = abs(snapshot.current_total_qty - target_qty)
        max_dev = max(max_dev, dev)
        if dev:
            current_duration += 1
            max_duration = max(max_duration, current_duration)
        else:
            current_duration = 0
    return max_dev, max_duration


def _cash_curve_drawdown(fills: list[Fill]) -> float:
    cash = 0.0
    peak = 0.0
    max_drawdown = 0.0
    for fill in fills:
        cash += fill.cash_delta
        if fill.side is Side.SELL:
            peak = max(peak, cash)
        max_drawdown = min(max_drawdown, cash - peak)
    return abs(max_drawdown)
