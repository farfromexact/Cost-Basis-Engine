from datetime import datetime, timedelta

from core.models import MinuteBar
from research.prompts import (
    PromptAction,
    PromptConfig,
    PromptContext,
    derive_lot_qty,
    evaluate_latest_prompt,
    scan_prompts,
)
from research.scenarios import get_scenario


def test_latest_prompt_flags_sb_when_price_is_extended_above_vwap() -> None:
    prompt = evaluate_latest_prompt(
        get_scenario("one_way_up"),
        PromptContext(target_qty=1000, settled_sellable_qty=1000, trade_qty=100),
        PromptConfig(sb_deviation=0.003, min_amount_ratio=1.0, start_time="09:30"),
    )

    assert prompt.action is PromptAction.SB_OPEN
    assert prompt.planned_zone["buyback_target"] < prompt.price


def test_latest_prompt_flags_bs_when_price_is_depressed_below_vwap() -> None:
    prompt = evaluate_latest_prompt(
        _downtrend_bars(),
        PromptContext(target_qty=1000, settled_sellable_qty=1000, trade_qty=100),
        PromptConfig(bs_deviation=-0.003, min_amount_ratio=1.0),
    )

    assert prompt.action is PromptAction.BS_OPEN
    assert prompt.planned_zone["sell_target"] > prompt.price
    assert "未提供现金余额" in prompt.warnings[0]


def test_prompt_respects_late_open_cutoff() -> None:
    bars = _downtrend_bars(start_hour=14, start_minute=35)
    prompt = evaluate_latest_prompt(
        bars,
        PromptContext(target_qty=1000, settled_sellable_qty=1000, trade_qty=100),
        PromptConfig(bs_deviation=-0.003, min_amount_ratio=1.0, latest_open_time="14:35"),
    )

    assert prompt.action is PromptAction.HOLD
    assert "已过开新 T 时间" in prompt.reason


def test_scan_prompts_applies_cooldown() -> None:
    prompts = scan_prompts(
        get_scenario("one_way_up"),
        PromptContext(target_qty=1000, settled_sellable_qty=1000, trade_qty=100),
        PromptConfig(sb_deviation=0.003, min_amount_ratio=1.0, start_time="09:30", cooldown_minutes=15),
    )

    assert len(prompts) == 1


def test_open_sb_pair_prompts_buyback_before_new_trade() -> None:
    prompt = evaluate_latest_prompt(
        _downtrend_bars(),
        PromptContext(
            target_qty=1000,
            settled_sellable_qty=900,
            trade_qty=100,
            open_pair_side="SB",
            open_pair_price=10.0,
            open_pair_qty=100,
        ),
        PromptConfig(start_time="09:30", buyback_target_pct=0.002),
    )

    assert prompt.action is PromptAction.SB_CLOSE
    assert prompt.planned_zone["gross_spread"] > 0


def test_open_bs_pair_prompts_sell_on_rebound_before_new_trade() -> None:
    prompt = evaluate_latest_prompt(
        get_scenario("one_way_up"),
        PromptContext(
            target_qty=1000,
            settled_sellable_qty=1000,
            trade_qty=100,
            open_pair_side="BS",
            open_pair_price=10.0,
            open_pair_qty=100,
        ),
        PromptConfig(start_time="09:30", rebound_target_pct=0.002),
    )

    assert prompt.action is PromptAction.BS_CLOSE
    assert prompt.planned_zone["gross_spread"] > 0


def test_derive_lot_qty_rounds_down_to_lot() -> None:
    assert derive_lot_qty(8_000_000, 52.81) == 151400


def _downtrend_bars(start_hour: int = 9, start_minute: int = 45) -> list[MinuteBar]:
    prices = [10.0, 9.96, 9.91, 9.88, 9.84, 9.82]
    ts = datetime(2026, 6, 18, start_hour, start_minute)
    bars: list[MinuteBar] = []
    previous = prices[0]
    for index, close in enumerate(prices):
        volume = 100_000 if index else 50_000
        bars.append(
            MinuteBar(
                ts=ts + timedelta(minutes=index),
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
