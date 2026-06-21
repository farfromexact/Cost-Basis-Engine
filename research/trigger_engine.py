from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from math import floor

from core.fee_model import FeeModel
from core.models import MinuteBar, Side
from data.validation import validate_minute_bars
from research.features import build_features


class ActionType(str, Enum):
    NO_TRADE = "NO_TRADE"
    WATCH_SELL_TO_BUY = "WATCH_SELL_TO_BUY"
    TRIGGER_SELL_TO_BUY = "TRIGGER_SELL_TO_BUY"
    WATCH_BUY_TO_SELL = "WATCH_BUY_TO_SELL"
    TRIGGER_BUY_TO_SELL = "TRIGGER_BUY_TO_SELL"
    MANAGE_OPEN_PAIR = "MANAGE_OPEN_PAIR"
    FORCE_CLOSE_OR_RESTORE = "FORCE_CLOSE_OR_RESTORE"


class RegimeType(str, Enum):
    MEAN_REVERTING = "MEAN_REVERTING"
    TREND_UP = "TREND_UP"
    TREND_DOWN = "TREND_DOWN"
    EVENT_DRIVEN = "EVENT_DRIVEN"
    ILLIQUID = "ILLIQUID"
    LIMIT_RISK = "LIMIT_RISK"
    LATE_SESSION = "LATE_SESSION"
    NO_TRADE = "NO_TRADE"


class SideCandidate(str, Enum):
    SELL_TO_BUY = "SELL_TO_BUY"
    BUY_TO_SELL = "BUY_TO_SELL"
    NONE = "NONE"


@dataclass(frozen=True)
class RulesConfig:
    lot_size: int = 100
    minimum_order_qty: int = 100
    max_t_ratio: float = 0.05
    max_single_trade_qty: int | None = None
    start_time: str = "09:45"
    no_new_trade_after: str = "14:30"
    latest_open_time: str = "14:30"
    force_restore_time: str = "14:50"
    close_time: str = "15:00"
    price_limit_pct: float = 0.10
    sb_trigger_deviation: float = 0.006
    sb_watch_deviation: float = 0.003
    bs_trigger_deviation: float = -0.006
    bs_watch_deviation: float = -0.003
    min_amount_ratio: float = 1.20
    expected_reversion_pct: float = 0.002
    risk_buffer_pct: float = 0.001
    min_net_edge: float = 0.0
    min_edge_buffer_bps: float = 5.0
    min_trigger_deviation_score: float = 1.0
    sb_min_trigger_deviation_score: float = 1.0
    bs_min_trigger_deviation_score: float = 1.0
    bs_probe_exhaustion_score: float = 35.0
    bs_strong_down_exhaustion_score: float = 65.0
    weak_trend_position_multiplier: float = 0.40
    strong_trend_position_multiplier: float = 0.30
    weak_trend_trigger_multiplier: float = 1.20
    strong_trend_trigger_multiplier: float = 1.80
    crash_day_return_pct: float = 0.05
    crash_recent_return_pct: float = 0.010
    trend_day_return_pct: float = 0.02
    trend_recent_return_pct: float = 0.004
    near_limit_buffer_pct: float = 0.015
    max_wait_minutes: int = 45
    enable_auto_add: bool = False
    max_legs_per_side: int = 1
    max_lifecycle_legs: int = 1
    max_lifecycle_total_t_ratio: float = 0.20
    min_lifecycle_leg_spacing_minutes: int = 2
    min_lifecycle_price_improvement_pct: float = 0.002
    risk_preset_id: str = "balanced"
    max_daily_turnover_ratio: float = 0.20
    max_same_day_capital_at_risk_ratio: float = 0.10
    beta_market: float = 1.0
    beta_sector: float = 0.0


@dataclass(frozen=True)
class PositionState:
    target_qty: int
    current_total_qty: int
    settled_sellable_qty: int
    purchasable_qty: int = 0
    today_bought_locked_qty: int = 0
    cash_available: float | None = None
    open_pair_side: str | None = None
    open_pair_price: float | None = None
    open_pair_qty: int | None = None


@dataclass(frozen=True)
class FeatureSnapshot:
    timestamp: str
    price: float
    vwap: float
    anchored_vwap: float
    vwap_deviation: float
    anchored_vwap_deviation: float
    residual_return: float
    time_normalized_zscore: float
    amount_ratio: float
    day_return: float
    day_position: float
    recent_return: float
    recent_high_breaks: int
    recent_low_breaks: int
    opening_range_break: str | None
    minutes_to_close: int
    near_upper_limit: bool
    near_lower_limit: bool
    exhaustion_score: float = 0.0
    anchor_type: str = "NEUTRAL"
    target_reason: str = ""


@dataclass(frozen=True)
class RegimeDecision:
    regime_type: RegimeType
    allow_sell_to_buy: bool
    allow_buy_to_sell: bool
    confidence: int
    reasons: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    regime_profile: str = "RANGE"
    sell_to_buy_position_multiplier: float = 1.0
    buy_to_sell_position_multiplier: float = 1.0
    sell_to_buy_trigger_multiplier: float = 1.0
    buy_to_sell_trigger_multiplier: float = 1.0


