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
    main_state: str = ""
    debug_state: str = ""
    vwap: float = 0.0
    vwap_deviation_bps: float = 0.0
    deviation_bps: float = 0.0
    regime: str = ""
    anchor_type: str = "NEUTRAL"
    deviation_score: float = 0.0
    exhaustion_score: float = 0.0
    liquidity_score: float = 0.0
    edge_after_cost: float = 0.0
    cost_bps: float = 0.0
    net_edge_bps: float = 0.0
    regime_simple: str = ""
    regime_detail: str = ""
    momentum_flag: str = ""
    inventory_ok: bool = False
    position_multiplier: float = 0.0
    target_price: float | None = None
    invalidation_price: float | None = None
    inventory_before: int = 0
    inventory_after_if_executed: int = 0
    leg_count: int = 1
    total_suggested_qty: int = 0
    max_total_suggested_qty: int = 0
    add_price_improvement_pct: float = 0.0
    minutes_since_last_leg: int = 0
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
            "main_state": self.main_state or self.state,
            "debug_state": self.debug_state or self.state,
            "vwap": self.vwap,
            "vwap_deviation_bps": self.vwap_deviation_bps,
            "deviation_bps": self.deviation_bps or self.vwap_deviation_bps,
            "regime": self.regime,
            "anchor_type": self.anchor_type,
            "deviation_score": self.deviation_score,
            "exhaustion_score": self.exhaustion_score,
            "liquidity_score": self.liquidity_score,
            "edge_after_cost": self.edge_after_cost,
            "cost_bps": self.cost_bps,
            "net_edge_bps": self.net_edge_bps,
            "regime_simple": self.regime_simple,
            "regime_detail": self.regime_detail,
            "momentum_flag": self.momentum_flag,
            "inventory_ok": self.inventory_ok,
            "position_multiplier": self.position_multiplier,
            "target_price": self.target_price,
            "invalidation_price": self.invalidation_price,
            "inventory_before": self.inventory_before,
            "inventory_after_if_executed": self.inventory_after_if_executed,
            "leg_count": self.leg_count,
            "total_suggested_qty": self.total_suggested_qty,
            "max_total_suggested_qty": self.max_total_suggested_qty,
            "add_price_improvement_pct": self.add_price_improvement_pct,
            "minutes_since_last_leg": self.minutes_since_last_leg,
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
    last_leg_at: datetime | None = None
    total_suggested_qty: int = 0
    max_legs: int = 3
    max_total_suggested_qty: int = 0
    min_minutes_between_legs: int = 2
    min_price_improvement_pct: float = 0.002


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
            add_event = _add_event(active, intent, current_time)
            if engine.rules.enable_auto_add and add_event is not None:
                next_qty = intent.suggested_qty or active.suggested_qty
                events.append(add_event)
                active = replace(
                    active,
                    leg_count=active.leg_count + 1,
                    last_leg_at=current_time,
                    last_leg_price=float(intent.reference_price),
                    total_suggested_qty=active.total_suggested_qty + next_qty,
                    net_edge=max(active.net_edge, intent.estimated_net_edge),
                )
                continue

            terminal = _terminal_event(active, intent, current_time, _add_constraint_blocker(active, intent, current_time))
            if terminal is not None:
                events.append(terminal)
                active = None
                continue

        if active is None and _is_signal(intent):
            signal, side = _signal_and_side(intent)
            if signal in last_open_by_signal and current_time - last_open_by_signal[signal] < cooldown:
                continue
            candidate = _open_opportunity(intent, signal, side, current_time, position.current_total_qty, position.target_qty, engine.rules)
            debug_state = _entry_debug_state(intent)
            state = _main_state(debug_state)
            events.append(_event_from_intent(candidate, intent, state, f"{state}_{signal}", _intent_reason(intent), debug_state=debug_state))
            last_open_by_signal[signal] = current_time
            if state == "ENTER":
                active = candidate

    return events


