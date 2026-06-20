from datetime import datetime
from zoneinfo import ZoneInfo

from core.models import MinuteBar
from data.yahoo import latest_usable_yahoo_session, normalize_yahoo_symbol, parse_yahoo_chart


def test_normalize_yahoo_symbol_for_samsung_aliases() -> None:
    assert normalize_yahoo_symbol("005930") == "005930.KS"
    assert normalize_yahoo_symbol("005930.KS") == "005930.KS"
    assert normalize_yahoo_symbol("三星") == "005930.KS"
    assert normalize_yahoo_symbol("Samsung Electronics") == "005930.KS"
    assert normalize_yahoo_symbol("三星优先股") == "005935.KS"


def test_parse_yahoo_chart_payload() -> None:
    first = int(datetime(2026, 6, 19, 9, 0, tzinfo=ZoneInfo("Asia/Seoul")).timestamp())
    second = int(datetime(2026, 6, 19, 9, 1, tzinfo=ZoneInfo("Asia/Seoul")).timestamp())
    payload = {
        "chart": {
            "result": [
                {
                    "meta": {"exchangeTimezoneName": "Asia/Seoul"},
                    "timestamp": [first, second],
                    "indicators": {
                        "quote": [
                            {
                                "open": [75000.0, 75100.0],
                                "high": [75200.0, 75300.0],
                                "low": [74900.0, 75000.0],
                                "close": [75100.0, 75200.0],
                                "volume": [120000, 150000],
                            }
                        ]
                    },
                }
            ],
            "error": None,
        }
    }

    bars = parse_yahoo_chart(payload)

    assert len(bars) == 2
    assert bars[0].ts.strftime("%H:%M") == "09:00"
    assert bars[1].close == 75200.0
    assert bars[1].volume == 150000
    assert bars[1].amount == 75200.0 * 150000


def test_parse_yahoo_chart_skips_unclosed_current_minute() -> None:
    closed = int(datetime(2026, 6, 19, 9, 0, tzinfo=ZoneInfo("Asia/Seoul")).timestamp())
    partial = int(datetime(2026, 6, 19, 9, 1, 23, tzinfo=ZoneInfo("Asia/Seoul")).timestamp())
    payload = {
        "chart": {
            "result": [
                {
                    "meta": {"exchangeTimezoneName": "Asia/Seoul"},
                    "timestamp": [closed, partial],
                    "indicators": {
                        "quote": [
                            {
                                "open": [75000.0, 75100.0],
                                "high": [75200.0, 75300.0],
                                "low": [74900.0, 75000.0],
                                "close": [75100.0, 75200.0],
                                "volume": [120000, 0],
                            }
                        ]
                    },
                }
            ],
            "error": None,
        }
    }

    bars = parse_yahoo_chart(payload)

    assert len(bars) == 1
    assert bars[0].ts.strftime("%H:%M:%S") == "09:00:00"


def test_latest_usable_yahoo_session_skips_sparse_latest_day() -> None:
    previous_day = [
        _bar(datetime(2026, 6, 18, 9, 0), 75000.0),
        _bar(datetime(2026, 6, 18, 9, 1), 75100.0),
        _bar(datetime(2026, 6, 18, 9, 2), 75200.0),
        _bar(datetime(2026, 6, 18, 9, 3), 75300.0),
        _bar(datetime(2026, 6, 18, 9, 4), 75400.0),
    ]
    sparse_latest_day = [_bar(datetime(2026, 6, 19, 9, 0), 76000.0)]

    selected = latest_usable_yahoo_session(previous_day + sparse_latest_day, min_session_bars=5)

    assert [bar.ts.date().isoformat() for bar in selected] == ["2026-06-18"] * 5
    assert selected[-1].close == 75400.0


def _bar(ts: datetime, close: float) -> MinuteBar:
    return MinuteBar(
        ts=ts,
        open=close,
        high=close + 100.0,
        low=close - 100.0,
        close=close,
        volume=1000,
        amount=close * 1000,
    )