@dataclass(frozen=True)
class DeviationDecision:
    side_candidate: SideCandidate
    deviation_score: float
    expected_reversion_zone: float | None
    invalidation_price: float | None
    max_wait_minutes: int
    gross_edge_estimate: float
    net_edge_after_fee: float
    estimated_fee: float
    estimated_slippage: float
    expected_gross_edge_bps: float = 0.0
    estimated_buy_cost: float = 0.0
    estimated_sell_cost: float = 0.0
    estimated_round_trip_cost_bps: float = 0.0
    net_edge_bps: float = 0.0
    min_edge_buffer_bps: float = 0.0
    anchor_type: str = "NEUTRAL"
    target_reason: str = ""
    exhaustion_score: float = 0.0
    liquidity_score: float = 0.0
    reason_codes: list[str] = field(default_factory=list)
    blocked_reasons: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class InventoryDecision:
    executable: bool
    suggested_qty: int
    suggested_ratio: float
    capital_required: float
    sellable_after_trade: int
    inventory_delta_after_trade: int
    reasons: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class TradeIntent:
    action_type: ActionType
    symbol: str
    timestamp: str
    side: SideCandidate
    suggested_qty: int
    suggested_ratio: float
    reference_price: float
    trigger_price: float | None
    expected_reversion_price: float | None
    invalidation_price: float | None
    max_wait_minutes: int
    estimated_gross_edge: float
    estimated_fee: float
    estimated_slippage: float
    estimated_net_edge: float
    expected_cost_reduction_per_share: float
    confidence: int
    regime_type: RegimeType
    reasons: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    next_action: str = ""
    feature_snapshot: FeatureSnapshot | None = None
    regime_decision: RegimeDecision | None = None
    deviation_decision: DeviationDecision | None = None
    inventory_decision: InventoryDecision | None = None

    def as_dict(self) -> dict:
        payload = self.__dict__.copy()
        payload["action_type"] = self.action_type.value
        payload["side"] = self.side.value
        payload["regime_type"] = self.regime_type.value
        if self.deviation_decision is not None:
            payload["estimated_round_trip_cost_bps"] = self.deviation_decision.estimated_round_trip_cost_bps
            payload["net_edge_bps"] = self.deviation_decision.net_edge_bps
            payload["min_edge_buffer_bps"] = self.deviation_decision.min_edge_buffer_bps
        else:
            payload["estimated_round_trip_cost_bps"] = 0.0
            payload["net_edge_bps"] = 0.0
            payload["min_edge_buffer_bps"] = 0.0
        if self.inventory_decision is not None:
            payload["inventory_ok"] = self.inventory_decision.executable
            payload["sellable_after_trade"] = self.inventory_decision.sellable_after_trade
            payload["inventory_delta_after_trade"] = self.inventory_decision.inventory_delta_after_trade
            payload["capital_required"] = self.inventory_decision.capital_required
        else:
            payload["inventory_ok"] = False
            payload["sellable_after_trade"] = 0
            payload["inventory_delta_after_trade"] = 0
            payload["capital_required"] = 0.0
        for key in ("feature_snapshot", "regime_decision", "deviation_decision", "inventory_decision"):
            value = payload[key]
            if value is not None:
                payload[key] = _dataclass_to_dict(value)
        return payload


