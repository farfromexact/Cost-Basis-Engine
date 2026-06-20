from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from math import floor

from core.models import MinuteBar
from data.validation import validate_minute_bars
from research.features import FeatureRow, build_features


class PromptAction(str, Enum):
    HOLD = "HOLD"
    SB_OPEN = "SB_OPEN"
    BS_OPEN = "BS_OPEN"
    SB_CLOSE = "SB_CLOSE"
    BS_CLOSE = "BS_CLOSE"


@dataclass(frozen=True)
class PromptConfig:
    sb_deviation: float = 0.005
    bs_deviation: float = -0.005
    min_amount_ratio: float = 1.2
    start_time: str = "09:45"
    latest_open_time: str = "14:35"
    buyback_target_pct: float = 0.002
    rebound_target_pct: float = 0.002
    cooldown_minutes: int = 15


@dataclass(frozen=True)
class PromptContext:
    target_qty: int
    settled_sellable_qty: int
    trade_qty: int
    cash_available: float | None = None
    open_pair_side: str | None = None
    open_pair_price: float | None = None
    open_pair_qty: int | None = None


@dataclass(frozen=True)
class IntradayPrompt:
    action: PromptAction
    ts: str
    price: float
    qty: int
    confidence: int
    reason: str
    vwap: float
    vwap_deviation_pct: float
    amount_ratio: float
    day_return_pct: float
    day_position_pct: float
    planned_zone: dict[str, float] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "action": self.action.value,
            "ts": self.ts,
            "price": self.price,
            "qty": self.qty,
            "confidence": self.confidence,
            "reason": self.reason,
            "vwap": self.vwap,
            "vwap_deviation_pct": self.vwap_deviation_pct,
            "amount_ratio": self.amount_ratio,
            "day_return_pct": self.day_return_pct,
            "day_position_pct": self.day_position_pct,
            "planned_zone": self.planned_zone,
            "warnings": self.warnings,
        }


def derive_lot_qty(value: float, price: float, lot_size: int = 100) -> int:
    if value <= 0 or price <= 0:
        return 0
    return floor(value / price / lot_size) * lot_size


def evaluate_latest_prompt(
    bars: list[MinuteBar],
    context: PromptContext,
    config: PromptConfig | None = None,
) -> IntradayPrompt:
    validate_minute_bars(bars)
    config = config or PromptConfig()
    features = build_features(bars)
    return _prompt_for_feature(features[-1], bars, context, config)


def scan_prompts(
    bars: list[MinuteBar],
    context: PromptContext,
    config: PromptConfig | None = None,
    max_prompts: int = 10,
) -> list[IntradayPrompt]:
    validate_minute_bars(bars)
    config = config or PromptConfig()
    features = build_features(bars)
    prompts: list[IntradayPrompt] = []
    last_prompt_index = -10_000
    for index, feature in enumerate(features):
        prompt = _prompt_for_feature(feature, bars[: index + 1], context, config)
        if prompt.action is PromptAction.HOLD:
            continue
        if index - last_prompt_index < config.cooldown_minutes:
            continue
        prompts.append(prompt)
        last_prompt_index = index
        if len(prompts) >= max_prompts:
            break
    return prompts


