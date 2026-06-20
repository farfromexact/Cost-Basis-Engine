from datetime import datetime, timedelta

from core.models import MinuteBar
from research.trigger_engine import (
    ActionType,
    PositionState,
    RegimeType,
    RulesConfig,
    TriggerEngine,
    zero_fee_model,
)


def test_default_state_is_no_trade_when_deviation_is_small() -> None:
    intent = _engine().evaluate(
        "TEST",
        _bars([10.0, 10.0, 10.01, 10.0]),
        _position(),
    )

    assert intent.action_type is ActionType.NO_TRADE


def test_regime_block_prevents_trade_before_start_time() -> None:
    intent = _engine().evaluate(
        "TEST",
        _bars([10.0, 10.0, 10.2], start_hour=9, start_minute=31),
        _position(),
    )

    assert intent.action_type is ActionType.NO_TRADE
    assert intent.regime_type is RegimeType.NO_TRADE


def test_trend_up_suppresses_sell_to_buy() -> None:
    intent = _engine().evaluate(
        "TEST",
        _bars([10.0, 10.08, 10.16, 10.28, 10.42, 10.55]),
        _position(),
    )

    assert intent.action_type is ActionType.WATCH_SELL_TO_BUY
    assert intent.regime_type is RegimeType.TREND_UP


def test_trend_down_suppresses_buy_to_sell() -> None:
    intent = _engine().evaluate(
        "TEST",
        _bars([10.0, 9.92, 9.84, 9.74, 9.62, 9.5]),
        _position(purchasable_qty=1000),
    )

    assert intent.action_type is ActionType.WATCH_BUY_TO_SELL
    assert intent.regime_type is RegimeType.TREND_DOWN


def test_vwap_deviation_with_insufficient_net_edge_only_watches() -> None:
    engine = TriggerEngine(RulesConfig(risk_buffer_pct=0.0))
    intent = engine.evaluate(
        "TEST",
        _bars([10.0, 10.0, 10.0, 10.08]),
        _position(target_qty=1000, settled_sellable_qty=1000),
    )

    assert intent.action_type is ActionType.WATCH_SELL_TO_BUY
    assert intent.estimated_net_edge <= 0
def test_deviation_below_trigger_threshold_only_watches() -> None:
    intent = _engine().evaluate(
        "TEST",
        _bars([10.0, 10.0, 10.0, 10.04]),
        _position(),
    )

    assert intent.action_type is ActionType.WATCH_SELL_TO_BUY
    assert intent.estimated_net_edge > 0
    assert any("deviation strength" in blocker for blocker in intent.blockers)


def test_strong_deviation_with_weak_liquidity_only_watches() -> None:
    engine = TriggerEngine(
        RulesConfig(
            sb_trigger_deviation=0.003,
            sb_watch_deviation=0.002,
            risk_buffer_pct=0.0,
            min_amount_ratio=1.2,
        ),
        zero_fee_model(),
    )
    intent = engine.evaluate(
        "TEST",
        _bars([10.0, 10.0, 10.0, 10.12], final_volume=50_000),
        _position(),
    )

    assert intent.action_type is ActionType.WATCH_SELL_TO_BUY
    assert intent.deviation_decision is not None
    assert intent.deviation_decision.deviation_score >= 1.0
    assert any("liquidity confirmation" in blocker for blocker in intent.blockers)


def test_sell_to_buy_triggers_when_regime_deviation_and_inventory_pass() -> None:
    intent = _engine().evaluate(
        "TEST",
        _bars([10.0, 10.0, 10.0, 10.12]),
        _position(),
    )

    assert intent.action_type is ActionType.TRIGGER_SELL_TO_BUY
    assert intent.suggested_qty == 100
    assert intent.expected_reversion_price < intent.reference_price


def test_buy_to_sell_triggers_when_regime_deviation_and_inventory_pass() -> None:
    intent = _engine().evaluate(
        "TEST",
        _bars([10.0, 10.0, 10.0, 9.88]),
        _position(purchasable_qty=1000),
    )

    assert intent.action_type is ActionType.TRIGGER_BUY_TO_SELL
    assert intent.suggested_qty == 100
    assert intent.expected_reversion_price > intent.reference_price


