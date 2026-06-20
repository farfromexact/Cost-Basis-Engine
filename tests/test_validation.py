from datetime import datetime

import pytest

from core.models import MinuteBar
from data.validation import validate_minute_bars


def test_duplicate_timestamps_are_rejected() -> None:
    ts = datetime(2026, 1, 2, 9, 30)
    bars = [
        MinuteBar(ts, 10, 10.1, 9.9, 10, 100, 1000),
        MinuteBar(ts, 10, 10.1, 9.9, 10, 100, 1000),
    ]

    with pytest.raises(ValueError):
        validate_minute_bars(bars)


def test_disordered_bars_are_rejected() -> None:
    bars = [
        MinuteBar(datetime(2026, 1, 2, 9, 31), 10, 10.1, 9.9, 10, 100, 1000),
        MinuteBar(datetime(2026, 1, 2, 9, 30), 10, 10.1, 9.9, 10, 100, 1000),
    ]

    with pytest.raises(ValueError):
        validate_minute_bars(bars)


def test_inconsistent_ohlc_is_rejected() -> None:
    bars = [MinuteBar(datetime(2026, 1, 2, 9, 30), 10, 10.01, 10.02, 10, 100, 1000)]

    with pytest.raises(ValueError):
        validate_minute_bars(bars)