class TriggerEngine:
    def __init__(
        self,
        rules: RulesConfig | None = None,
        fee_model: FeeModel | None = None,
    ) -> None:
        self.rules = rules or RulesConfig()
        self.fee_model = fee_model or FeeModel()

    def evaluate(
        self,
        symbol: str,
        bars: list[MinuteBar],
        position: PositionState,
        market_return: float = 0.0,
        sector_return: float = 0.0,
    ) -> TradeIntent:
        validate_minute_bars(bars)
        feature = self.build_feature_snapshot(bars, market_return, sector_return)
        if position.open_pair_side:
            return self._manage_open_pair(symbol, feature, position)

        regime = self.evaluate_regime(feature)
        if regime.blockers and not (regime.allow_sell_to_buy or regime.allow_buy_to_sell):
            return self._intent(
                symbol=symbol,
                action_type=ActionType.NO_TRADE,
                side=SideCandidate.NONE,
                feature=feature,
                regime=regime,
                deviation=None,
                inventory=None,
                reasons=regime.reasons,
                blockers=regime.blockers,
                warnings=[],
                next_action="Continue watching; regime is not suitable for opening a new T pair",
            )

        deviation = self.evaluate_deviation(feature, position)
        if deviation.side_candidate is SideCandidate.NONE:
            return self._intent(
                symbol=symbol,
                action_type=ActionType.NO_TRADE,
                side=SideCandidate.NONE,
                feature=feature,
                regime=regime,
                deviation=deviation,
                inventory=None,
                reasons=regime.reasons + deviation.reasons,
                blockers=regime.blockers,
                warnings=deviation.warnings,
                next_action="Continue watching; deviation has not reached tradable conditions",
            )

        if deviation.side_candidate is SideCandidate.SELL_TO_BUY and not regime.allow_sell_to_buy:
            return self._watch_intent(symbol, feature, regime, deviation, "Regime blocks or de-risks S->B")
        if deviation.side_candidate is SideCandidate.BUY_TO_SELL and not regime.allow_buy_to_sell:
            return self._watch_intent(symbol, feature, regime, deviation, "Regime blocks or de-risks B->S")

        quality_blocker = self._quality_gate_blocker(feature, deviation, regime)
        if quality_blocker:
            return self._watch_intent(symbol, feature, regime, deviation, quality_blocker)

        inventory = self.evaluate_inventory(feature, position, deviation, regime)
        if not inventory.executable:
            return self._intent(
                symbol=symbol,
                action_type=ActionType.NO_TRADE,
                side=deviation.side_candidate,
                feature=feature,
                regime=regime,
                deviation=deviation,
                inventory=inventory,
                reasons=regime.reasons + deviation.reasons + inventory.reasons,
                blockers=regime.blockers + inventory.blockers,
                warnings=deviation.warnings,
                next_action="Inventory or capital constraints prevent execution",
            )

        action = (
            ActionType.TRIGGER_SELL_TO_BUY
            if deviation.side_candidate is SideCandidate.SELL_TO_BUY
            else ActionType.TRIGGER_BUY_TO_SELL
        )
        next_action = (
            "Allow S->B first leg; wait for reversion zone"
            if action is ActionType.TRIGGER_SELL_TO_BUY
            else "Allow B->S first leg; use sellable inventory to restore target"
        )
        return self._intent(
            symbol=symbol,
            action_type=action,
            side=deviation.side_candidate,
            feature=feature,
            regime=regime,
            deviation=deviation,
            inventory=inventory,
            reasons=regime.reasons + deviation.reasons + inventory.reasons,
            blockers=regime.blockers,
            warnings=deviation.warnings,
            next_action=next_action,
        )

    def build_feature_snapshot(
        self,
        bars: list[MinuteBar],
        market_return: float = 0.0,
        sector_return: float = 0.0,
    ) -> FeatureSnapshot:
        features = build_features(bars)
        latest = features[-1]
        bar = latest.bar
        day_open = bars[0].open
        day_high = max(item.high for item in bars)
        day_low = min(item.low for item in bars)
        day_range = max(day_high - day_low, 0.01)
        recent_window = bars[-6:]
        recent_return = bar.close / recent_window[0].open - 1.0 if recent_window else 0.0
        recent_high_breaks = _count_recent_breaks([item.high for item in recent_window], higher=True)
        recent_low_breaks = _count_recent_breaks([item.low for item in recent_window], higher=False)
        zscore = _rolling_zscore([row.vwap_deviation for row in features], window=30)
        opening_range = bars[: min(30, len(bars))]
        opening_high = max(item.high for item in opening_range)
        opening_low = min(item.low for item in opening_range)
        opening_break = None
        if len(bars) > len(opening_range):
            if bar.close > opening_high:
                opening_break = "UP"
            elif bar.close < opening_low:
                opening_break = "DOWN"
        day_return = bar.close / day_open - 1.0
        residual = day_return - self.rules.beta_market * market_return - self.rules.beta_sector * sector_return
        near_upper = day_return >= self.rules.price_limit_pct - self.rules.near_limit_buffer_pct
        near_lower = day_return <= -self.rules.price_limit_pct + self.rules.near_limit_buffer_pct
        anchor_type, target_reason = _anchor_diagnostics(bars, [row.vwap for row in features])
        return FeatureSnapshot(
            timestamp=str(bar.ts),
            price=bar.close,
            vwap=latest.vwap,
            anchored_vwap=latest.vwap,
            vwap_deviation=latest.vwap_deviation,
            anchored_vwap_deviation=latest.vwap_deviation,
            residual_return=residual,
            time_normalized_zscore=zscore,
            amount_ratio=latest.amount_ratio,
            day_return=day_return,
            day_position=(bar.close - day_low) / day_range,
            recent_return=recent_return,
            recent_high_breaks=recent_high_breaks,
            recent_low_breaks=recent_low_breaks,
            opening_range_break=opening_break,
            minutes_to_close=_minutes_to_close(bar, self.rules.close_time),
            near_upper_limit=near_upper,
            near_lower_limit=near_lower,
            exhaustion_score=_exhaustion_score(bars),
            anchor_type=anchor_type,
            target_reason=target_reason,
        )

    def evaluate_regime(self, feature: FeatureSnapshot) -> RegimeDecision:
        minute = feature.timestamp[11:16]
        reasons: list[str] = []
        blockers: list[str] = []
        allow_stb = True
        allow_bts = True
        regime = RegimeType.MEAN_REVERTING
        profile = "RANGE"
        stb_position_multiplier = 1.0
        bts_position_multiplier = 1.0
        stb_trigger_multiplier = 1.0
        bts_trigger_multiplier = 1.0

        if minute < self.rules.start_time:
            return RegimeDecision(
                regime_type=RegimeType.NO_TRADE,
                allow_sell_to_buy=False,
                allow_buy_to_sell=False,
                confidence=90,
                blockers=["Opening noise window; do not open a new pair"],
            )
        if minute >= self.rules.force_restore_time:
            return RegimeDecision(
                regime_type=RegimeType.LATE_SESSION,
                allow_sell_to_buy=False,
                allow_buy_to_sell=False,
                confidence=95,
                blockers=["Force-restore window near close"],
            )
        if minute >= self.rules.no_new_trade_after or minute >= self.rules.latest_open_time:
            return RegimeDecision(
                regime_type=RegimeType.LATE_SESSION,
                allow_sell_to_buy=False,
                allow_buy_to_sell=False,
                confidence=88,
                blockers=["Too late to open a new T pair"],
            )
        if feature.near_upper_limit or feature.near_lower_limit:
            return RegimeDecision(
                regime_type=RegimeType.LIMIT_RISK,
                allow_sell_to_buy=False,
                allow_buy_to_sell=False,
                confidence=90,
                blockers=["Near price limit risk zone; do not mechanically trade"],
            )
        if feature.amount_ratio < 0.20:
            return RegimeDecision(
                regime_type=RegimeType.ILLIQUID,
                allow_sell_to_buy=False,
                allow_buy_to_sell=False,
                confidence=80,
                blockers=["Current turnover is too low for reliable execution"],
            )

        crash_down = (
            feature.day_return <= -self.rules.crash_day_return_pct
            and feature.recent_return <= -self.rules.crash_recent_return_pct
            and feature.day_position <= 0.20
        )
        strong_down = (
            feature.day_return <= -self.rules.trend_day_return_pct
            and feature.recent_return <= -self.rules.trend_recent_return_pct
            and feature.day_position <= 0.30
        )
        weak_down = (
            (feature.day_return <= -(self.rules.trend_day_return_pct * 0.50)
            or feature.recent_return <= -self.rules.trend_recent_return_pct)
            and feature.day_position <= 0.45
            and feature.recent_low_breaks >= 2
        )

        if (
            feature.day_return >= self.rules.trend_day_return_pct
            and feature.recent_return >= self.rules.trend_recent_return_pct
            and feature.day_position >= 0.70
        ):
            regime = RegimeType.TREND_UP
            profile = "STRONG_TREND_UP"
            allow_stb = False
            reasons.append("One-way uptrend; suppress S->B to avoid selling into momentum")
        elif crash_down:
            regime = RegimeType.TREND_DOWN
            allow_bts = False
            profile = "CRASH_DOWN"
            bts_trigger_multiplier = self.rules.strong_trend_trigger_multiplier
            reasons.append("Crash-like downtrend; block B->S and avoid adding into weakness")
        elif strong_down:
            regime = RegimeType.TREND_DOWN
            profile = "STRONG_TREND_DOWN"
            bts_position_multiplier = self.rules.strong_trend_position_multiplier
            bts_trigger_multiplier = self.rules.strong_trend_trigger_multiplier
            reasons.append(
                "Strong downtrend; B->S is probe-only and requires extreme deviation plus strong exhaustion"
            )
        elif weak_down:
            regime = RegimeType.TREND_DOWN
            profile = "WEAK_DOWN"
            bts_position_multiplier = self.rules.weak_trend_position_multiplier
            bts_trigger_multiplier = self.rules.weak_trend_trigger_multiplier
            reasons.append("Weak downtrend; B->S is allowed only as reduced-size probe")
        else:
            reasons.append("No strong trend or extreme liquidity regime detected; allow both sides to watch")

        confidence = 65
        if regime is not RegimeType.MEAN_REVERTING:
            confidence = 78
        return RegimeDecision(
            regime_type=regime,
            allow_sell_to_buy=allow_stb,
            allow_buy_to_sell=allow_bts,
            confidence=confidence,
            reasons=reasons,
            blockers=blockers,
            regime_profile=profile,
            sell_to_buy_position_multiplier=stb_position_multiplier,
            buy_to_sell_position_multiplier=bts_position_multiplier,
            sell_to_buy_trigger_multiplier=stb_trigger_multiplier,
            buy_to_sell_trigger_multiplier=bts_trigger_multiplier,
        )

    def evaluate_deviation(
        self,
        feature: FeatureSnapshot,
        position: PositionState,
    ) -> DeviationDecision:
        candidate = SideCandidate.NONE
        reasons: list[str] = []
        warnings: list[str] = []
        price = feature.price
        preliminary_qty = self._preliminary_qty(position, feature.price)
        expected_price: float | None = None
        invalidation_price: float | None = None
        gross_edge = 0.0
        reason_codes: list[str] = []
        blocked_reasons: list[str] = []
        target_reason = feature.target_reason or "VWAP treated as the mean-reversion anchor."

        if feature.vwap_deviation >= self.rules.sb_watch_deviation:
            candidate = SideCandidate.SELL_TO_BUY
            expected_price = min(feature.vwap, price * (1.0 - self.rules.expected_reversion_pct))
            invalidation_price = price * (1.0 + self.rules.expected_reversion_pct)
            gross_edge = max(0.0, price - expected_price) * preliminary_qty
            reasons.append("Price is above VWAP")
            reason_codes.append("SB_ABOVE_VWAP")
            if feature.recent_high_breaks >= 3:
                warnings.append("Recent consecutive highs; deviation may still extend")
                blocked_reasons.append("RECENT_HIGH_BREAKS")
        elif feature.vwap_deviation <= self.rules.bs_watch_deviation:
            candidate = SideCandidate.BUY_TO_SELL
            if feature.anchor_type == "VWAP_RESISTANCE":
                repair_target = price + max(0.0, feature.vwap - price) * 0.40
                expected_price = max(price * (1.0 + self.rules.expected_reversion_pct), repair_target)
                target_reason = feature.target_reason or "VWAP looks like resistance; target downgraded to a partial repair zone."
                reason_codes.append("VWAP_RESISTANCE_TARGET_DOWNGRADED")
            else:
                expected_price = max(feature.vwap, price * (1.0 + self.rules.expected_reversion_pct))
            invalidation_price = price * (1.0 - self.rules.expected_reversion_pct)
            gross_edge = max(0.0, expected_price - price) * preliminary_qty
            reasons.append("Price is below VWAP")
            reason_codes.append("BS_BELOW_VWAP")
            if feature.exhaustion_score >= 65:
                reasons.append(f"Downside exhaustion score is supportive: {feature.exhaustion_score:.0f}/100")
                reason_codes.append("DOWNSIDE_EXHAUSTION_SUPPORTIVE")
            elif feature.exhaustion_score >= 40:
                reasons.append(f"Downside exhaustion is partial: {feature.exhaustion_score:.0f}/100")
                reason_codes.append("DOWNSIDE_EXHAUSTION_PARTIAL")
            else:
                warnings.append(f"Downside exhaustion is weak: {feature.exhaustion_score:.0f}/100")
                blocked_reasons.append("DOWNSIDE_EXHAUSTION_WEAK")
            if feature.recent_low_breaks >= 3:
                warnings.append("Recent consecutive lows; deviation may still extend")
                blocked_reasons.append("RECENT_LOW_BREAKS")
        else:
            return DeviationDecision(
                side_candidate=SideCandidate.NONE,
                deviation_score=0.0,
                expected_reversion_zone=None,
                invalidation_price=None,
                max_wait_minutes=self.rules.max_wait_minutes,
                gross_edge_estimate=0.0,
                net_edge_after_fee=0.0,
                estimated_fee=0.0,
                estimated_slippage=0.0,
                anchor_type=feature.anchor_type,
                target_reason=feature.target_reason,
                exhaustion_score=feature.exhaustion_score,
                liquidity_score=min(100.0, feature.amount_ratio * 50.0),
                reason_codes=["DEVIATION_BELOW_WATCH"],
                reasons=["Deviation has not reached watch threshold"],
            )

        fee, slippage, buy_cost, sell_cost = self._round_trip_cost(candidate, price, expected_price or price, preliminary_qty)
        risk_buffer = price * preliminary_qty * self.rules.risk_buffer_pct
        net_edge = gross_edge - fee - slippage - risk_buffer
        notional = max(0.000001, price * preliminary_qty)
        expected_gross_edge_bps = (gross_edge / notional) * 10000.0 if preliminary_qty > 0 else 0.0
        round_trip_cost_bps = ((fee + slippage) / notional) * 10000.0 if preliminary_qty > 0 else 0.0
        net_edge_bps = expected_gross_edge_bps - round_trip_cost_bps
        trigger_threshold = (
            self.rules.sb_trigger_deviation
            if candidate is SideCandidate.SELL_TO_BUY
            else abs(self.rules.bs_trigger_deviation)
        )
        deviation_score = abs(feature.vwap_deviation) / trigger_threshold if trigger_threshold else 0.0
        if feature.amount_ratio < self.rules.min_amount_ratio:
            warnings.append("Turnover confirmation is weak; deviation reliability is lower")
            blocked_reasons.append("LIQUIDITY_BELOW_TRIGGER_REQUIREMENT")
        if feature.time_normalized_zscore:
            reasons.append(f"时间标准化z-score={feature.time_normalized_zscore:.2f}")
        if net_edge <= self.rules.min_net_edge or net_edge_bps < self.rules.min_edge_buffer_bps:
            blocked_reasons.append("EDGE_AFTER_COST_BELOW_MINIMUM")
        return DeviationDecision(
            side_candidate=candidate,
            deviation_score=round(deviation_score, 4),
            expected_reversion_zone=round(expected_price, 4) if expected_price is not None else None,
            invalidation_price=round(invalidation_price, 4) if invalidation_price is not None else None,
            max_wait_minutes=self.rules.max_wait_minutes,
            gross_edge_estimate=round(gross_edge, 4),
            net_edge_after_fee=round(net_edge, 4),
            estimated_fee=round(fee, 4),
            estimated_slippage=round(slippage, 4),
            expected_gross_edge_bps=round(expected_gross_edge_bps, 4),
            estimated_buy_cost=round(buy_cost, 4),
            estimated_sell_cost=round(sell_cost, 4),
            estimated_round_trip_cost_bps=round(round_trip_cost_bps, 4),
            net_edge_bps=round(net_edge_bps, 4),
            min_edge_buffer_bps=round(self.rules.min_edge_buffer_bps, 4),
            anchor_type=feature.anchor_type,
            target_reason=target_reason,
            exhaustion_score=round(feature.exhaustion_score, 2),
            liquidity_score=round(min(100.0, feature.amount_ratio * 50.0), 2),
            reason_codes=reason_codes,
            blocked_reasons=blocked_reasons,
            reasons=reasons,
            warnings=warnings,
        )

    def evaluate_inventory(
        self,
        feature: FeatureSnapshot,
        position: PositionState,
        deviation: DeviationDecision,
        regime: RegimeDecision | None = None,
    ) -> InventoryDecision:
        base_qty = self._preliminary_qty(position, feature.price)
        qty = base_qty
        if regime is not None:
            if deviation.side_candidate is SideCandidate.SELL_TO_BUY:
                multiplier = regime.sell_to_buy_position_multiplier
            elif deviation.side_candidate is SideCandidate.BUY_TO_SELL:
                multiplier = regime.buy_to_sell_position_multiplier
            else:
                multiplier = 1.0
            if multiplier < 1.0:
                qty = _round_lot(base_qty * max(0.0, multiplier), self.rules.lot_size)
            else:
                qty = base_qty
        risk_limit_qty = self._risk_limit_qty(position, feature.price)
        blockers: list[str] = []
        reasons: list[str] = []
        if regime is not None and qty < base_qty:
            reasons.append(
                f"Regime position multiplier applied: {qty}/{base_qty} shares "
                f"under {regime.regime_profile}"
            )
        if risk_limit_qty < self._base_qty(position):
            reasons.append(
                "Risk preset caps single-pair size: "
                f"turnover<={self.rules.max_daily_turnover_ratio:.0%}, "
                f"capital_at_risk<={self.rules.max_same_day_capital_at_risk_ratio:.0%}, "
                f"max_open_pair={self.rules.max_wait_minutes}m"
            )
        if qty < self.rules.minimum_order_qty:
            blockers.append("Suggested quantity is below the minimum order size")
        if deviation.side_candidate is SideCandidate.SELL_TO_BUY:
            if position.settled_sellable_qty < qty:
                blockers.append("Settled sellable quantity is insufficient for S->B")
            inventory_delta = -qty
            capital_required = 0.0
            sellable_after = max(0, position.settled_sellable_qty - qty)
            reasons.append("S->B only uses settled sellable inventory")
        elif deviation.side_candidate is SideCandidate.BUY_TO_SELL:
            if position.purchasable_qty < qty:
                blockers.append("Purchasable quantity is insufficient for B->S")
            if position.settled_sellable_qty < qty:
                blockers.append("Sellable old inventory is insufficient to complete B->S loop")
            capital_required = qty * feature.price
            if position.cash_available is not None and position.cash_available < capital_required:
                blockers.append("Cash available is insufficient for B->S")
            inventory_delta = qty
            sellable_after = position.settled_sellable_qty
            reasons.append("B->S buy leg must be restored by selling existing sellable inventory")
        else:
            blockers.append("No executable side")
            inventory_delta = 0
            capital_required = 0.0
            sellable_after = position.settled_sellable_qty

        max_deviation = max(self.rules.minimum_order_qty, _round_lot(position.target_qty * self.rules.max_t_ratio, self.rules.lot_size))
        if abs(inventory_delta) > max_deviation:
            blockers.append("Inventory deviation would exceed the maximum allowed range")

        suggested_ratio = qty / position.target_qty if position.target_qty else 0.0
        return InventoryDecision(
            executable=not blockers,
            suggested_qty=qty if not blockers else 0,
            suggested_ratio=round(suggested_ratio, 6),
            capital_required=round(capital_required, 4),
            sellable_after_trade=sellable_after,
            inventory_delta_after_trade=inventory_delta,
            reasons=reasons,
            blockers=blockers,
        )

    def _manage_open_pair(
        self,
        symbol: str,
        feature: FeatureSnapshot,
        position: PositionState,
    ) -> TradeIntent:
        side_text = (position.open_pair_side or "").upper()
        open_price = position.open_pair_price or feature.price
        pair_qty = position.open_pair_qty or self._preliminary_qty(position, feature.price)
        force = feature.timestamp[11:16] >= self.rules.force_restore_time
        if side_text == "SB":
            edge_per_share = open_price - feature.price
            expected_price = feature.price
            invalidation = open_price * (1.0 + self.rules.expected_reversion_pct)
            next_action = "Open SB pair exists; manage buyback first"
        elif side_text == "BS":
            edge_per_share = feature.price - open_price
            expected_price = feature.price
            invalidation = open_price * (1.0 - self.rules.expected_reversion_pct)
            next_action = "Open BS pair exists; manage sell leg first"
        else:
            edge_per_share = 0.0
            expected_price = feature.price
            invalidation = None
            next_action = "Unknown open_pair_side; restore target inventory first"
            force = True
        action = ActionType.FORCE_CLOSE_OR_RESTORE if force else ActionType.MANAGE_OPEN_PAIR
        reason = "Force restore near close" if force else "Open pair exists; do not open a new pair"
        return TradeIntent(
            action_type=action,
            symbol=symbol,
            timestamp=feature.timestamp,
            side=SideCandidate.NONE,
            suggested_qty=pair_qty,
            suggested_ratio=round(pair_qty / position.target_qty, 6) if position.target_qty else 0.0,
            reference_price=feature.price,
            trigger_price=feature.price,
            expected_reversion_price=round(expected_price, 4),
            invalidation_price=round(invalidation, 4) if invalidation is not None else None,
            max_wait_minutes=0 if force else self.rules.max_wait_minutes,
            estimated_gross_edge=round(edge_per_share * pair_qty, 4),
            estimated_fee=0.0,
            estimated_slippage=0.0,
            estimated_net_edge=round(edge_per_share * pair_qty, 4),
            expected_cost_reduction_per_share=round(edge_per_share, 4),
            confidence=90 if force else 75,
            regime_type=RegimeType.LATE_SESSION if force else RegimeType.MEAN_REVERTING,
            reasons=[reason],
            blockers=[],
            warnings=[],
            next_action=next_action,
            feature_snapshot=feature,
        )

    def _watch_intent(
        self,
        symbol: str,
        feature: FeatureSnapshot,
        regime: RegimeDecision,
        deviation: DeviationDecision,
        blocker: str,
    ) -> TradeIntent:
        action = (
            ActionType.WATCH_SELL_TO_BUY
            if deviation.side_candidate is SideCandidate.SELL_TO_BUY
            else ActionType.WATCH_BUY_TO_SELL
        )
        return self._intent(
            symbol=symbol,
            action_type=action,
            side=deviation.side_candidate,
            feature=feature,
            regime=regime,
            deviation=deviation,
            inventory=None,
            reasons=regime.reasons + deviation.reasons,
            blockers=regime.blockers + [blocker],
            warnings=deviation.warnings,
            next_action="Continue watching; do not open a new T pair",
        )

    def _quality_gate_blocker(
        self,
        feature: FeatureSnapshot,
        deviation: DeviationDecision,
        regime: RegimeDecision,
    ) -> str | None:
        required_score = self._required_deviation_score(deviation, regime)
        side_label = "S->B" if deviation.side_candidate is SideCandidate.SELL_TO_BUY else "B->S"
        if deviation.deviation_score < required_score:
            return (
                f"Signal quality gate: {side_label} deviation strength below "
                f"regime-adjusted trigger threshold ({deviation.deviation_score:.2f} < {required_score:.2f})"
            )
        if deviation.side_candidate is SideCandidate.BUY_TO_SELL:
            if (
                regime.regime_profile == "WEAK_DOWN"
                and deviation.exhaustion_score < self.rules.bs_probe_exhaustion_score
            ):
                return (
                    "Signal quality gate: B->S weak-down probe requires downside exhaustion "
                    f">={self.rules.bs_probe_exhaustion_score:.0f}/100"
                )
            if (
                regime.regime_profile == "STRONG_TREND_DOWN"
                and deviation.exhaustion_score < self.rules.bs_strong_down_exhaustion_score
            ):
                return (
                    "Signal quality gate: B->S strong-down probe requires strong downside exhaustion "
                    f">={self.rules.bs_strong_down_exhaustion_score:.0f}/100"
                )
        if feature.amount_ratio < self.rules.min_amount_ratio:
            return "Signal quality gate: liquidity confirmation below trigger requirement"
        if deviation.net_edge_after_fee <= self.rules.min_net_edge:
            return "Signal quality gate: post-cost edge below minimum"
        if deviation.net_edge_bps < self.rules.min_edge_buffer_bps:
            return (
                "Signal quality gate: round-trip net edge below buffer "
                f"({deviation.net_edge_bps:.2f} < {self.rules.min_edge_buffer_bps:.2f} bps)"
            )
        return None

    def _required_deviation_score(
        self,
        deviation: DeviationDecision,
        regime: RegimeDecision,
    ) -> float:
        if deviation.side_candidate is SideCandidate.SELL_TO_BUY:
            side_min = self.rules.sb_min_trigger_deviation_score
            regime_multiplier = regime.sell_to_buy_trigger_multiplier
        elif deviation.side_candidate is SideCandidate.BUY_TO_SELL:
            side_min = self.rules.bs_min_trigger_deviation_score
            regime_multiplier = regime.buy_to_sell_trigger_multiplier
        else:
            side_min = self.rules.min_trigger_deviation_score
            regime_multiplier = 1.0
        return max(self.rules.min_trigger_deviation_score, side_min) * max(0.0, regime_multiplier)

    def _intent(
        self,
        symbol: str,
        action_type: ActionType,
        side: SideCandidate,
        feature: FeatureSnapshot,
        regime: RegimeDecision,
        deviation: DeviationDecision | None,
        inventory: InventoryDecision | None,
        reasons: list[str],
        blockers: list[str],
        warnings: list[str],
        next_action: str,
    ) -> TradeIntent:
        suggested_qty = inventory.suggested_qty if inventory else 0
        suggested_ratio = inventory.suggested_ratio if inventory else 0.0
        gross_edge = deviation.gross_edge_estimate if deviation else 0.0
        fee = deviation.estimated_fee if deviation else 0.0
        slippage = deviation.estimated_slippage if deviation else 0.0
        net_edge = deviation.net_edge_after_fee if deviation else 0.0
        per_share = net_edge / suggested_qty if suggested_qty else 0.0
        confidence = min(95, max(regime.confidence, round((deviation.deviation_score if deviation else 0) * 35 + 45)))
        return TradeIntent(
            action_type=action_type,
            symbol=symbol,
            timestamp=feature.timestamp,
            side=side,
            suggested_qty=suggested_qty,
            suggested_ratio=suggested_ratio,
            reference_price=feature.price,
            trigger_price=feature.price if action_type.name.startswith("TRIGGER") else None,
            expected_reversion_price=deviation.expected_reversion_zone if deviation else None,
            invalidation_price=deviation.invalidation_price if deviation else None,
            max_wait_minutes=deviation.max_wait_minutes if deviation else self.rules.max_wait_minutes,
            estimated_gross_edge=gross_edge,
            estimated_fee=fee,
            estimated_slippage=slippage,
            estimated_net_edge=net_edge,
            expected_cost_reduction_per_share=round(per_share, 6),
            confidence=confidence,
            regime_type=regime.regime_type,
            reasons=reasons,
            blockers=blockers,
            warnings=warnings,
            next_action=next_action,
            feature_snapshot=feature,
            regime_decision=regime,
            deviation_decision=deviation,
            inventory_decision=inventory,
        )

    def _preliminary_qty(self, position: PositionState, price: float | None = None) -> int:
        qty = self._base_qty(position)
        qty = min(qty, self._risk_limit_qty(position, price))
        return max(0, qty)

    def _base_qty(self, position: PositionState) -> int:
        qty = _round_lot(position.target_qty * self.rules.max_t_ratio, self.rules.lot_size)
        if self.rules.max_single_trade_qty is not None:
            qty = min(qty, _round_lot(self.rules.max_single_trade_qty, self.rules.lot_size))
        return max(0, qty)

    def _risk_limit_qty(self, position: PositionState, price: float | None = None) -> int:
        if position.target_qty <= 0:
            return 0
        caps = [float(position.target_qty)]
        if self.rules.max_daily_turnover_ratio > 0:
            caps.append(position.target_qty * self.rules.max_daily_turnover_ratio / 2.0)
        if self.rules.max_same_day_capital_at_risk_ratio > 0:
            if price and price > 0:
                target_notional = position.target_qty * price
                caps.append((target_notional * self.rules.max_same_day_capital_at_risk_ratio) / price)
            else:
                caps.append(position.target_qty * self.rules.max_same_day_capital_at_risk_ratio)
        return max(0, _round_lot(min(caps) + 1e-9, self.rules.lot_size))

    def _round_trip_cost(
        self,
        candidate: SideCandidate,
        first_price: float,
        second_price: float,
        qty: int,
    ) -> tuple[float, float, float, float]:
        if qty <= 0:
            return 0.0, 0.0, 0.0, 0.0
        if candidate is SideCandidate.SELL_TO_BUY:
            first = self.fee_model.calculate(Side.SELL, first_price, qty)
            second = self.fee_model.calculate(Side.BUY, second_price, qty)
            sell_cost = first.total_fees + first.slippage
            buy_cost = second.total_fees + second.slippage
        elif candidate is SideCandidate.BUY_TO_SELL:
            first = self.fee_model.calculate(Side.BUY, first_price, qty)
            second = self.fee_model.calculate(Side.SELL, second_price, qty)
            buy_cost = first.total_fees + first.slippage
            sell_cost = second.total_fees + second.slippage
        else:
            return 0.0, 0.0, 0.0, 0.0
        return first.total_fees + second.total_fees, first.slippage + second.slippage, buy_cost, sell_cost