def _prompt_for_feature(
    feature: FeatureRow,
    bars_so_far: list[MinuteBar],
    context: PromptContext,
    config: PromptConfig,
) -> IntradayPrompt:
    bar = feature.bar
    minute = bar.ts.strftime("%H:%M")
    day_open = bars_so_far[0].open
    day_high = max(item.high for item in bars_so_far)
    day_low = min(item.low for item in bars_so_far)
    day_range = max(day_high - day_low, 0.01)
    day_position = (bar.close - day_low) / day_range
    base_warnings = _constraint_warnings(context, bar.close)

    if minute < config.start_time:
        return _hold(feature, bars_so_far, context, "开盘噪音区，暂不提示开新 T", base_warnings)
    close_prompt = _open_pair_close_prompt(feature, bars_so_far, context, config, base_warnings)
    if close_prompt is not None:
        return close_prompt
    if minute >= config.latest_open_time:
        return _hold(feature, bars_so_far, context, "已过开新 T 时间，只适合处理已有仓位", base_warnings)
    if feature.amount_ratio < config.min_amount_ratio:
        return _hold(feature, bars_so_far, context, "成交额未明显放大", base_warnings)

    sb_score = feature.vwap_deviation / config.sb_deviation if config.sb_deviation > 0 else 0
    bs_score = feature.vwap_deviation / config.bs_deviation if config.bs_deviation < 0 else 0

    if feature.vwap_deviation >= config.sb_deviation and sb_score >= bs_score:
        if context.settled_sellable_qty < context.trade_qty:
            return _hold(feature, bars_so_far, context, "可卖底仓不足，不能开 SB", base_warnings)
        confidence = _confidence(abs(sb_score), feature.amount_ratio, day_position)
        return IntradayPrompt(
            action=PromptAction.SB_OPEN,
            ts=str(bar.ts),
            price=bar.close,
            qty=context.trade_qty,
            confidence=confidence,
            reason="价格高于当日 VWAP 且成交额放大，可考虑先卖后买",
            vwap=round(feature.vwap, 4),
            vwap_deviation_pct=round(feature.vwap_deviation * 100, 4),
            amount_ratio=round(feature.amount_ratio, 4),
            day_return_pct=round((bar.close / day_open - 1.0) * 100, 4),
            day_position_pct=round(day_position * 100, 2),
            planned_zone={
                "sell_now": round(bar.close, 4),
                "buyback_reference_vwap": round(feature.vwap, 4),
                "buyback_target": round(bar.close * (1.0 - config.buyback_target_pct), 4),
            },
            warnings=base_warnings,
        )

    if feature.vwap_deviation <= config.bs_deviation:
        if context.cash_available is not None and context.cash_available < context.trade_qty * bar.close:
            return _hold(feature, bars_so_far, context, "现金不足，不能开 BS", base_warnings)
        confidence = _confidence(abs(bs_score), feature.amount_ratio, 1.0 - day_position)
        warnings = list(base_warnings)
        if context.cash_available is None:
            warnings.append("未提供现金余额，BS 只提示机会，不校验买入资金")
        return IntradayPrompt(
            action=PromptAction.BS_OPEN,
            ts=str(bar.ts),
            price=bar.close,
            qty=context.trade_qty,
            confidence=confidence,
            reason="价格低于当日 VWAP 且成交额放大，可考虑先买后卖原有底仓",
            vwap=round(feature.vwap, 4),
            vwap_deviation_pct=round(feature.vwap_deviation * 100, 4),
            amount_ratio=round(feature.amount_ratio, 4),
            day_return_pct=round((bar.close / day_open - 1.0) * 100, 4),
            day_position_pct=round(day_position * 100, 2),
            planned_zone={
                "buy_now": round(bar.close, 4),
                "sell_reference_vwap": round(feature.vwap, 4),
                "sell_target": round(bar.close * (1.0 + config.rebound_target_pct), 4),
            },
            warnings=warnings,
        )

    return _hold(feature, bars_so_far, context, "偏离未达到 SB 或 BS 提示阈值", base_warnings)


def _hold(
    feature: FeatureRow,
    bars_so_far: list[MinuteBar],
    context: PromptContext,
    reason: str,
    warnings: list[str],
) -> IntradayPrompt:
    bar = feature.bar
    day_open = bars_so_far[0].open
    day_high = max(item.high for item in bars_so_far)
    day_low = min(item.low for item in bars_so_far)
    day_range = max(day_high - day_low, 0.01)
    day_position = (bar.close - day_low) / day_range
    return IntradayPrompt(
        action=PromptAction.HOLD,
        ts=str(bar.ts),
        price=bar.close,
        qty=context.trade_qty,
        confidence=0,
        reason=reason,
        vwap=round(feature.vwap, 4),
        vwap_deviation_pct=round(feature.vwap_deviation * 100, 4),
        amount_ratio=round(feature.amount_ratio, 4),
        day_return_pct=round((bar.close / day_open - 1.0) * 100, 4),
        day_position_pct=round(day_position * 100, 2),
        warnings=warnings,
    )


