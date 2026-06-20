from datetime import datetime
from zoneinfo import ZoneInfo

from data.yahoo import normalize_yahoo_symbol, parse_yahoo_chart


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
