from datetime import datetime, timedelta

from core.models import MinuteBar
from research.risk_limits import rules_with_risk_limit_preset
from research.trigger_engine import ActionType, PositionState, RulesConfig, TriggerEngine, zero_fee_model


def test_defensive_risk_preset_caps_trigger_sizing_and_wait_time() -> None:
    rules = rules_with_risk_limit_preset(
        RulesConfig(
            max_t_ratio=0.10,
            sb_trigger_deviation=0.003,
            sb_watch_deviation=0.002,
            risk_buffer_pct=0.0,
            min_amount_ratio=1.0,
        ),
        "defensive",
    )
    intent = TriggerEngine(rules, zero_fee_model()).evaluate(
        "TEST",
        _bars([10.0, 10.0, 10.0, 10.12]),
        PositionState(target_qty=10000, current_total_qty=10000, settled_sellable_qty=10000, purchasable_qty=10000),
    )

    assert intent.action_type is ActionType.TRIGGER_SELL_TO_BUY
    assert intent.suggested_qty == 500
    assert intent.max_wait_minutes == 25
    assert intent.inventory_decision is not None
    assert any("Risk preset caps" in reason for reason in intent.inventory_decision.reasons)


def _bars(closes: list[float]) -> list[MinuteBar]:
    start = datetime(2026, 6, 18, 10, 0)
    bars = []
    previous = closes[0]
    for index, close in enumerate(closes):
        volume = 100_000 if index < len(closes) - 1 else 250_000
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