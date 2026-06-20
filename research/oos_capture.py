from __future__ import annotations

import csv
import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from core.models import MinuteBar
from data.adapters import load_minute_csv
from data.eastmoney import fetch_intraday_minute_bars
from data.validation import validate_minute_bars
from research.dataset_registry import DatasetRecord, SPLIT_OUT_OF_SAMPLE, file_sha256, verify_dataset_lock


@dataclass(frozen=True)
class LockedOosCaptureResult:
    path: str
    scenario: str
    dataset_id: str
    symbol: str
    date: str
    source: str
    bar_count: int
    start_ts: str
    end_ts: str
    content_sha256: str
    registry_record: dict
    registry_snippet: str
    capability_note: str

    def as_dict(self) -> dict:
        return {
            "path": self.path,
            "scenario": self.scenario,
            "dataset_id": self.dataset_id,
            "symbol": self.symbol,
            "date": self.date,
            "source": self.source,
            "bar_count": self.bar_count,
            "start_ts": self.start_ts,
            "end_ts": self.end_ts,
            "content_sha256": self.content_sha256,
            "registry_record": self.registry_record,
            "registry_snippet": self.registry_snippet,
            "capability_note": self.capability_note,
        }


def capture_locked_oos_dataset(
    bars: list[MinuteBar],
    symbol: str,
    date: str,
    source: str,
    output_dir: str | Path = "datasets/oos",
    min_bars: int = 200,
    scenario: str | None = None,
    dataset_id: str | None = None,
    label: str | None = None,
    overwrite: bool = False,
) -> LockedOosCaptureResult:
    normalized_symbol = _safe_symbol(symbol)
    normalized_date = _safe_date(date)
    normalized_source = _safe_source(source)
    selected = _bars_for_date(bars, normalized_date)
    if len(selected) < min_bars:
        raise ValueError(f"not enough bars for locked OOS capture: {len(selected)} < {min_bars}")
    validate_minute_bars(selected)
    output_path = Path(output_dir) / f"{normalized_symbol}_{normalized_date}_{normalized_source}_intraday.csv"
    if output_path.exists() and not overwrite:
        raise FileExistsError(f"locked OOS output already exists: {output_path}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    _write_minute_csv(output_path, selected)
    digest = file_sha256(output_path)
    scenario_name = scenario or f"oos_{normalized_symbol}_{normalized_date}_{normalized_source}"
    dataset_name = dataset_id or f"locked_oos_{normalized_symbol}_{normalized_date}_{normalized_source}_v1"
    start_ts = str(selected[0].ts)
    end_ts = str(selected[-1].ts)
    record = DatasetRecord(
        dataset_id=dataset_name,
        scenario=scenario_name,
        split=SPLIT_OUT_OF_SAMPLE,
        label=label or f"Locked OOS {normalized_source} intraday sample: {normalized_symbol} on {normalized_date}",
        source=_source_description(normalized_source),
        start_ts=start_ts,
        end_ts=end_ts,
        note=_note_for_source(normalized_source),
        kind="csv",
        data_path=str(output_path).replace("\\", "/"),
        content_sha256=digest,
        locked=True,
    )
    verify_dataset_lock(record)
    return LockedOosCaptureResult(
        path=str(output_path),
        scenario=scenario_name,
        dataset_id=dataset_name,
        symbol=normalized_symbol,
        date=normalized_date,
        source=normalized_source,
        bar_count=len(selected),
        start_ts=start_ts,
        end_ts=end_ts,
        content_sha256=digest,
        registry_record=record.as_dict(),
        registry_snippet=dataset_record_snippet(record),
        capability_note=(
            "Locked OOS capture only: CSV is hash-checked and registry metadata is emitted. "
            "Manual registry review is still required; public-feed data is not broker-confirmed."
        ),
    )


def capture_locked_oos_from_source(
    source: str,
    symbol: str,
    date: str,
    csv_path: str | Path | None = None,
    output_dir: str | Path = "datasets/oos",
    min_bars: int = 200,
    scenario: str | None = None,
    dataset_id: str | None = None,
    label: str | None = None,
    overwrite: bool = False,
    yahoo_range: str = "5d",
) -> LockedOosCaptureResult:
    normalized_source = _safe_source(source)
    if normalized_source == "csv":
        if csv_path is None:
            raise ValueError("csv source requires csv_path")
        bars = load_minute_csv(csv_path)
    elif normalized_source == "eastmoney":
        bars = fetch_intraday_minute_bars(symbol)
    elif normalized_source == "yahoo":
        bars = fetch_yahoo_range_bars(symbol, yahoo_range=yahoo_range)
    else:
        raise ValueError(f"unsupported OOS capture source: {source}")
    return capture_locked_oos_dataset(
        bars=bars,
        symbol=symbol,
        date=date,
        source=normalized_source,
        output_dir=output_dir,
        min_bars=min_bars,
        scenario=scenario,
        dataset_id=dataset_id,
        label=label,
        overwrite=overwrite,
    )


def fetch_yahoo_range_bars(symbol: str, yahoo_range: str = "5d", timeout: float = 15.0) -> list[MinuteBar]:
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{quote(symbol.upper())}?interval=1m&range={yahoo_range}&includePrePost=false"
    request = Request(url, headers={"User-Agent": "cost-basis-engine/0.1"})
    with urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return parse_yahoo_range_chart(payload)


def parse_yahoo_range_chart(payload: dict) -> list[MinuteBar]:
    chart = payload.get("chart") or {}
    if chart.get("error"):
        raise ValueError(f"Yahoo chart error: {chart['error']}")
    results = chart.get("result") or []
    if not results:
        raise ValueError("Yahoo chart payload has no result rows")
    result = results[0]
    timezone_name = (result.get("meta") or {}).get("exchangeTimezoneName") or "Asia/Shanghai"
    tz = ZoneInfo(timezone_name)
    timestamps = result.get("timestamp") or []
    quotes = ((result.get("indicators") or {}).get("quote") or [{}])[0]
    bars: list[MinuteBar] = []
    for index, epoch in enumerate(timestamps):
        ts = datetime.fromtimestamp(int(epoch), tz).replace(tzinfo=None)
        values = [_item_at(quotes.get(name), index) for name in ("open", "high", "low", "close", "volume")]
        if None in values:
            continue
        open_price, high, low, close, volume = values
        if min(open_price, high, low, close) <= 0:
            continue
        volume_int = int(volume or 0)
        bars.append(
            MinuteBar(
                ts=ts,
                open=float(open_price),
                high=float(high),
                low=float(low),
                close=float(close),
                volume=volume_int,
                amount=float(close) * volume_int,
            )
        )
    validate_minute_bars(bars)
    return bars


def dataset_record_snippet(record: DatasetRecord) -> str:
    return (
        f'    "{record.scenario}": DatasetRecord(\n'
        f'        dataset_id="{record.dataset_id}",\n'
        f'        scenario="{record.scenario}",\n'
        f'        split=SPLIT_OUT_OF_SAMPLE,\n'
        f'        label="{record.label}",\n'
        f'        source="{record.source}",\n'
        f'        start_ts="{record.start_ts}",\n'
        f'        end_ts="{record.end_ts}",\n'
        f'        note="{record.note}",\n'
        f'        kind=DATASET_KIND_CSV,\n'
        f'        data_path="{record.data_path}",\n'
        f'        content_sha256="{record.content_sha256}",\n'
        f'        locked=True,\n'
        f'    ),'
    )


def _write_minute_csv(path: Path, bars: list[MinuteBar]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["ts", "open", "high", "low", "close", "volume", "amount"])
        writer.writeheader()
        for bar in bars:
            writer.writerow(
                {
                    "ts": bar.ts.isoformat(sep=" "),
                    "open": bar.open,
                    "high": bar.high,
                    "low": bar.low,
                    "close": bar.close,
                    "volume": bar.volume,
                    "amount": bar.amount,
                }
            )


def _bars_for_date(bars: list[MinuteBar], date: str) -> list[MinuteBar]:
    selected = [bar for bar in bars if bar.ts.strftime("%Y%m%d") == date]
    if not selected:
        raise ValueError(f"no bars found for date {date}")
    return selected


def _item_at(values, index: int):
    if not values or index >= len(values):
        return None
    return values[index]


def _safe_symbol(symbol: str) -> str:
    return symbol.strip().upper().split(".")[0]


def _safe_date(date: str) -> str:
    text = str(date).replace("-", "").strip()
    if len(text) != 8 or not text.isdigit():
        raise ValueError("date must be YYYYMMDD or YYYY-MM-DD")
    return text


def _safe_source(source: str) -> str:
    text = source.strip().lower()
    if text not in {"csv", "eastmoney", "yahoo"}:
        raise ValueError("source must be csv, eastmoney, or yahoo")
    return text


def _source_description(source: str) -> str:
    if source == "eastmoney":
        return "Eastmoney public quote endpoint captured by CLI OOS capture command"
    if source == "yahoo":
        return "Yahoo public chart feed captured by CLI OOS capture command"
    return "Local CSV normalized by CLI OOS capture command"


def _note_for_source(source: str) -> str:
    if source == "yahoo":
        return "Locked public-chart minute bars; turnover amount is approximated as close * volume; not broker-confirmed market data."
    if source == "eastmoney":
        return "Locked public-quote minute bars; not broker-confirmed market data."
    return "Locked local CSV minute bars; source provenance must be reviewed before registry inclusion."
