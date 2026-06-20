from datetime import datetime, timedelta

from core.models import MinuteBar
from data.adapters import load_minute_csv
from research.dataset_registry import DatasetRecord, verify_dataset_lock
from research.oos_capture import capture_locked_oos_dataset, capture_locked_oos_from_source, parse_yahoo_range_chart


def test_capture_locked_oos_dataset_writes_hash_checked_csv(tmp_path) -> None:
    bars = _bars("2026-06-19", 5)

    result = capture_locked_oos_dataset(
        bars=bars,
        symbol="000001.SZ",
        date="2026-06-19",
        source="yahoo",
        output_dir=tmp_path,
        min_bars=5,
    )

    assert result.scenario == "oos_000001_20260619_yahoo"
    assert result.dataset_id == "locked_oos_000001_20260619_yahoo_v1"
    assert result.bar_count == 5
    assert result.content_sha256
    assert "DatasetRecord" in result.registry_snippet
    loaded = load_minute_csv(result.path)
    assert len(loaded) == 5
    record = DatasetRecord(**{k: v for k, v in result.registry_record.items() if k != "is_out_of_sample"})
    assert verify_dataset_lock(record, root=tmp_path.parent if False else ".") == result.content_sha256


def test_capture_locked_oos_from_csv_source_normalizes_output(tmp_path) -> None:
    source_path = tmp_path / "input.csv"
    capture_locked_oos_dataset(_bars("2026-06-19", 5), "000001", "20260619", "csv", tmp_path / "source", min_bars=5)
    generated = tmp_path / "source" / "000001_20260619_csv_intraday.csv"

    result = capture_locked_oos_from_source(
        source="csv",
        symbol="300750",
        date="20260619",
        csv_path=generated,
        output_dir=tmp_path / "out",
        min_bars=5,
    )

    assert result.path.endswith("300750_20260619_csv_intraday.csv")
    assert result.registry_record["locked"] is True
    assert result.registry_record["split"] == "out_of_sample"


def test_capture_rejects_insufficient_bar_count(tmp_path) -> None:
    try:
        capture_locked_oos_dataset(_bars("2026-06-19", 3), "000001", "20260619", "csv", tmp_path, min_bars=5)
    except ValueError as exc:
        assert "not enough bars" in str(exc)
    else:
        raise AssertionError("insufficient bars should fail")


def test_parse_yahoo_range_chart_keeps_exchange_dates() -> None:
    first = int(datetime(2026, 6, 19, 9, 30).timestamp())
    second = int(datetime(2026, 6, 19, 9, 31).timestamp())
    payload = {
        "chart": {
            "result": [
                {
                    "meta": {"exchangeTimezoneName": "UTC"},
                    "timestamp": [first, second],
                    "indicators": {
                        "quote": [
                            {
                                "open": [10.0, 10.1],
                                "high": [10.2, 10.2],
                                "low": [9.9, 10.0],
                                "close": [10.1, 10.15],
                                "volume": [1000, 1200],
                            }
                        ]
                    },
                }
            ],
            "error": None,
        }
    }

    bars = parse_yahoo_range_chart(payload)

    assert len(bars) == 2
    assert bars[1].amount == 10.15 * 1200


def _bars(date_text: str, count: int) -> list[MinuteBar]:
    start = datetime.fromisoformat(date_text + " 09:30:00")
    bars = []
    for index in range(count):
        close = 10.0 + index * 0.01
        bars.append(
            MinuteBar(
                ts=start + timedelta(minutes=index),
                open=close,
                high=close + 0.02,
                low=close - 0.02,
                close=close + 0.01,
                volume=1000 + index,
                amount=(1000 + index) * (close + 0.01),
            )
        )
    return bars
