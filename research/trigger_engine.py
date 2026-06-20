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
    max_t_ratio: float = 0.10
    max_single_trade_qty: int | None = None
    start_time: str = "09:45"
    latest_open_time: str = "14:35"
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
    min_trigger_deviation_score: float = 1.0
    trend_day_return_pct: float = 0.02
    trend_recent_return_pct: float = 0.004
    near_limit_buffer_pct: float = 0.015
    max_wait_minutes: int = 45
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


@dataclass(frozen=True)
class RegimeDecision:
    regime_type: RegimeType
    allow_sell_to_buy: bool
    allow_buy_to_sell: bool
    confidence: int
    reasons: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)


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

        quality_blocker = self._quality_gate_blocker(feature, deviation)
        if quality_blocker:
            return self._watch_intent(symbol, feature, regime, deviation, quality_blocker)

        inventory = self.evaluate_inventory(feature, position, deviation)
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
        )

    def evaluate_regime(self, feature: FeatureSnapshot) -> RegimeDecision:
        minute = feature.timestamp[11:16]
        reasons: list[str] = []
        blockers: list[str] = []
        allow_stb = True
        allow_bts = True
        regime = RegimeType.MEAN_REVERTING

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
        if minute >= self.rules.latest_open_time:
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

        if (
            feature.day_return >= self.rules.trend_day_return_pct
            and feature.recent_return >= self.rules.trend_recent_return_pct
            and feature.day_position >= 0.70
        ):
            regime = RegimeType.TREND_UP
            allow_stb = False
            reasons.append("One-way uptrend; suppress S->B to avoid selling into momentum")
        elif (
            feature.day_return <= -self.rules.trend_day_return_pct
            and feature.recent_return <= -self.rules.trend_recent_return_pct
            and feature.day_position <= 0.30
        ):
            regime = RegimeType.TREND_DOWN
            allow_bts = False
            reasons.append("One-way downtrend; suppress B->S to avoid adding into weakness")
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

        if feature.vwap_deviation >= self.rules.sb_watch_deviation:
            candidate = SideCandidate.SELL_TO_BUY
            expected_price = min(feature.vwap, price * (1.0 - self.rules.expected_reversion_pct))
            invalidation_price = price * (1.0 + self.rules.expected_reversion_pct)
            gross_edge = max(0.0, price - expected_price) * preliminary_qty
            reasons.append("Price is above VWAP")
            if feature.recent_high_breaks >= 3:
                warnings.append("Recent consecutive highs; deviation may still extend")
        elif feature.vwap_deviation <= self.rules.bs_watch_deviation:
            candidate = SideCandidate.BUY_TO_SELL
            expected_price = max(feature.vwap, price * (1.0 + self.rules.expected_reversion_pct))
            invalidation_price = price * (1.0 - self.rules.expected_reversion_pct)
            gross_edge = max(0.0, expected_price - price) * preliminary_qty
            reasons.append("Price is below VWAP")
            if feature.recent_low_breaks >= 3:
                warnings.append("Recent consecutive lows; deviation may still extend")
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
                reasons=["Deviation has not reached watch threshold"],
            )

        fee, slippage = self._round_trip_cost(candidate, price, expected_price or price, preliminary_qty)
        risk_buffer = price * preliminary_qty * self.rules.risk_buffer_pct
        net_edge = gross_edge - fee - slippage - risk_buffer
        trigger_threshold = (
            self.rules.sb_trigger_deviation
            if candidate is SideCandidate.SELL_TO_BUY
            else abs(self.rules.bs_trigger_deviation)
        )
        deviation_score = abs(feature.vwap_deviation) / trigger_threshold if trigger_threshold else 0.0
        if feature.amount_ratio < self.rules.min_amount_ratio:
            warnings.append("Turnover confirmation is weak; deviation reliability is lower")
        if feature.time_normalized_zscore:
            reasons.append(f"濠婃艾濮?z-score={feature.time_normalized_zscore:.2f}")
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
            reasons=reasons,
            warnings=warnings,
        )

    def evaluate_inventory(
        self,
        feature: FeatureSnapshot,
        position: PositionState,
        deviation: DeviationDecision,
    ) -> InventoryDecision:
        qty = self._preliminary_qty(position, feature.price)
        risk_limit_qty = self._risk_limit_qty(position, feature.price)
        blockers: list[str] = []
        reasons: list[str] = []
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
    ) -> str | None:
        if deviation.deviation_score < self.rules.min_trigger_deviation_score:
            return "Signal quality gate: deviation strength below trigger threshold"
        if feature.amount_ratio < self.rules.min_amount_ratio:
            return "Signal quality gate: liquidity confirmation below trigger requirement"
        if deviation.net_edge_after_fee <= self.rules.min_net_edge:
            return "Signal quality gate: post-cost edge below minimum"
        return None
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
    ) -> tuple[float, float]:
        if qty <= 0:
            return 0.0, 0.0
        if candidate is SideCandidate.SELL_TO_BUY:
            first = self.fee_model.calculate(Side.SELL, first_price, qty)
            second = self.fee_model.calculate(Side.BUY, second_price, qty)
        elif candidate is SideCandidate.BUY_TO_SELL:
            first = self.fee_model.calculate(Side.BUY, first_price, qty)
            second = self.fee_model.calculate(Side.SELL, second_price, qty)
        else:
            return 0.0, 0.0
        return first.total_fees + second.total_fees, first.slippage + second.slippage


def zero_fee_model() -> FeeModel:
    from core.fee_model import FeeConfig

    return FeeModel(
        FeeConfig(
            buy_commission_rate=0.0,
            sell_commission_rate=0.0,
            min_commission=0.0,
            stamp_tax_rate=0.0,
            transfer_fee_rate=0.0,
            other_fee_rate=0.0,
            buy_slippage_rate=0.0,
            sell_slippage_rate=0.0,
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


def _minutes_to_close(bar: MinuteBar, close_time: str) -> int:
    close_hour, close_minute = (int(part) for part in close_time.split(":", 1))
    return max(0, (close_hour * 60 + close_minute) - (bar.ts.hour * 60 + bar.ts.minute))


def _dataclass_to_dict(value) -> dict:
    payload = value.__dict__.copy()
    for key, item in list(payload.items()):
        if isinstance(item, Enum):
            payload[key] = item.value
    return payload




