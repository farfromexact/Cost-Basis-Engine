from __future__ import annotations

from dataclasses import dataclass, field

from core.models import Fill, PairStatus, Side, TradePair


@dataclass
class PairBook:
    open_pairs: list[TradePair] = field(default_factory=list)
    closed_pairs: list[TradePair] = field(default_factory=list)
    expired_pairs: list[TradePair] = field(default_factory=list)
    next_id: int = 1

    def open_sell_then_buy(
        self,
        sell_fill: Fill,
        planned_buy_price: float,
        latest_buy_time: str,
    ) -> TradePair:
        if sell_fill.side is not Side.SELL:
            raise ValueError("S->B pair must open with a SELL fill")
        pair_id = sell_fill.pair_id or f"SB-{self.next_id:04d}"
        self.next_id += 1
        pair = TradePair(
            pair_id=pair_id,
            open_fill=sell_fill,
            planned_buy_price=planned_buy_price,
            latest_buy_time=latest_buy_time,
        )
        self.open_pairs.append(pair)
        return pair

    def close_pair(self, pair_id: str, buy_fill: Fill) -> TradePair:
        pair = self.get_open(pair_id)
        pair.close(buy_fill)
        self.open_pairs.remove(pair)
        self.closed_pairs.append(pair)
        return pair

    def expire_pair(self, pair_id: str) -> TradePair:
        pair = self.get_open(pair_id)
        pair.status = PairStatus.EXPIRED
        self.open_pairs.remove(pair)
        self.expired_pairs.append(pair)
        return pair

    def get_open(self, pair_id: str) -> TradePair:
        for pair in self.open_pairs:
            if pair.pair_id == pair_id:
                return pair
        raise KeyError(f"open pair not found: {pair_id}")

    def first_open(self) -> TradePair | None:
        return self.open_pairs[0] if self.open_pairs else None
