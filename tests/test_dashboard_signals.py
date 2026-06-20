from datetime import datetime, timedelta

from app.dashboard import _scan_signal_markers
from core.models import MinuteBar


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
    assert markers.iloc[-1]["action"] == "Trigger S->B"
    assert markers.iloc[-1]["state"] == "OPEN"


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

    trigger_signals = list(markers.loc[markers["level"] == "Trigger", "signal"])
    assert trigger_signals == ["SB"]


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