def _open_opportunity(
    intent: TradeIntent,
    signal: str,
    side: str,
    opened_at: datetime,
    inventory_before: int,
    target_qty: int,
    rules: RulesConfig,
) -> _OpenOpportunity:
    suggested_qty = int(intent.suggested_qty or 0)
    max_total = _round_lot(target_qty * max(0.0, rules.max_lifecycle_total_t_ratio), rules.lot_size)
    max_total = max(suggested_qty, max_total)
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
        suggested_qty=suggested_qty,
        net_edge=intent.estimated_net_edge,
        inventory_before=inventory_before,
        last_leg_price=float(intent.reference_price),
        last_leg_at=opened_at,
        total_suggested_qty=suggested_qty,
        max_legs=max(1, int(rules.max_lifecycle_legs if rules.enable_auto_add else rules.max_legs_per_side)),
        max_total_suggested_qty=max_total,
        min_minutes_between_legs=max(1, int(rules.min_lifecycle_leg_spacing_minutes)),
        min_price_improvement_pct=max(0.0, float(rules.min_lifecycle_price_improvement_pct)),
    )


def _terminal_event(
    active: _OpenOpportunity,
    intent: TradeIntent,
    current_time: datetime,
    add_blocker: str | None = None,
) -> OpportunityEvent | None:
    price = float(intent.reference_price)
    elapsed = current_time - active.opened_at

    if _close_ready(active.side, price, active.expected_reversion_price):
        reason = f"Price reached expected reversion zone {active.expected_reversion_price:.4f}; close readiness only."
        return _event_from_intent(active, intent, "EXIT", f"EXIT_{active.signal}", reason, debug_state="CLOSE_READY")

    if intent.regime_type.value == "LATE_SESSION":
        reason = "Late-session inventory clock is active; decide whether to restore target inventory or abandon the T loop."
        return _event_from_intent(active, intent, "ABORT", f"ABORT_{active.signal}", reason, debug_state="FORCED_DECISION")

    if _blocked(active.side, price, active.invalidation_price):
        if add_blocker:
            reason = (
                f"Price crossed invalidation level {active.invalidation_price:.4f}; "
                f"next leg is not allowed because {add_blocker}."
            )
        else:
            reason = f"Price crossed invalidation level {active.invalidation_price:.4f}; opportunity is blocked."
        return _event_from_intent(active, intent, "ABORT", f"ABORT_{active.signal}", reason, debug_state="BLOCKED")

    if elapsed >= timedelta(minutes=active.max_wait_minutes):
        reason = f"Waited {active.max_wait_minutes} minutes without close readiness; opportunity expired."
        return _event_from_intent(active, intent, "ABORT", f"ABORT_{active.signal}", reason, debug_state="EXPIRED")

    if _is_trigger(intent):
        signal, _side = _signal_and_side(intent)
        if signal != active.signal:
            reason = "Opposite trigger appeared before close readiness; do not infer a completed loop."
            return _event_from_intent(active, intent, "ABORT", f"ABORT_{active.signal}", reason, debug_state="BLOCKED")

    return None


def _add_event(active: _OpenOpportunity, intent: TradeIntent, current_time: datetime) -> OpportunityEvent | None:
    if not _is_same_side_trigger(active, intent):
        return None
    blocker = _add_constraint_blocker(active, intent, current_time)
    if blocker is not None:
        return None
    next_qty = intent.suggested_qty or active.suggested_qty
    price = float(intent.reference_price)
    improvement = _price_improvement_pct(active.side, active.last_leg_price, price)
    next_leg_count = active.leg_count + 1
    next_total_qty = active.total_suggested_qty + next_qty
    reason = (
        f"Price improved {improvement:.2%} for the next {active.side} leg; "
        f"leg {next_leg_count}/{active.max_legs}, total T qty {next_total_qty}/{active.max_total_suggested_qty}."
    )
    return _event_from_intent(
        active,
        intent,
        "ENTER",
        f"ENTER_{active.signal}",
        reason,
        debug_state="ADD",
        leg_count=next_leg_count,
        total_suggested_qty=next_total_qty,
        add_price_improvement_pct=improvement,
        minutes_since_last_leg=_elapsed_minutes(active.last_leg_at or active.opened_at, current_time),
    )


