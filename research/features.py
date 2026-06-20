from __future__ import annotations

from dataclasses import dataclass

from core.models import MinuteBar


@dataclass(frozen=True)
class FeatureRow:
    bar: MinuteBar
    vwap: float
    vwap_deviation: float
    amount_ratio: float
    close_to_open_return: float


def build_features(bars: list[MinuteBar]) -> list[FeatureRow]:
    rows: list[FeatureRow] = []
    cumulative_amount = 0.0
    cumulative_volume = 0
    amount_history: list[float] = []
    for bar in bars:
        cumulative_amount += bar.amount
        cumulative_volume += bar.volume
        vwap = cumulative_amount / cumulative_volume if cumulative_volume else bar.close
        avg_amount = sum(amount_history[-20:]) / min(len(amount_history), 20) if amount_history else bar.amount
        amount_ratio = bar.amount / avg_amount if avg_amount else 1.0
        rows.append(
            FeatureRow(
                bar=bar,
                vwap=vwap,
                vwap_deviation=(bar.close / vwap - 1.0) if vwap else 0.0,
                amount_ratio=amount_ratio,
                close_to_open_return=bar.close / bar.open - 1.0,
            )
        )
        amount_history.append(bar.amount)
    return rows
