from __future__ import annotations

from dataclasses import dataclass, replace
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
    vwap: float = 0.0
    vwap_deviation_bps: float = 0.0
    regime: str = ""
    anchor_type: str = "NEUTRAL"
    deviation_score: float = 0.0
    exhaustion_score: float = 0.0
    liquidity_score: float = 0.0
    edge_after_cost: float = 0.0
    position_multiplier: float = 0.0
    target_price: float | None = None
    invalidation_price: float | None = None
    inventory_before: int = 0
    inventory_after_if_executed: int = 0
    reason_codes: str = ""
    blocked_reasons: str = ""
    why_not_earlier: str = ""
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
            "vwap": self.vwap,
            "vwap_deviation_bps": self.vwap_deviation_bps,
            "regime": self.regime,
            "anchor_type": self.anchor_type,
            "deviation_score": self.deviation_score,
            "exhaustion_score": self.exhaustion_score,
            "liquidity_score": self.liquidity_score,
            "edge_after_cost": self.edge_after_cost,
            "position_multiplier": self.position_multiplier,
            "target_price": self.target_price,
            "invalidation_price": self.invalidation_price,
            "inventory_before": self.inventory_before,
            "inventory_after_if_executed": self.inventory_after_if_executed,
            "reason_codes": self.reason_codes,
            "blocked_reasons": self.blocked_reasons,
            "why_not_earlier": self.why_not_earlier,
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
    inventory_before: int = 0
    leg_count: int = 1
    last_leg_price: float = 0.0


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
            add_event = _add_event(active, intent, current_time)
            if add_event is not None:
                events.append(add_event)
                active = replace(
                    active,
                    leg_count=active.leg_count + 1,
                    last_leg_price=float(intent.reference_price),
                    net_edge=max(active.net_edge, intent.estimated_net_edge),
                )
                continue

        if active is None and _is_signal(intent):
            signal, side = _signal_and_side(intent)
            if signal in last_open_by_signal and current_time - last_open_by_signal[signal] < cooldown:
                continue
            candidate = _open_opportunity(intent, signal, side, current_time, position.current_total_qty)
            state = _entry_state(intent)
            events.append(_event_from_intent(candidate, intent, state, f"{state.title()} {side}", _intent_reason(intent)))
            last_open_by_signal[signal] = current_time
            if state in {"PROBE", "CONFIRM"}:
                active = candidate

    return events


def _open_opportunity(intent: TradeIntent, signal: str, side: str, opened_at: datetime, inventory_before: int) -> _OpenOpportunity:
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
        inventory_before=inventory_before,
        last_leg_price=float(intent.reference_price),
    )


def _terminal_event(active: _OpenOpportunity, intent: TradeIntent, current_time: datetime) -> OpportunityEvent | None:
    price = float(intent.reference_price)
    elapsed = current_time - active.opened_at

    if _close_ready(active.side, price, active.expected_reversion_price):
        reason = f"Price reached expected reversion zone {active.expected_reversion_price:.4f}; close readiness only."
        return _event_from_intent(active, intent, "CLOSE_READY", f"Close {active.side}", reason)

    if intent.regime_type.value == "LATE_SESSION":
        reason = "Late-session inventory clock is active; decide whether to restore target inventory or abandon the T loop."
        return _event_from_intent(active, intent, "FORCED_DECISION", f"Forced decision {active.side}", reason)

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


def _add_event(active: _OpenOpportunity, intent: TradeIntent, current_time: datetime) -> OpportunityEvent | None:
    if active.leg_count >= 3 or not _is_trigger(intent):
        return None
    signal, _side = _signal_and_side(intent)
    if signal != active.signal:
        return None
    if current_time - active.opened_at < timedelta(minutes=2):
        return None
    price = float(intent.reference_price)
    if active.side == "B->S" and price < active.last_leg_price * 0.998:
        return _event_from_intent(active, intent, "ADD", f"Add {active.side}", "Price improved for the next B->S leg and total legs remain capped.")
    if active.side == "S->B" and price > active.last_leg_price * 1.002:
        return _event_from_intent(active, intent, "ADD", f"Add {active.side}", "Price improved for the next S->B leg and total legs remain capped.")
    return None