def test_sell_to_buy_rejected_when_settled_sellable_is_insufficient() -> None:
    intent = _engine().evaluate(
        "TEST",
        _bars([10.0, 10.0, 10.0, 10.12]),
        _position(settled_sellable_qty=0),
    )

    assert intent.action_type is ActionType.NO_TRADE
    assert any("sellable quantity" in blocker or "settled" in blocker for blocker in intent.blockers)


def test_buy_to_sell_rejected_when_purchasable_qty_is_insufficient() -> None:
    intent = _engine().evaluate(
        "TEST",
        _bars([10.0, 10.0, 10.0, 9.88]),
        _position(purchasable_qty=0),
    )

    assert intent.action_type is ActionType.NO_TRADE
    assert any("Purchasable quantity" in blocker for blocker in intent.blockers)


def test_open_pair_takes_priority_over_new_signal() -> None:
    intent = _engine().evaluate(
        "TEST",
        _bars([10.0, 10.0, 10.0, 10.12]),
        _position(open_pair_side="SB", open_pair_price=10.2, open_pair_qty=100),
    )

    assert intent.action_type is ActionType.MANAGE_OPEN_PAIR
    assert intent.suggested_qty == 100


def test_late_open_pair_forces_restore() -> None:
    intent = _engine().evaluate(
        "TEST",
        _bars([10.0, 10.0, 9.9], start_hour=14, start_minute=50),
        _position(open_pair_side="SB", open_pair_price=10.2, open_pair_qty=100),
    )

    assert intent.action_type is ActionType.FORCE_CLOSE_OR_RESTORE


def test_trade_intent_output_fields_are_complete() -> None:
    payload = _engine().evaluate(
        "TEST",
        _bars([10.0, 10.0, 10.0, 10.12]),
        _position(),
    ).as_dict()

    required = {
        "action_type",
        "symbol",
        "timestamp",
        "side",
        "suggested_qty",
        "reference_price",
        "expected_reversion_price",
        "estimated_net_edge",
        "confidence",
        "regime_type",
        "reasons",
        "blockers",
        "warnings",
        "next_action",
    }
    assert required.issubset(payload)


def _engine() -> TriggerEngine:
    return TriggerEngine(
        RulesConfig(
            sb_trigger_deviation=0.003,
            sb_watch_deviation=0.002,
            bs_trigger_deviation=-0.003,
            bs_watch_deviation=-0.002,
            risk_buffer_pct=0.0,
            min_amount_ratio=1.0,
            trend_day_return_pct=0.02,
            trend_recent_return_pct=0.004,
        ),
        zero_fee_model(),
    )


def _position(
    target_qty: int = 1000,
    current_total_qty: int = 1000,
    settled_sellable_qty: int = 1000,
    purchasable_qty: int = 1000,
    open_pair_side: str | None = None,
    open_pair_price: float | None = None,
    open_pair_qty: int | None = None,
) -> PositionState:
    return PositionState(
        target_qty=target_qty,
        current_total_qty=current_total_qty,
        settled_sellable_qty=settled_sellable_qty,
        purchasable_qty=purchasable_qty,
        open_pair_side=open_pair_side,
        open_pair_price=open_pair_price,
        open_pair_qty=open_pair_qty,
    )


def _bars(
    closes: list[float],
    start_hour: int = 10,
    start_minute: int = 0,
    final_volume: int | None = None,
) -> list[MinuteBar]:
    start = datetime(2026, 6, 18, start_hour, start_minute)
    bars: list[MinuteBar] = []
    previous = closes[0]
    for index, close in enumerate(closes):
        volume = final_volume if index == len(closes) - 1 and final_volume is not None else 100_000 if index < len(closes) - 1 else 250_000
        bars.append(
            MinuteBar(
                ts=start + timedelta(minutes=index),
                open=previous,
                high=max(previous, close) + 0.01,
                low=min(previous, close) - 0.01,
                close=close,
                volume=volume,
                amount=volume * close,
            )
        )
        previous = close
    return bars



