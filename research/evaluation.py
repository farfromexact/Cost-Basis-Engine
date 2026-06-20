from __future__ import annotations

from dataclasses import dataclass

from core.accounting import EvaluationMetrics


@dataclass(frozen=True)
class BaselineComparison:
    no_trade_excess_pnl: float
    strategy_excess_pnl: float
    strategy_closed_t_net_pnl: float
    ending_quantity_delta: int


def compare_to_no_trade(metrics: EvaluationMetrics) -> BaselineComparison:
    return BaselineComparison(
        no_trade_excess_pnl=0.0,
        strategy_excess_pnl=metrics.excess_pnl_vs_hold,
        strategy_closed_t_net_pnl=metrics.closed_t_net_pnl,
        ending_quantity_delta=metrics.ending_quantity_delta,
    )
