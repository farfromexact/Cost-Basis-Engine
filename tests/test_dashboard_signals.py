from datetime import datetime, timedelta

import pandas as pd

from app.dashboard import (
    _bars_until_replay_time,
    _current_intent_marker_row,
    _inventory_metric_payload,
    _main_chart_signal_markers,
    _nearest_closed_minute,
    _scan_signal_markers,
    _selected_time_from_chart_event,
)
from core.models import MinuteBar
from research.trigger_engine import ActionType, InventoryDecision, RegimeType, SideCandidate, TradeIntent


def test_scan_signal_markers_finds_sell_to_buy_trigger() -> None:
    markers = _scan_signal_markers(
        symbol="TEST",
        market_source="A 鑲?/ Eastmoney",
        bars=_bars([10.0, 10.0, 10.0, 10.12]),
        held_qty=1000,
        settled_sellable_qty=1000,
        purchasable_qty=1000,
        max_t_ratio=0.10,
        max_single_trade_qty=None,
        ignore_fees=True,
        open_pair_side=None,
        open_pair_price=None,
        open_pair_qty=None,
    )

    assert not markers.empty
    assert "SB" in set(markers["signal"])
    assert markers.iloc[-1]["action"] == "ENTER_SB"
    assert markers.iloc[-1]["state"] == "ENTER"
    assert markers.iloc[-1]["debug_state"] == "PROBE"
    assert "deviation_bps" in markers.columns
    assert "reason_codes" in markers.columns
    assert "why_not_earlier" in markers.columns


def test_scan_signal_markers_ignores_no_trade_points() -> None:
    markers = _scan_signal_markers(
        symbol="TEST",
        market_source="A 鑲?/ Eastmoney",
        bars=_bars([10.0, 10.0, 10.0, 10.01]),
        held_qty=1000,
        settled_sellable_qty=1000,
        purchasable_qty=1000,
        max_t_ratio=0.10,
        max_single_trade_qty=None,
        ignore_fees=True,
        open_pair_side=None,
        open_pair_price=None,
        open_pair_qty=None,
    )

    assert markers.empty


def test_current_intent_marker_uses_latest_closed_minute_decision() -> None:
    market_df = pd.DataFrame(
        [
            {
                "time": pd.Timestamp("2026-06-19 15:00:00"),
                "close": 52.81,
                "vwap_deviation_pct": -0.83,
            }
        ]
    )
    intent = TradeIntent(
        action_type=ActionType.NO_TRADE,
        symbol="603236",
        timestamp="2026-06-19 15:00:00",
        side=SideCandidate.NONE,
        suggested_qty=0,
        suggested_ratio=0.0,
        reference_price=52.81,
        trigger_price=None,
        expected_reversion_price=None,
        invalidation_price=None,
        max_wait_minutes=45,
        estimated_gross_edge=0.0,
        estimated_fee=0.0,
        estimated_slippage=0.0,
        estimated_net_edge=0.0,
        expected_cost_reduction_per_share=0.0,
        confidence=80,
        regime_type=RegimeType.LATE_SESSION,
        blockers=["Close/restore window has priority."],
        next_action="Do not open a new pair.",
    )

    row = _current_intent_marker_row(intent, market_df)

    assert row["time"] == pd.Timestamp("2026-06-19 15:00:00")
    assert row["label"] == "Current: No Trade"
    assert row["action"] == "No Trade"
    assert row["side"] == "None"
    assert row["price"] == 52.81
    assert row["suggested_ratio_pct"] == 0.0
    assert row["vwap_deviation_pct"] == -0.83
    assert row["reason"] == "Close/restore window has priority."
    assert "latest closed minute" in row["note"]