def _open_pair_close_prompt(
    feature: FeatureRow,
    bars_so_far: list[MinuteBar],
    context: PromptContext,
    config: PromptConfig,
    warnings: list[str],
) -> IntradayPrompt | None:
    if not context.open_pair_side or context.open_pair_price is None:
        return None
    side = context.open_pair_side.upper()
    qty = context.open_pair_qty or context.trade_qty
    bar = feature.bar
    minute = bar.ts.strftime("%H:%M")
    day_open = bars_so_far[0].open
    day_high = max(item.high for item in bars_so_far)
    day_low = min(item.low for item in bars_so_far)
    day_range = max(day_high - day_low, 0.01)
    day_position = (bar.close - day_low) / day_range

    if side == "SB":
        target = context.open_pair_price * (1.0 - config.buyback_target_pct)
        should_close = (
            bar.close <= target
            or feature.vwap_deviation <= 0
            or minute >= config.latest_open_time
        )
        if not should_close:
            return _hold(feature, bars_so_far, context, "已有 SB 未闭合，等待买回条件", warnings)
        return IntradayPrompt(
            action=PromptAction.SB_CLOSE,
            ts=str(bar.ts),
            price=bar.close,
            qty=qty,
            confidence=_confidence(abs(feature.vwap_deviation / config.sb_deviation), feature.amount_ratio, 1.0 - day_position),
            reason="已有 SB 未闭合，当前满足买回/时间处理条件",
            vwap=round(feature.vwap, 4),
            vwap_deviation_pct=round(feature.vwap_deviation * 100, 4),
            amount_ratio=round(feature.amount_ratio, 4),
            day_return_pct=round((bar.close / day_open - 1.0) * 100, 4),
            day_position_pct=round(day_position * 100, 2),
            planned_zone={
                "buyback_now": round(bar.close, 4),
                "open_sell_price": round(context.open_pair_price, 4),
                "gross_spread": round(context.open_pair_price - bar.close, 4),
            },
            warnings=warnings,
        )

    if side == "BS":
        target = context.open_pair_price * (1.0 + config.rebound_target_pct)
        should_close = (
            bar.close >= target
            or feature.vwap_deviation >= 0
            or minute >= config.latest_open_time
        )
        if not should_close:
            return _hold(feature, bars_so_far, context, "已有 BS 未闭合，等待卖出条件", warnings)
        return IntradayPrompt(
            action=PromptAction.BS_CLOSE,
            ts=str(bar.ts),
            price=bar.close,
            qty=qty,
            confidence=_confidence(abs(feature.vwap_deviation / config.bs_deviation), feature.amount_ratio, day_position),
            reason="已有 BS 未闭合，当前满足卖出/时间处理条件",
            vwap=round(feature.vwap, 4),
            vwap_deviation_pct=round(feature.vwap_deviation * 100, 4),
            amount_ratio=round(feature.amount_ratio, 4),
            day_return_pct=round((bar.close / day_open - 1.0) * 100, 4),
            day_position_pct=round(day_position * 100, 2),
            planned_zone={
                "sell_now": round(bar.close, 4),
                "open_buy_price": round(context.open_pair_price, 4),
                "gross_spread": round(bar.close - context.open_pair_price, 4),
            },
            warnings=warnings,
        )
    return None


def _confidence(deviation_score: float, amount_ratio: float, day_position_edge: float) -> int:
    raw = 45 + min(deviation_score, 2.0) * 18 + min(amount_ratio, 3.0) * 5 + day_position_edge * 10
    return max(0, min(95, round(raw)))


def _constraint_warnings(context: PromptContext, price: float) -> list[str]:
    warnings: list[str] = []
    if context.trade_qty <= 0:
        warnings.append("trade_qty 未设置为正数")
    if context.target_qty <= 0:
        warnings.append("target_qty 未设置，库存约束不完整")
    if context.settled_sellable_qty < context.trade_qty:
        warnings.append("可卖底仓低于单次做 T 数量")
    if context.cash_available is not None and context.cash_available < context.trade_qty * price:
        warnings.append("现金余额低于单次 BS 买入金额")
    return warnings