def zero_fee_model() -> FeeModel:
    from core.fee_model import FeeConfig

    return FeeModel(
        FeeConfig(
            market="GENERIC",
            buy_commission_rate=0.0,
            sell_commission_rate=0.0,
            min_commission=0.0,
            stamp_tax_rate=0.0,
            transfer_fee_rate=0.0,
            other_fee_rate=0.0,
            buy_slippage_rate=0.0,
            sell_slippage_rate=0.0,
            a_share_handling_fee_bps=0.0,
            a_share_management_fee_bps=0.0,
            a_share_transfer_fee_bps=0.0,
            a_share_stamp_duty_sell_bps=0.0,
            a_share_broker_commission_bps=0.0,
            a_share_min_commission_cny=0.0,
            us_sec_fee_per_million=0.0,
            us_finra_taf_per_share=0.0,
            us_finra_taf_cap_per_trade=0.0,
            us_broker_commission_per_share=0.0,
            us_broker_min_commission=0.0,
            us_platform_fee_per_order=0.0,
        )
    )


def _round_lot(value: float, lot_size: int) -> int:
    if value <= 0:
        return 0
    return floor(value / lot_size) * lot_size


def _count_recent_breaks(values: list[float], higher: bool) -> int:
    count = 0
    best = values[0] if values else 0.0
    for value in values[1:]:
        if higher and value > best:
            count += 1
            best = value
        elif not higher and value < best:
            count += 1
            best = value
    return count


