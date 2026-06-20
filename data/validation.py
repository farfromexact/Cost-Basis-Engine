from __future__ import annotations

from core.models import MinuteBar


def validate_minute_bars(bars: list[MinuteBar]) -> None:
    if not bars:
        raise ValueError("minute bars cannot be empty")
    previous_ts = None
    seen = set()
    for bar in bars:
        if bar.ts in seen:
            raise ValueError(f"duplicate timestamp: {bar.ts}")
        seen.add(bar.ts)
        if previous_ts is not None and bar.ts <= previous_ts:
            raise ValueError("minute bars must be strictly increasing")
        previous_ts = bar.ts
        if min(bar.open, bar.high, bar.low, bar.close) <= 0:
            raise ValueError("prices must be positive")
        if bar.high < max(bar.open, bar.close) or bar.low > min(bar.open, bar.close):
            raise ValueError("OHLC range is inconsistent")
        if bar.volume < 0 or bar.amount < 0:
            raise ValueError("volume and amount cannot be negative")