def _add_constraint_blocker(active: _OpenOpportunity, intent: TradeIntent, current_time: datetime) -> str | None:
    if not _is_same_side_trigger(active, intent):
        return None
    next_qty = intent.suggested_qty or active.suggested_qty
    if current_time - active.opened_at >= timedelta(minutes=active.max_wait_minutes):
        return f"max wait reached ({active.max_wait_minutes}m)"
    if active.leg_count >= active.max_legs:
        return f"max legs reached ({active.leg_count}/{active.max_legs})"
    if active.total_suggested_qty + next_qty > active.max_total_suggested_qty:
        return (
            "total T position cap would be exceeded "
            f"({active.total_suggested_qty + next_qty}/{active.max_total_suggested_qty})"
        )
    elapsed_minutes = _elapsed_minutes(active.last_leg_at or active.opened_at, current_time)
    if elapsed_minutes < active.min_minutes_between_legs:
        return (
            "minimum minutes between legs has not passed "
            f"({elapsed_minutes}/{active.min_minutes_between_legs})"
        )
    improvement = _price_improvement_pct(active.side, active.last_leg_price, float(intent.reference_price))
    if improvement < active.min_price_improvement_pct:
        return (
            "price improvement is below add-leg requirement "
            f"({improvement:.2%}/{active.min_price_improvement_pct:.2%})"
        )
    return None


def _is_same_side_trigger(active: _OpenOpportunity, intent: TradeIntent) -> bool:
    if not _is_trigger(intent):
        return False
    signal, _side = _signal_and_side(intent)
    return signal == active.signal


def _event_from_intent(
    active: _OpenOpportunity,
    intent: TradeIntent,
    state: str,
    action: str,
    reason: str,
    debug_state: str | None = None,
    leg_count: int | None = None,
    total_suggested_qty: int | None = None,
    add_price_improvement_pct: float = 0.0,
    minutes_since_last_leg: int = 0,
) -> OpportunityEvent:
    feature = intent.feature_snapshot
    deviation = intent.deviation_decision
    inventory = intent.inventory_decision
    suggested_qty = intent.suggested_qty or active.suggested_qty
    inventory_before = active.inventory_before
    event_leg_count = leg_count if leg_count is not None else active.leg_count
    event_total_qty = total_suggested_qty if total_suggested_qty is not None else active.total_suggested_qty
    inventory_after = inventory_before + _signed_inventory_delta(active.side, event_total_qty)
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
        main_state=state,
        debug_state=debug_state or state,
        vwap=round(feature.vwap, 4) if feature else 0.0,
        vwap_deviation_bps=round((feature.vwap_deviation * 10000), 2) if feature else 0.0,
        deviation_bps=round((feature.vwap_deviation * 10000), 2) if feature else 0.0,
        regime=intent.regime_type.value,
        anchor_type=deviation.anchor_type if deviation else (feature.anchor_type if feature else "NEUTRAL"),
        deviation_score=deviation.deviation_score if deviation else 0.0,
        exhaustion_score=deviation.exhaustion_score if deviation else (feature.exhaustion_score if feature else 0.0),
        liquidity_score=deviation.liquidity_score if deviation else 0.0,
        edge_after_cost=deviation.net_edge_after_fee if deviation else intent.estimated_net_edge,
        cost_bps=deviation.estimated_round_trip_cost_bps if deviation else 0.0,
        net_edge_bps=deviation.net_edge_bps if deviation else 0.0,
        regime_simple=_simple_regime(intent),
        regime_detail=(intent.regime_decision.regime_profile if intent.regime_decision else intent.regime_type.value),
        momentum_flag=_momentum_flag(deviation),
        inventory_ok=bool(inventory.executable) if inventory else not bool(intent.blockers),
        position_multiplier=round((suggested_qty / max(1, active.suggested_qty)), 4) if active.suggested_qty else 0.0,
        target_price=intent.expected_reversion_price,
        invalidation_price=intent.invalidation_price,
        inventory_before=inventory_before,
        inventory_after_if_executed=inventory_after,
        leg_count=event_leg_count,
        total_suggested_qty=event_total_qty,
        max_total_suggested_qty=active.max_total_suggested_qty,
        add_price_improvement_pct=round(add_price_improvement_pct, 6),
        minutes_since_last_leg=minutes_since_last_leg,
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


