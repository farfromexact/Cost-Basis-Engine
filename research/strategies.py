from __future__ import annotations

from dataclasses import dataclass

from core.inventory_ledger import InventoryLedger
from core.models import Order, Side, TradePair
from research.features import FeatureRow


@dataclass(frozen=True)
class SellThenBuyConfig:
    trade_qty: int = 100
    sell_deviation: float = 0.003
    buyback_deviation: float = -0.001
    min_amount_ratio: float = 1.05
    latest_open_time: str = "14:35"
    latest_buy_time: str = "14:50"


class SellThenBuyBaselineStrategy:
    def __init__(self, config: SellThenBuyConfig | None = None) -> None:
        self.config = config or SellThenBuyConfig()

    def decide(
        self,
        feature: FeatureRow,
        ledger: InventoryLedger,
        open_pair: TradePair | None,
    ) -> Order | None:
        minute = feature.bar.ts.strftime("%H:%M")
        if open_pair is not None:
            if (
                feature.vwap_deviation <= self.config.buyback_deviation
                or minute >= open_pair.latest_buy_time
            ):
                return Order(
                    ts=feature.bar.ts,
                    side=Side.BUY,
                    qty=open_pair.qty,
                    price=feature.bar.close,
                    reason="buyback_after_vwap_reversion_or_time_stop",
                    pair_id=open_pair.pair_id,
                )
            return None

        if minute >= self.config.latest_open_time:
            return None
        if ledger.available_to_sell < self.config.trade_qty:
            return None
        if feature.vwap_deviation < self.config.sell_deviation:
            return None
        if feature.amount_ratio < self.config.min_amount_ratio:
            return None
        return Order(
            ts=feature.bar.ts,
            side=Side.SELL,
            qty=self.config.trade_qty,
            price=feature.bar.close,
            reason="sell_spike_above_intraday_vwap",
        )
