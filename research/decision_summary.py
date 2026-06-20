from __future__ import annotations

from dataclasses import dataclass

from research.trigger_engine import ActionType, TradeIntent


ACTION_LABELS = {
    ActionType.NO_TRADE: "No trade",
    ActionType.WATCH_SELL_TO_BUY: "Watch S->B",
    ActionType.TRIGGER_SELL_TO_BUY: "Trigger S->B",
    ActionType.WATCH_BUY_TO_SELL: "Watch B->S",
    ActionType.TRIGGER_BUY_TO_SELL: "Trigger B->S",
    ActionType.MANAGE_OPEN_PAIR: "Manage open pair",
    ActionType.FORCE_CLOSE_OR_RESTORE: "Force close/restore",
}


@dataclass(frozen=True)
class DecisionSummary:
    recommendation: list[str]
    evidence: list[str]
    invalidation: list[str]
    position_impact: list[str]
    caveats: list[str]

    def as_dict(self) -> dict[str, list[str]]:
        return {
            "recommendation": self.recommendation,
            "evidence": self.evidence,
            "invalidation": self.invalidation,
            "position_impact": self.position_impact,
            "caveats": self.caveats,
        }


def build_decision_summary(intent: TradeIntent) -> DecisionSummary:
    return DecisionSummary(
        recommendation=_recommendation(intent),
        evidence=_evidence(intent),
        invalidation=_invalidation(intent),
        position_impact=_position_impact(intent),
        caveats=_caveats(intent),
    )


def _recommendation(intent: TradeIntent) -> list[str]:
    label = ACTION_LABELS[intent.action_type]
    rows = [
        f"Action: {label}",
        f"Confidence: {intent.confidence}/100",
        f"Reference price: {_fmt_price(intent.reference_price)}",
    ]
    if intent.action_type.name.startswith("TRIGGER"):
        rows.append(f"Executable quantity: {intent.suggested_qty:,} shares")
    elif intent.action_type in {ActionType.MANAGE_OPEN_PAIR, ActionType.FORCE_CLOSE_OR_RESTORE}:
        rows.append(f"Pair quantity to manage: {intent.suggested_qty:,} shares")
    else:
        rows.append("Execution: wait only")
    if intent.next_action:
        rows.append(f"Next: {intent.next_action}")
    return rows


def _evidence(intent: TradeIntent) -> list[str]:
    rows = [f"Regime: {intent.regime_type.value}"]
    feature = intent.feature_snapshot
    if feature is not None:
        rows.extend(
            [
                f"VWAP deviation: {feature.vwap_deviation * 100:+.3f}%",
                f"Turnover ratio: {feature.amount_ratio:.2f}x",
                f"Recent return: {feature.recent_return * 100:+.3f}%",
            ]
        )
    if intent.deviation_decision is not None:
        rows.append(f"Deviation score: {intent.deviation_decision.deviation_score:.2f}x")
    rows.append(f"Estimated net edge: {_fmt_money(intent.estimated_net_edge)}")
    rows.extend(f"Reason: {item}" for item in intent.reasons[:3])
    return rows


def _invalidation(intent: TradeIntent) -> list[str]:
    rows: list[str] = []
    if intent.invalidation_price is not None:
        rows.append(f"Invalidation price: {_fmt_price(intent.invalidation_price)}")
    else:
        rows.append("Invalidation price: not active")
    if intent.expected_reversion_price is not None:
        rows.append(f"Expected reversion zone: {_fmt_price(intent.expected_reversion_price)}")
    else:
        rows.append("Expected reversion zone: not active")
    rows.append(f"Max wait: {intent.max_wait_minutes} minutes")
    if not intent.action_type.name.startswith("TRIGGER"):
        rows.append("No first-leg execution until all gates pass.")
    return rows


def _position_impact(intent: TradeIntent) -> list[str]:
    rows = [
        f"Suggested quantity: {intent.suggested_qty:,} shares",
        f"Suggested ratio: {intent.suggested_ratio * 100:.2f}%",
        f"Estimated cost reduction/share: {_fmt_price(intent.expected_cost_reduction_per_share)}",
    ]
    inventory = intent.inventory_decision
    if inventory is not None:
        rows.extend(
            [
                f"Inventory delta after first leg: {inventory.inventory_delta_after_trade:+,} shares",
                f"Sellable after first leg: {inventory.sellable_after_trade:,} shares",
                f"Capital required: {_fmt_money(inventory.capital_required)}",
            ]
        )
    else:
        rows.append("Position impact: no new first-leg execution recommended.")
    return rows


def _caveats(intent: TradeIntent) -> list[str]:
    rows = [f"Blocker: {item}" for item in intent.blockers]
    rows.extend(f"Warning: {item}" for item in intent.warnings)
    rows.append("Cost-basis reduction is not realized until both legs close, target inventory is restored, and fees/slippage are deducted.")
    rows.append("This is decision support, not out-of-sample profitability evidence.")
    return rows


def _fmt_price(value: float) -> str:
    return f"{value:,.4f}"


def _fmt_money(value: float) -> str:
    return f"{value:,.2f}"
