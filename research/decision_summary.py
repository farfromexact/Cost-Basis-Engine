from __future__ import annotations

from dataclasses import dataclass

from app.ui_text import t
from research.trigger_engine import ActionType, TradeIntent


_ACTION_LABEL_KEYS = {
    ActionType.NO_TRADE: "action.no_trade",
    ActionType.WATCH_SELL_TO_BUY: "action.watch_sb",
    ActionType.TRIGGER_SELL_TO_BUY: "action.trigger_sb",
    ActionType.WATCH_BUY_TO_SELL: "action.watch_bs",
    ActionType.TRIGGER_BUY_TO_SELL: "action.trigger_bs",
    ActionType.MANAGE_OPEN_PAIR: "action.manage_pair",
    ActionType.FORCE_CLOSE_OR_RESTORE: "action.force_close",
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


def build_decision_summary(intent: TradeIntent, lang: str | None = None) -> DecisionSummary:
    return DecisionSummary(
        recommendation=_recommendation(intent, lang=lang),
        evidence=_evidence(intent, lang=lang),
        invalidation=_invalidation(intent, lang=lang),
        position_impact=_position_impact(intent, lang=lang),
        caveats=_caveats(intent, lang=lang),
    )


def _recommendation(intent: TradeIntent, lang: str | None = None) -> list[str]:
    label = t(lang, _ACTION_LABEL_KEYS[intent.action_type])
    rows = [
        t(lang, "summary.action_prefix", action=label),
        t(lang, "summary.confidence_prefix", value=intent.confidence),
        t(lang, "summary.ref_price", value=_fmt_price(intent.reference_price)),
    ]
    if intent.action_type.name.startswith("TRIGGER"):
        rows.append(t(lang, "summary.exec_qty", value=intent.suggested_qty))
    elif intent.action_type in {ActionType.MANAGE_OPEN_PAIR, ActionType.FORCE_CLOSE_OR_RESTORE}:
        rows.append(t(lang, "summary.pair_qty", value=intent.suggested_qty))
    else:
        rows.append(t(lang, "summary.no_exec"))
    if intent.next_action:
        rows.append(t(lang, "intent.next_action_prefix", value=intent.next_action))
    return rows


def _evidence(intent: TradeIntent, lang: str | None = None) -> list[str]:
    rows = [t(lang, "summary.regime", value=intent.regime_type.value)]
    feature = intent.feature_snapshot
    if feature is not None:
        rows.extend(
            [
                t(lang, "summary.vwap_dev", value=feature.vwap_deviation * 100),
                t(lang, "summary.turnover", value=feature.amount_ratio),
                t(lang, "summary.recent_return", value=feature.recent_return * 100),
            ]
        )
    if intent.deviation_decision is not None:
        rows.append(t(lang, "summary.deviation_score", value=intent.deviation_decision.deviation_score))
        rows.append(t(lang, "summary.round_trip_cost_bps", value=intent.deviation_decision.estimated_round_trip_cost_bps))
        rows.append(t(lang, "summary.net_edge_bps", value=intent.deviation_decision.net_edge_bps))
        rows.append(t(lang, "summary.edge_buffer_bps", value=intent.deviation_decision.min_edge_buffer_bps))
    rows.append(t(lang, "summary.net_edge", value=_fmt_money(intent.estimated_net_edge)))
    rows.extend(t(lang, "summary.reason_prefix", value=item) for item in intent.reasons[:3])
    return rows


def _invalidation(intent: TradeIntent, lang: str | None = None) -> list[str]:
    rows: list[str] = []
    if intent.invalidation_price is not None:
        rows.append(t(lang, "summary.invalidation_price", value=_fmt_price(intent.invalidation_price)))
    else:
        rows.append(t(lang, "summary.no_invalidation"))
    if intent.expected_reversion_price is not None:
        rows.append(t(lang, "summary.expected_reversion", value=_fmt_price(intent.expected_reversion_price)))
    else:
        rows.append(t(lang, "summary.no_expected_reversion"))
    rows.append(t(lang, "summary.max_wait", value=intent.max_wait_minutes))
    if not intent.action_type.name.startswith("TRIGGER"):
        rows.append(t(lang, "reason.trade_wait"))
    return rows


def _position_impact(intent: TradeIntent, lang: str | None = None) -> list[str]:
    rows = [
        t(lang, "summary.suggested_qty", value=intent.suggested_qty),
        t(lang, "summary.suggested_ratio", value=intent.suggested_ratio * 100),
        t(lang, "summary.cost_reduction_per_share", value=_fmt_price(intent.expected_cost_reduction_per_share)),
    ]
    inventory = intent.inventory_decision
    if inventory is not None:
        rows.extend(
            [
                t(lang, "summary.inventory_delta", value=inventory.inventory_delta_after_trade),
                t(lang, "summary.sellable_after", value=inventory.sellable_after_trade),
                t(lang, "summary.capital_required", value=_fmt_money(inventory.capital_required)),
            ]
        )
    else:
        rows.append(t(lang, "summary.no_position_impact"))
    return rows


def _caveats(intent: TradeIntent, lang: str | None = None) -> list[str]:
    rows = [t(lang, "summary.caveat_blocker", value=item) for item in intent.blockers]
    rows.extend(t(lang, "summary.caveat_warning", value=item) for item in intent.warnings)
    rows.append(t(lang, "summary.cost_basis_footer"))
    rows.append(t(lang, "summary.performance_footer"))
    return rows


def _fmt_price(value: float) -> str:
    return f"{value:,.4f}"


def _fmt_money(value: float) -> str:
    return f"{value:,.2f}"
