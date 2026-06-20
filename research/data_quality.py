from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from core.models import MinuteBar


@dataclass(frozen=True)
class DataQualityCheck:
    name: str
    status: str
    detail: str

    def as_dict(self) -> dict[str, str]:
        return self.__dict__.copy()


@dataclass(frozen=True)
class DataQualityReport:
    status: str
    bar_count: int
    latest_ts: str
    checks: list[DataQualityCheck]
    caveats: list[str]
    confidence_note: str

    def as_dict(self) -> dict:
        return {
            "status": self.status,
            "bar_count": self.bar_count,
            "latest_ts": self.latest_ts,
            "checks": [check.as_dict() for check in self.checks],
            "caveats": self.caveats,
            "confidence_note": self.confidence_note,
        }


def build_data_quality_report(
    bars: list[MinuteBar],
    market_source: str,
    now: datetime | None = None,
    min_bars: int = 30,
    max_live_stale_minutes: int = 10,
    max_zero_volume_ratio: float = 0.30,
) -> DataQualityReport:
    checks: list[DataQualityCheck] = []
    caveats: list[str] = []
    latest_ts = str(bars[-1].ts) if bars else "n/a"

    if not bars:
        return DataQualityReport(
            status="BAD",
            bar_count=0,
            latest_ts=latest_ts,
            checks=[DataQualityCheck("availability", "BAD", "No minute bars were loaded.")],
            caveats=["No signal should be interpreted without minute-bar data."],
            confidence_note="Do not use this output for trading decisions.",
        )

    _add_staleness_check(checks, bars[-1].ts, now, max_live_stale_minutes)
    _add_coverage_check(checks, bars, min_bars, max_zero_volume_ratio)
    _add_amount_quality_check(checks, caveats, bars, market_source)

    status = _rollup_status(checks)
    confidence_note = (
        "Data quality supports normal interpretation."
        if status == "OK"
        else "Downgrade confidence until data-quality warnings are resolved."
    )
    return DataQualityReport(
        status=status,
        bar_count=len(bars),
        latest_ts=latest_ts,
        checks=checks,
        caveats=caveats,
        confidence_note=confidence_note,
    )


def _add_staleness_check(
    checks: list[DataQualityCheck],
    latest_ts: datetime,
    now: datetime | None,
    max_live_stale_minutes: int,
) -> None:
    if now is None:
        checks.append(
            DataQualityCheck(
                "staleness",
                "UNKNOWN",
                f"Latest bar is {latest_ts}; wall-clock freshness was not evaluated.",
            )
        )
        return
    age_seconds = (now - latest_ts).total_seconds()
    if age_seconds < 0:
        checks.append(DataQualityCheck("staleness", "OK", "Latest bar timestamp is not older than the reference time."))
        return
    age_minutes = age_seconds / 60
    if age_minutes > max_live_stale_minutes:
        checks.append(
            DataQualityCheck(
                "staleness",
                "WARN",
                f"Latest bar is {age_minutes:.1f} minutes old, above the {max_live_stale_minutes}-minute live threshold.",
            )
        )
    else:
        checks.append(DataQualityCheck("staleness", "OK", f"Latest bar age is {age_minutes:.1f} minutes."))


def _add_coverage_check(
    checks: list[DataQualityCheck],
    bars: list[MinuteBar],
    min_bars: int,
    max_zero_volume_ratio: float,
) -> None:
    if len(bars) < min_bars:
        checks.append(DataQualityCheck("coverage", "WARN", f"Only {len(bars)} bars loaded; fewer than {min_bars}."))
    else:
        checks.append(DataQualityCheck("coverage", "OK", f"{len(bars)} bars loaded."))

    zero_volume = sum(1 for bar in bars if bar.volume <= 0)
    zero_ratio = zero_volume / len(bars)
    if zero_ratio > max_zero_volume_ratio:
        checks.append(
            DataQualityCheck(
                "sparse_volume",
                "WARN",
                f"{zero_ratio:.1%} of bars have zero volume; intraday signals may be sparse or stale.",
            )
        )
    else:
        checks.append(DataQualityCheck("sparse_volume", "OK", f"{zero_ratio:.1%} zero-volume bars."))


def _add_amount_quality_check(
    checks: list[DataQualityCheck],
    caveats: list[str],
    bars: list[MinuteBar],
    market_source: str,
) -> None:
    is_yahoo = "yahoo" in market_source.lower() or "korea" in market_source.lower()
    close_volume_amount = _amount_matches_close_volume(bars)
    if is_yahoo:
        detail = "Turnover amount is approximated from close * volume for this data source."
        checks.append(DataQualityCheck("amount_quality", "WARN", detail))
        caveats.append(detail)
    elif close_volume_amount:
        detail = "Amount values match close * volume; VWAP may be an approximation rather than exchange turnover."
        checks.append(DataQualityCheck("amount_quality", "WARN", detail))
        caveats.append(detail)
    else:
        checks.append(DataQualityCheck("amount_quality", "OK", "Amount field does not look like close * volume approximation."))


def _amount_matches_close_volume(bars: list[MinuteBar]) -> bool:
    nonzero = [bar for bar in bars if bar.volume > 0 and bar.amount > 0]
    if not nonzero:
        return False
    matches = sum(1 for bar in nonzero if abs(bar.amount - bar.close * bar.volume) <= max(0.01, bar.amount * 0.000001))
    return matches / len(nonzero) >= 0.95


def _rollup_status(checks: list[DataQualityCheck]) -> str:
    if any(check.status == "BAD" for check in checks):
        return "BAD"
    if any(check.status == "WARN" for check in checks):
        return "WARN"
    if any(check.status == "UNKNOWN" for check in checks):
        return "UNKNOWN"
    return "OK"