def _event_from_intent(
    active: _OpenOpportunity,
    intent: TradeIntent,
    state: str,
    action: str,
    reason: str,
) -> OpportunityEvent:
    feature = intent.feature_snapshot
    deviation = intent.deviation_decision
    inventory = intent.inventory_decision
    suggested_qty = intent.suggested_qty or active.suggested_qty
    inventory_before = active.inventory_before
    inventory_after = inventory_before + (inventory.inventory_delta_after_trade if inventory else 0)
    return OpportunityEvent(
        time=intent.timestamp,
        price=float(intent.reference_price),
        signal=active.signal,
        level=_event_level(state),
        side=active.side,
        state=state,
        action=action,
        confidence=active.confidence,
        suggested_qty=suggested_qty,
        vwap_deviation_pct=(feature.vwap_deviation * 100) if feature else 0.0,
        net_edge=active.net_edge,
        reason=reason,
        opportunity_id=active.opportunity_id,
        vwap=round(feature.vwap, 4) if feature else 0.0,
        vwap_deviation_bps=round((feature.vwap_deviation * 10000), 2) if feature else 0.0,
        regime=intent.regime_type.value,
        anchor_type=deviation.anchor_type if deviation else (feature.anchor_type if feature else "NEUTRAL"),
        deviation_score=deviation.deviation_score if deviation else 0.0,
        exhaustion_score=deviation.exhaustion_score if deviation else (feature.exhaustion_score if feature else 0.0),
        liquidity_score=deviation.liquidity_score if deviation else 0.0,
        edge_after_cost=deviation.net_edge_after_fee if deviation else intent.estimated_net_edge,
        position_multiplier=round((suggested_qty / max(1, active.suggested_qty)), 4) if active.suggested_qty else 0.0,
        target_price=intent.expected_reversion_price,
        invalidation_price=intent.invalidation_price,
        inventory_before=inventory_before,
        inventory_after_if_executed=inventory_after,
        reason_codes=", ".join(deviation.reason_codes) if deviation else "",
        blocked_reasons=", ".join(intent.blockers + (deviation.blocked_reasons if deviation else [])),
        why_not_earlier=_why_not_earlier(state, intent),
    )


def _is_trigger(intent: TradeIntent) -> bool:
    return intent.action_type in {ActionType.TRIGGER_SELL_TO_BUY, ActionType.TRIGGER_BUY_TO_SELL}


def _is_signal(intent: TradeIntent) -> bool:
    return intent.action_type in {
        ActionType.WATCH_SELL_TO_BUY,
        ActionType.WATCH_BUY_TO_SELL,
        ActionType.TRIGGER_SELL_TO_BUY,
        ActionType.TRIGGER_BUY_TO_SELL,
    }


def _signal_and_side(intent: TradeIntent) -> tuple[str, str]:
    if intent.action_type is ActionType.TRIGGER_SELL_TO_BUY:
        return "SB", "S->B"
    if intent.action_type is ActionType.TRIGGER_BUY_TO_SELL:
        return "BS", "B->S"
    if intent.action_type is ActionType.WATCH_SELL_TO_BUY:
        return "SB", "S->B"
    if intent.action_type is ActionType.WATCH_BUY_TO_SELL:
        return "BS", "B->S"
    raise ValueError(f"unsupported signal action: {intent.action_type}")


def _entry_state(intent: TradeIntent) -> str:
    if not _is_trigger(intent):
        return "WATCH"
    if intent.action_type is ActionType.TRIGGER_BUY_TO_SELL:
        exhaustion = intent.deviation_decision.exhaustion_score if intent.deviation_decision else 0.0
        return "CONFIRM" if exhaustion >= 70 else "PROBE"
    deviation_score = intent.deviation_decision.deviation_score if intent.deviation_decision else 0.0
    return "CONFIRM" if deviation_score >= 1.6 else "PROBE"


def _event_level(state: str) -> str:
    if state == "WATCH":
        return "Watch"
    if state in {"PROBE", "ADD", "CONFIRM"}:
        return state.title()
    return "Lifecycle"


def _why_not_earlier(state: str, intent: TradeIntent) -> str:
    if state == "WATCH":
        return "Earlier minute remains watch-only because trigger, liquidity, edge, or inventory gates are not all satisfied."
    if intent.blockers:
        return f"Earlier blocked by: {intent.blockers[0]}"
    if intent.deviation_decision and intent.deviation_decision.blocked_reasons:
        return f"Earlier diagnostics: {intent.deviation_decision.blocked_reasons[0]}"
    return "Earlier minutes did not yet produce this lifecycle state under closed-minute evaluation."


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
