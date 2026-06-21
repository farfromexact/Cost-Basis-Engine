from datetime import datetime, timedelta

from core.models import MinuteBar
from research.data_quality import build_data_quality_report


def test_data_quality_flags_stale_live_data() -> None:
    bars = _bars(count=40, latest=datetime(2026, 6, 19, 10, 0), amount_offset=0.02)

    report = build_data_quality_report(
        bars,
        market_source="A-share / Eastmoney",
        now=datetime(2026, 6, 19, 10, 20),
    )

    assert report.status == "WARN"
    assert any(check.name == "staleness" and check.status == "WARN" for check in report.checks)
    assert "Downgrade confidence" in report.confidence_note


def test_data_quality_flags_sparse_bars_and_zero_volume() -> None:
    bars = _bars(count=3, latest=datetime(2026, 6, 19, 10, 0), volume=0, amount_offset=0.02)

    report = build_data_quality_report(
        bars,
        market_source="A-share / Eastmoney",
        now=datetime(2026, 6, 19, 10, 0),
    )

    assert report.status == "WARN"
    assert any(check.name == "coverage" and check.status == "WARN" for check in report.checks)
    assert any(check.name == "sparse_volume" and check.status == "WARN" for check in report.checks)


def test_data_quality_flags_yahoo_turnover_approximation() -> None:
    bars = _bars(count=40, latest=datetime(2026, 6, 19, 10, 0), amount_offset=0.0)

    report = build_data_quality_report(
        bars,
        market_source="Korea / Yahoo Finance",
        now=datetime(2026, 6, 19, 10, 0),
    )

    assert report.status == "WARN"
    assert any(check.name == "amount_quality" and check.status == "WARN" for check in report.checks)
    assert any("approximated" in caveat for caveat in report.caveats)


def test_data_quality_flags_us_yahoo_turnover_approximation() -> None:
    bars = _bars(count=40, latest=datetime(2026, 6, 19, 10, 0), amount_offset=0.0)

    report = build_data_quality_report(
        bars,
        market_source="US / Yahoo Finance",
        now=datetime(2026, 6, 19, 10, 0),
    )

    assert report.status == "WARN"
    assert any(check.name == "amount_quality" and check.status == "WARN" for check in report.checks)


def test_data_quality_passes_recent_dense_exchange_turnover() -> None:
    bars = _bars(count=40, latest=datetime(2026, 6, 19, 10, 0), amount_offset=0.02)

    report = build_data_quality_report(
        bars,
        market_source="A-share / Eastmoney",
        now=datetime(2026, 6, 19, 10, 0),
    )

    assert report.status == "OK"
    assert report.caveats == []
    assert "normal interpretation" in report.confidence_note


def _bars(
    count: int,
    latest: datetime,
    volume: int = 10_000,
    amount_offset: float = 0.0,
) -> list[MinuteBar]:
    start = latest - timedelta(minutes=count - 1)
    bars: list[MinuteBar] = []
    for index in range(count):
        ts = start + timedelta(minutes=index)
        close = 10.0 + index * 0.01
        bars.append(
            MinuteBar(
                ts=ts,
                open=close,
                high=close + 0.01,
                low=close - 0.01,
                close=close,
                volume=volume,
                amount=volume * (close + amount_offset),
            )
        )
    return bars