def _entry_debug_state(intent: TradeIntent) -> str:
    if not _is_trigger(intent):
        return "WATCH"
    if intent.action_type is ActionType.TRIGGER_BUY_TO_SELL:
        exhaustion = intent.deviation_decision.exhaustion_score if intent.deviation_decision else 0.0
        return "CONFIRM" if exhaustion >= 70 else "PROBE"
    deviation_score = intent.deviation_decision.deviation_score if intent.deviation_decision else 0.0
    return "CONFIRM" if deviation_score >= 1.6 else "PROBE"


def _main_state(debug_state: str) -> str:
    if debug_state == "WATCH":
        return "WATCH"
    if debug_state in {"PROBE", "CONFIRM", "ADD"}:
        return "ENTER"
    if debug_state == "CLOSE_READY":
        return "EXIT"
    if debug_state in {"FORCED_DECISION", "BLOCKED", "EXPIRED"}:
        return "ABORT"
    return debug_state


def _event_level(state: str) -> str:
    if state == "WATCH":
        return "Watch"
    if state == "ENTER":
        return "Trigger"
    if state in {"EXIT", "ABORT"}:
        return "Lifecycle"
    return "Lifecycle"


def _why_not_earlier(state: str, intent: TradeIntent) -> str:
    if state == "WATCH":
        return "Earlier minute remains watch-only because trigger, liquidity, edge, or inventory gates are not all satisfied."
    if state == "ADD":
        return "Earlier same-side triggers did not pass leg-count, total-cap, time-spacing, and price-improvement constraints."
    if intent.blockers:
        return f"Earlier blocked by: {intent.blockers[0]}"
    if intent.deviation_decision and intent.deviation_decision.blocked_reasons:
        return f"Earlier diagnostics: {intent.deviation_decision.blocked_reasons[0]}"
    return "Earlier minutes did not yet produce this lifecycle state under closed-minute evaluation."


def _simple_regime(intent: TradeIntent) -> str:
    detail = intent.regime_decision.regime_profile if intent.regime_decision else intent.regime_type.value
    if detail in {"RANGE", "MEAN_REVERTING"} or intent.regime_type.value == "MEAN_REVERTING":
        return "NORMAL"
    if detail in {"CRASH_DOWN", "LIMIT_RISK", "ILLIQUID", "LATE_SESSION"} or intent.regime_type.value in {"LIMIT_RISK", "ILLIQUID", "LATE_SESSION", "NO_TRADE"}:
        return "DANGER"
    return "TREND"


def _momentum_flag(deviation) -> str:
    if deviation is None:
        return ""
    blocked = set(deviation.blocked_reasons)
    if "RECENT_LOW_BREAKS" in blocked:
        return "continuous_breakdown"
    if "RECENT_HIGH_BREAKS" in blocked:
        return "continuous_breakout"
    if "DOWNSIDE_EXHAUSTION_WEAK" in blocked:
        return "down_momentum_not_confirmed"
    return "not_accelerating_or_repairing"


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


def _signed_inventory_delta(side: str, qty: int) -> int:
    if side == "S->B":
        return -qty
    if side == "B->S":
        return qty
    return 0


def _price_improvement_pct(side: str, previous_price: float, current_price: float) -> float:
    if previous_price <= 0:
        return 0.0
    if side == "B->S":
        return max(0.0, (previous_price - current_price) / previous_price)
    if side == "S->B":
        return max(0.0, (current_price - previous_price) / previous_price)
    return 0.0


def _elapsed_minutes(start: datetime, end: datetime) -> int:
    return max(0, int((end - start).total_seconds() // 60))


def _round_lot(value: float, lot_size: int) -> int:
    if value <= 0:
        return 0
    return int(value // lot_size) * lot_size


def _parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(str(value))
