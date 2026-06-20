from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Sequence

from core.fee_model import FeeModel
from core.models import MinuteBar
from research.trigger_engine import ActionType, PositionState, RulesConfig, TradeIntent, TriggerEngine


LIFECYCLE_NOTE = "Signal lifecycle only; no execution, fill, PnL, or cost-basis reduction is inferred."


@dataclass(frozen=True)
class OpportunityEvent:
    time: str
    price: float
    signal: str
    level: str
    side: str
    state: str
    action: str
    confidence: int
    suggested_qty: int
    vwap_deviation_pct: float
    net_edge: float
    reason: str
    opportunity_id: str
    note: str = LIFECYCLE_NOTE

    def as_dict(self) -> dict:
        return {
            "time": self.time,
            "price": self.price,
            "signal": self.signal,
            "level": self.level,
            "side": self.side,
            "state": self.state,
            "action": self.action,
            "confidence": self.confidence,
            "suggested_qty": self.suggested_qty,
            "vwap_deviation_pct": self.vwap_deviation_pct,
            "net_edge": self.net_edge,
            "reason": self.reason,
            "opportunity_id": self.opportunity_id,
            "note": self.note,
        }


@dataclass(frozen=True)
class _OpenOpportunity:
    opportunity_id: str
    signal: str
    side: str
    opened_at: datetime
    opened_price: float
    expected_reversion_price: float | None
    invalidation_price: float | None
    max_wait_minutes: int
    confidence: int
    suggested_qty: int
    net_edge: float


def scan_opportunity_lifecycle(
    symbol: str,
    bars: Sequence[MinuteBar],
    position: PositionState,
    rules: RulesConfig | None = None,
    fee_model: FeeModel | None = None,
    marker_cooldown_minutes: int = 10,
) -> list[OpportunityEvent]:
    """Scan closed-minute trigger states without inferring fills or PnL."""

    if not bars:
        return []

    engine = TriggerEngine(rules=rules, fee_model=fee_model)
    events: list[OpportunityEvent] = []
    active: _OpenOpportunity | None = None
    last_open_by_signal: dict[str, datetime] = {}
    cooldown = timedelta(minutes=max(1, marker_cooldown_minutes))

    for index in range(len(bars)):
        intent = engine.evaluate(symbol, list(bars[: index + 1]), position)
        current_time = _parse_timestamp(intent.timestamp)

        if active is not None:
            terminal = _terminal_event(active, intent, current_time)
            if terminal is not None:
                events.append(terminal)
                active = None
                continue

        if active is None and _is_trigger(intent):
            signal, side = _signal_and_side(intent)
            if signal in last_open_by_signal and current_time - last_open_by_signal[signal] < cooldown:
                continue
            active = _open_opportunity(intent, signal, side, current_time)
            events.append(_event_from_intent(active, intent, "OPEN", f"Trigger {side}", _intent_reason(intent)))
            last_open_by_signal[signal] = current_time

    return events


def _open_opportunity(intent: TradeIntent, signal: str, side: str, opened_at: datetime) -> _OpenOpportunity:
    return _OpenOpportunity(
        opportunity_id=f"{signal}-{opened_at.strftime('%H%M%S')}",
        signal=signal,
        side=side,
        opened_at=opened_at,
        opened_price=float(intent.reference_price),
        expected_reversion_price=intent.expected_reversion_price,
        invalidation_price=intent.invalidation_price,
        max_wait_minutes=max(1, int(intent.max_wait_minutes or 1)),
        confidence=intent.confidence,
        suggested_qty=intent.suggested_qty,
        net_edge=intent.estimated_net_edge,
    )


def _terminal_event(active: _OpenOpportunity, intent: TradeIntent, current_time: datetime) -> OpportunityEvent | None:
    price = float(intent.reference_price)
    elapsed = current_time - active.opened_at

    if _close_ready(active.side, price, active.expected_reversion_price):
        reason = f"Price reached expected reversion zone {active.expected_reversion_price:.4f}; close readiness only."
        return _event_from_intent(active, intent, "CLOSE_READY", f"Close ready {active.side}", reason)

    if _blocked(active.side, price, active.invalidation_price):
        reason = f"Price crossed invalidation level {active.invalidation_price:.4f}; opportunity is blocked."
        return _event_from_intent(active, intent, "BLOCKED", f"Blocked {active.side}", reason)

    if elapsed >= timedelta(minutes=active.max_wait_minutes):
        reason = f"Waited {active.max_wait_minutes} minutes without close readiness; opportunity expired."
        return _event_from_intent(active, intent, "EXPIRED", f"Expired {active.side}", reason)

    if _is_trigger(intent):
        signal, _side = _signal_and_side(intent)
        if signal != active.signal:
            reason = "Opposite trigger appeared before close readiness; do not infer a completed loop."
            return _event_from_intent(active, intent, "BLOCKED", f"Blocked {active.side}", reason)

    return None


def _event_from_intent(
    active: _OpenOpportunity,
    intent: TradeIntent,
    state: str,
    action: str,
    reason: str,
) -> OpportunityEvent:
    feature = intent.feature_snapshot
    return OpportunityEvent(
        time=intent.timestamp,
        price=float(intent.reference_price),
        signal=active.signal,
        level="Trigger" if state == "OPEN" else "Lifecycle",
        side=active.side,
        state=state,
        action=action,
        confidence=active.confidence,
        suggested_qty=active.suggested_qty,
        vwap_deviation_pct=(feature.vwap_deviation * 100) if feature else 0.0,
        net_edge=active.net_edge,
        reason=reason,
        opportunity_id=active.opportunity_id,
    )


def _is_trigger(intent: TradeIntent) -> bool:
    return intent.action_type in {ActionType.TRIGGER_SELL_TO_BUY, ActionType.TRIGGER_BUY_TO_SELL}


def _signal_and_side(intent: TradeIntent) -> tuple[str, str]:
    if intent.action_type is ActionType.TRIGGER_SELL_TO_BUY:
        return "SB", "S->B"
    if intent.action_type is ActionType.TRIGGER_BUY_TO_SELL:
        return "BS", "B->S"
    raise ValueError(f"unsupported trigger action: {intent.action_type}")


def _close_ready(side: str, price: float, expected_reversion_price: float | None) -> bool:
    if expected_reversion_price is None:
        return False
    if side == "S->B":
        return price <= expected_reversion_price
    return price >= expected_reversion_price


def _blocked(side: str, price: float, invalidation_price: float | None) -> bool:
    if invalidation_price is None:
        return False
    if side == "S->B":
        return price >= invalidation_price
    return price <= invalidation_price


def _intent_reason(intent: TradeIntent) -> str:
    return "; ".join(intent.reasons[:2]) if intent.reasons else intent.next_action


def _parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(str(value))
