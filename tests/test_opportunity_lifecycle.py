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
    assert states == ["ENTER", "EXIT"]
    assert [event.debug_state for event in events] == ["PROBE", "CLOSE_READY"]
    assert events[-1].note == LIFECYCLE_NOTE
    assert "close readiness only" in events[-1].reason
    assert events[0].reason_codes
    assert events[0].why_not_earlier
    payload = events[0].as_dict()
    assert "deviation_bps" in payload
    assert payload["deviation_bps"] == payload["vwap_deviation_bps"]


def test_lifecycle_expires_open_opportunity_after_wait_limit() -> None:
    events = scan_opportunity_lifecycle(
        "TEST",
        _bars([10.0, 10.0, 10.0, 10.12, 10.13, 10.14]),
        _position(),
        rules=RulesConfig(max_t_ratio=0.10, max_wait_minutes=2),
        fee_model=zero_fee_model(),
    )

    assert [event.state for event in events] == ["ENTER", "ABORT"]
    assert [event.debug_state for event in events] == ["PROBE", "EXPIRED"]


def test_lifecycle_blocks_opportunity_at_invalidation() -> None:
    events = scan_opportunity_lifecycle(
        "TEST",
        _bars([10.0, 10.0, 10.0, 10.12, 10.15]),
        _position(),
        rules=RulesConfig(max_t_ratio=0.10),
        fee_model=zero_fee_model(),
    )

    assert [event.state for event in events] == ["ENTER", "ABORT"]
    assert [event.debug_state for event in events] == ["PROBE", "BLOCKED"]
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

    trigger_events = [event for event in events if event.state == "ENTER"]
    assert [event.signal for event in trigger_events] == ["SB"]


def test_lifecycle_does_not_auto_add_by_default() -> None:
    events = scan_opportunity_lifecycle(
        "TEST",
        _bars([10.0, 10.0, 9.88, 9.87, 9.84]),
        _position(),
        rules=RulesConfig(
            max_t_ratio=0.10,
            bs_trigger_deviation=-0.002,
            bs_watch_deviation=-0.001,
            min_amount_ratio=1.0,
            risk_buffer_pct=0.0,
            trend_day_return_pct=1.0,
            trend_recent_return_pct=1.0,
            max_lifecycle_legs=3,
            max_lifecycle_total_t_ratio=0.30,
            min_lifecycle_leg_spacing_minutes=2,
            min_lifecycle_price_improvement_pct=0.002,
        ),
        fee_model=zero_fee_model(),
    )

    assert "ADD" not in [event.debug_state for event in events]


def test_lifecycle_adds_same_side_leg_only_when_enabled_and_inside_bounds() -> None:
    events = scan_opportunity_lifecycle(
        "TEST",
        _bars([10.0, 10.0, 9.88, 9.87, 9.84]),
        _position(),
        rules=RulesConfig(
            max_t_ratio=0.10,
            bs_trigger_deviation=-0.002,
            bs_watch_deviation=-0.001,
            min_amount_ratio=1.0,
            risk_buffer_pct=0.0,
            trend_day_return_pct=1.0,
            trend_recent_return_pct=1.0,
            enable_auto_add=True,
            max_lifecycle_legs=3,
            max_lifecycle_total_t_ratio=0.30,
            min_lifecycle_leg_spacing_minutes=2,
            min_lifecycle_price_improvement_pct=0.002,
        ),
        fee_model=zero_fee_model(),
    )

    assert [event.state for event in events] == ["ENTER", "ENTER"]
    assert [event.debug_state for event in events] == ["PROBE", "ADD"]
    assert events[-1].leg_count == 2
    assert events[-1].total_suggested_qty == 200
    assert events[-1].max_total_suggested_qty == 300
    assert events[-1].minutes_since_last_leg == 2
    assert events[-1].add_price_improvement_pct >= 0.002
    assert "total T qty 200/300" in events[-1].reason


def test_lifecycle_blocks_add_when_total_t_cap_would_be_exceeded() -> None:
    events = scan_opportunity_lifecycle(
        "TEST",
        _bars([10.0, 10.0, 9.88, 9.87, 9.84]),
        _position(target_qty=2000, current_total_qty=2000, settled_sellable_qty=2000, purchasable_qty=2000),
        rules=RulesConfig(
            max_t_ratio=0.10,
            bs_trigger_deviation=-0.002,
            bs_watch_deviation=-0.001,
            min_amount_ratio=1.0,
            risk_buffer_pct=0.0,
            trend_day_return_pct=1.0,
            trend_recent_return_pct=1.0,
            enable_auto_add=True,
            max_lifecycle_legs=3,
            max_lifecycle_total_t_ratio=0.15,
            min_lifecycle_leg_spacing_minutes=2,
            min_lifecycle_price_improvement_pct=0.002,
        ),
        fee_model=zero_fee_model(),
    )

    assert [event.state for event in events] == ["ENTER", "ABORT"]
    assert [event.debug_state for event in events] == ["PROBE", "BLOCKED"]
    assert "total T position cap" in events[-1].reason


def _position(
    target_qty: int = 1000,
    current_total_qty: int = 1000,
    settled_sellable_qty: int = 1000,
    purchasable_qty: int = 1000,
) -> PositionState:
    return PositionState(
        target_qty=target_qty,
        current_total_qty=current_total_qty,
        settled_sellable_qty=settled_sellable_qty,
        purchasable_qty=purchasable_qty,
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
