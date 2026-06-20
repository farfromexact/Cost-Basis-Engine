from datetime import datetime, timedelta

from core.models import MinuteBar
from research.decision_summary import build_decision_summary
from research.trigger_engine import ActionType, PositionState, RulesConfig, TriggerEngine, zero_fee_model


def test_decision_summary_separates_executable_trigger_sections() -> None:
    intent = _engine().evaluate(
        "TEST",
        _bars([10.0, 10.0, 10.0, 10.12]),
        _position(),
    )

    assert intent.action_type is ActionType.TRIGGER_SELL_TO_BUY
    summary = build_decision_summary(intent)

    assert set(summary.as_dict()) == {"recommendation", "evidence", "invalidation", "position_impact", "caveats"}
    assert any("Action: Trigger S->B" in row for row in summary.recommendation)
    assert any("Deviation score" in row for row in summary.evidence)
    assert any("Invalidation price" in row for row in summary.invalidation)
    assert any("Inventory delta after first leg: -100 shares" in row for row in summary.position_impact)
    assert any("not realized until both legs close" in row for row in summary.caveats)


def test_decision_summary_marks_watch_only_signal_as_non_executable() -> None:
    intent = _engine().evaluate(
        "TEST",
        _bars([10.0, 10.0, 10.0, 10.04]),
        _position(),
    )

    assert intent.action_type is ActionType.WATCH_SELL_TO_BUY
    summary = build_decision_summary(intent)

    assert any("Execution: wait only" in row for row in summary.recommendation)
    assert any("No first-leg execution" in row for row in summary.invalidation)
    assert any("deviation strength" in row for row in summary.caveats)
    assert any("Position impact: no new first-leg execution" in row for row in summary.position_impact)


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


def _position() -> PositionState:
    return PositionState(
        target_qty=1000,
        current_total_qty=1000,
        settled_sellable_qty=1000,
        purchasable_qty=1000,
    )


def _bars(closes: list[float]) -> list[MinuteBar]:
    start = datetime(2026, 6, 18, 10, 0)
    bars: list[MinuteBar] = []
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
