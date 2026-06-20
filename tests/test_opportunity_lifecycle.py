from datetime import datetime, timedelta

from core.models import MinuteBar
from research.opportunity_lifecycle import LIFECYCLE_NOTE, scan_opportunity_lifecycle
from research.trigger_engine import PositionState, RulesConfig, zero_fee_model


def test_lifecycle_marks_close_ready_without_inferred_fill() -> None:
    events = scan_opportunity_lifecycle(
        "TEST",
        _bars([10.0, 10.0, 10.0, 10.12, 10.03]),
        _position(),
        rules=RulesConfig(max_t_ratio=0.10),
        fee_model=zero_fee_model(),
    )

    states = [event.state for event in events]
    assert states == ["OPEN", "CLOSE_READY"]
    assert events[-1].note == LIFECYCLE_NOTE
    assert "close readiness only" in events[-1].reason


def test_lifecycle_expires_open_opportunity_after_wait_limit() -> None:
    events = scan_opportunity_lifecycle(
        "TEST",
        _bars([10.0, 10.0, 10.0, 10.12, 10.13, 10.14]),
        _position(),
        rules=RulesConfig(max_t_ratio=0.10, max_wait_minutes=2),
        fee_model=zero_fee_model(),
    )

    assert [event.state for event in events] == ["OPEN", "EXPIRED"]


def test_lifecycle_blocks_opportunity_at_invalidation() -> None:
    events = scan_opportunity_lifecycle(
        "TEST",
        _bars([10.0, 10.0, 10.0, 10.12, 10.15]),
        _position(),
        rules=RulesConfig(max_t_ratio=0.10),
        fee_model=zero_fee_model(),
    )

    assert [event.state for event in events] == ["OPEN", "BLOCKED"]
    assert "invalidation" in events[-1].reason


def test_lifecycle_collapses_continuous_same_side_triggers() -> None:
    events = scan_opportunity_lifecycle(
        "TEST",
        _bars([10.0, 10.0, 10.15, 10.16, 10.17, 10.18]),
        _position(),
        rules=RulesConfig(max_t_ratio=0.10),
        fee_model=zero_fee_model(),
        marker_cooldown_minutes=10,
    )

    trigger_events = [event for event in events if event.level == "Trigger"]
    assert [event.signal for event in trigger_events] == ["SB"]


def _position() -> PositionState:
    return PositionState(
        target_qty=1000,
        current_total_qty=1000,
        settled_sellable_qty=1000,
        purchasable_qty=1000,
    )


def _bars(closes: list[float]) -> list[MinuteBar]:
    start = datetime(2026, 6, 19, 10, 0)
    bars: list[MinuteBar] = []
    previous = closes[0]
    for index, close in enumerate(closes):
        volume = 250_000 if index >= 2 else 100_000
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