def test_inventory_metric_payload_exposes_sellability_state() -> None:
    intent = TradeIntent(
        action_type=ActionType.TRIGGER_SELL_TO_BUY,
        symbol="603236",
        timestamp="2026-06-19 10:14:00",
        side=SideCandidate.SELL_TO_BUY,
        suggested_qty=100,
        suggested_ratio=0.10,
        reference_price=10.12,
        trigger_price=10.12,
        expected_reversion_price=10.05,
        invalidation_price=10.20,
        max_wait_minutes=45,
        estimated_gross_edge=10.0,
        estimated_fee=0.0,
        estimated_slippage=0.0,
        estimated_net_edge=10.0,
        expected_cost_reduction_per_share=0.10,
        confidence=90,
        regime_type=RegimeType.MEAN_REVERTING,
        inventory_decision=InventoryDecision(
            executable=True,
            suggested_qty=100,
            suggested_ratio=0.10,
            capital_required=0.0,
            sellable_after_trade=900,
            inventory_delta_after_trade=-100,
        ),
    )

    payload = _inventory_metric_payload(intent)

    assert payload["inventory_ok"] is True
    assert payload["sellable_after_trade"] == 900
    assert payload["inventory_delta_after_trade"] == -100
    assert payload["capital_required"] == 0.0


def test_replay_bars_truncate_future_minutes() -> None:
    bars = _bars([10.0, 10.1, 10.2, 10.3])

    replay_bars = _bars_until_replay_time(bars, pd.Timestamp(bars[1].ts))

    assert [bar.close for bar in replay_bars] == [10.0, 10.1]


def test_nearest_closed_minute_selects_closest_point() -> None:
    market_df = pd.DataFrame(
        [
            {"time": pd.Timestamp("2026-06-19 10:31:00")},
            {"time": pd.Timestamp("2026-06-19 10:32:00")},
            {"time": pd.Timestamp("2026-06-19 10:33:00")},
        ]
    )

    selected = _nearest_closed_minute(pd.Timestamp("2026-06-19 10:32:25"), market_df)

    assert selected == pd.Timestamp("2026-06-19 10:32:00")


def test_selected_time_from_chart_event_parses_minute_selection() -> None:
    event = {"selection": {"minute_select": [{"time": "2026-06-19T10:32:00"}]}}

    selected = _selected_time_from_chart_event(event)

    assert selected == pd.Timestamp("2026-06-19 10:32:00")


def test_selected_time_from_chart_event_prefers_local_time_key() -> None:
    event = {"selection": {"minute_select": [{"time_key": "2026-06-19 10:32:00"}]}}

    selected = _selected_time_from_chart_event(event)

    assert selected == pd.Timestamp("2026-06-19 10:32:00")


def test_scan_signal_markers_collapses_continuous_same_side_triggers() -> None:
    markers = _scan_signal_markers(
        symbol="TEST",
        market_source="A 鑲?/ Eastmoney",
        bars=_bars([10.0, 10.0, 10.15, 10.16, 10.17, 10.18]),
        held_qty=1000,
        settled_sellable_qty=1000,
        purchasable_qty=1000,
        max_t_ratio=0.10,
        max_single_trade_qty=None,
        ignore_fees=True,
        open_pair_side=None,
        open_pair_price=None,
        open_pair_qty=None,
        marker_cooldown_minutes=10,
    )

    trigger_signals = list(markers.loc[markers["state"] == "ENTER", "signal"])
    assert trigger_signals == ["SB"]


def test_main_chart_signal_markers_hide_watch_and_debug_only_states() -> None:
    markers = pd.DataFrame(
        [
            {"state": "WATCH", "debug_state": "WATCH", "action": "WATCH_BS"},
            {"state": "ENTER", "debug_state": "PROBE", "action": "ENTER_BS"},
            {"state": "EXIT", "debug_state": "CLOSE_READY", "action": "EXIT_BS"},
            {"state": "ABORT", "debug_state": "BLOCKED", "action": "ABORT_BS"},
        ]
    )

    visible = _main_chart_signal_markers(markers)

    assert list(visible["state"]) == ["ENTER", "EXIT", "ABORT"]
    assert "PROBE" not in set(visible["state"])


def _bars(closes: list[float]) -> list[MinuteBar]:
    start = datetime(2026, 6, 19, 10, 0)
    bars: list[MinuteBar] = []
    previous = closes[0]
    for index, close in enumerate(closes):
        volume = 250_000 if index >= 2 else 100_000
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




