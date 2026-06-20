from __future__ import annotations

from datetime import datetime, timedelta

from core.models import MinuteBar


def scenario_mean_revert() -> list[MinuteBar]:
    prices = [10.00, 10.03, 10.08, 10.09, 10.04, 9.98, 9.99, 10.00]
    return _bars_from_prices(prices, amount_multiplier=[1, 1, 2, 2, 1, 2, 1, 1])


def scenario_one_way_up() -> list[MinuteBar]:
    prices = [10.00, 10.03, 10.08, 10.12, 10.16, 10.20, 10.23, 10.26]
    return _bars_from_prices(prices, amount_multiplier=[1, 1, 2, 2, 2, 2, 2, 2])


def scenario_low_liquidity() -> list[MinuteBar]:
    prices = [10.00, 10.01, 10.04, 10.05, 10.03]
    return _bars_from_prices(prices, amount_multiplier=[0.01] * len(prices), volume=100)


def get_scenario(name: str) -> list[MinuteBar]:
    scenarios = {
        "mean_revert": scenario_mean_revert,
        "one_way_up": scenario_one_way_up,
        "low_liquidity": scenario_low_liquidity,
    }
    try:
        return scenarios[name]()
    except KeyError as exc:
        raise ValueError(f"unknown scenario: {name}") from exc


def _bars_from_prices(
    prices: list[float],
    amount_multiplier: list[float],
    volume: int = 10000,
) -> list[MinuteBar]:
    start = datetime(2026, 1, 2, 9, 30)
    bars: list[MinuteBar] = []
    previous = prices[0]
    for index, close in enumerate(prices):
        open_price = previous
        high = max(open_price, close) + 0.01
        low = min(open_price, close) - 0.01
        vol = int(volume * amount_multiplier[index])
        bars.append(
            MinuteBar(
                ts=start + timedelta(minutes=index),
                open=round(open_price, 2),
                high=round(high, 2),
                low=round(low, 2),
                close=round(close, 2),
                volume=vol,
                amount=round(vol * close, 2),
            )
        )
        previous = close
    return bars