def _rolling_zscore(values: list[float], window: int) -> float:
    if len(values) < 3:
        return 0.0
    series = values[-window:]
    mean = sum(series) / len(series)
    variance = sum((item - mean) ** 2 for item in series) / len(series)
    std = variance**0.5
    if std == 0:
        return 0.0
    return (values[-1] - mean) / std


def _exhaustion_score(bars: list[MinuteBar]) -> float:
    if len(bars) < 5:
        return 0.0
    latest = bars[-1]
    score = 0.0
    recent5 = bars[-5:]
    recent15 = bars[-15:] if len(bars) >= 15 else bars
    slope5 = recent5[-1].close / recent5[0].open - 1.0 if recent5[0].open else 0.0
    slope15 = recent15[-1].close / recent15[0].open - 1.0 if recent15[0].open else 0.0
    if slope15 < 0 and slope5 > slope15:
        score += 20.0

    if len(bars) >= 10:
        prior_low = min(bar.low for bar in bars[-10:-5])
        recent_low = min(bar.low for bar in recent5)
        if recent_low >= prior_low * 0.997:
            score += 18.0

    if len(bars) >= 6:
        prior_recent_low = min(bar.low for bar in bars[-6:-1])
        if latest.low < prior_recent_low and latest.close > prior_recent_low:
            score += 22.0

    latest_range = latest.high - latest.low
    if latest_range > 0:
        close_location = (latest.close - latest.low) / latest_range
        score += max(0.0, min(20.0, close_location * 20.0))

    down_bars = [bar for bar in bars[-12:] if bar.close < bar.open and bar.volume > 0]
    if len(down_bars) >= 4:
        split = max(1, len(down_bars) // 2)
        early = down_bars[:split]
        late = down_bars[split:]
        if late:
            early_avg = sum(bar.volume for bar in early) / len(early)
            late_avg = sum(bar.volume for bar in late) / len(late)
            if late_avg < early_avg:
                score += 15.0

    if len(bars) >= 6 and latest.close > bars[-2].close:
        avg_volume = sum(bar.volume for bar in bars[-6:-1]) / 5
        if avg_volume > 0 and latest.volume >= avg_volume:
            score += 5.0

    return round(min(100.0, score), 2)


def _anchor_diagnostics(bars: list[MinuteBar], vwap_values: list[float]) -> tuple[str, str]:
    if len(bars) < 8 or len(vwap_values) < 8:
        return "NEUTRAL", "Insufficient history to classify VWAP anchor."
    latest_price = bars[-1].close
    latest_vwap = vwap_values[-1]
    lookback = min(20, len(bars))
    recent_bars = bars[-lookback:]
    recent_vwaps = vwap_values[-lookback:]
    below_ratio = sum(1 for bar, vwap in zip(recent_bars, recent_vwaps) if bar.close < vwap) / lookback
    vwap_base = recent_vwaps[0] or latest_vwap
    vwap_slope = latest_vwap / vwap_base - 1.0 if vwap_base else 0.0
    first_half = recent_bars[: max(1, lookback // 2)]
    falling_highs = recent_bars[-1].high < max(bar.high for bar in first_half)
    falling_lows = recent_bars[-1].low < min(bar.low for bar in first_half)
    if latest_price < latest_vwap and below_ratio >= 0.70 and vwap_slope <= -0.0005 and (falling_highs or falling_lows):
        return "VWAP_RESISTANCE", "VWAP is falling and price has stayed below it; use partial repair target, not full VWAP."
    if abs(vwap_slope) <= 0.0008 and 0.25 <= below_ratio <= 0.75:
        return "VWAP_REVERSION", "VWAP is relatively flat with two-sided trading; full VWAP can remain a reversion anchor."
    return "NEUTRAL", "VWAP anchor is mixed; use conservative reversion target."


def _minutes_to_close(bar: MinuteBar, close_time: str) -> int:
    close_hour, close_minute = (int(part) for part in close_time.split(":", 1))
    return max(0, (close_hour * 60 + close_minute) - (bar.ts.hour * 60 + bar.ts.minute))


def _dataclass_to_dict(value) -> dict:
    payload = value.__dict__.copy()
    for key, item in list(payload.items()):
        if isinstance(item, Enum):
            payload[key] = item.value
    return payload





