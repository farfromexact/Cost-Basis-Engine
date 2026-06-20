from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from http.client import RemoteDisconnected
from urllib.parse import quote
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from core.models import MinuteBar
from data.validation import validate_minute_bars


YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart"

SAMSUNG_COMMON_SYMBOL = "005930.KS"
SAMSUNG_PREFERRED_SYMBOL = "005935.KS"


def fetch_yahoo_intraday_bars(
    symbol: str,
    timeout: float = 10.0,
    retries: int = 3,
) -> list[MinuteBar]:
    yahoo_symbol = normalize_yahoo_symbol(symbol)
    url = (
        f"{YAHOO_CHART_URL}/{quote(yahoo_symbol)}"
        "?range=1d&interval=1m&includePrePost=false"
    )
    request = Request(
        url,
        headers={"User-Agent": "cost-basis-engine/0.1"},
    )
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            with urlopen(request, timeout=timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
            return parse_yahoo_chart(payload)
        except (OSError, RemoteDisconnected, json.JSONDecodeError) as exc:
            last_error = exc
            if attempt < retries - 1:
                time.sleep(0.5 * (attempt + 1))
                continue
            break
    raise RuntimeError(f"failed to fetch Yahoo minute bars for {yahoo_symbol}: {last_error}") from last_error


def normalize_yahoo_symbol(symbol: str) -> str:
    normalized = symbol.strip()
    upper = normalized.upper()
    compact_upper = upper.replace(" ", "")
    compact_text = normalized.replace(" ", "")
    common_aliases = {
        "SAMSUNG",
        "SAMSUNGELECTRONICS",
        "三星",
        "三星电子",
        "三星電子",
        "삼성",
        "삼성전자",
    }
    preferred_aliases = {
        "SAMSUNGPREFERRED",
        "SAMSUNGELECTRONICSPREFERRED",
        "三星优先股",
        "三星優先股",
        "삼성전자우",
    }
    if compact_upper in common_aliases or compact_text in common_aliases:
        return SAMSUNG_COMMON_SYMBOL
    if compact_upper in preferred_aliases or compact_text in preferred_aliases:
        return SAMSUNG_PREFERRED_SYMBOL
    if upper.endswith((".KS", ".KQ")):
        return upper
    if len(upper) == 6 and upper.isdigit():
        return f"{upper}.KS"
    return upper


def parse_yahoo_chart(payload: dict) -> list[MinuteBar]:
    chart = payload.get("chart") or {}
    error = chart.get("error")
    if error:
        raise ValueError(f"Yahoo chart error: {error}")
    results = chart.get("result") or []
    if not results:
        raise ValueError("Yahoo chart payload has no result rows")

    result = results[0]
    timestamps = result.get("timestamp") or []
    quotes = ((result.get("indicators") or {}).get("quote") or [{}])[0]
    timezone_name = (result.get("meta") or {}).get("exchangeTimezoneName") or "UTC"
    bars: list[MinuteBar] = []
    for index, raw_ts in enumerate(timestamps):
        open_price = _item_at(quotes.get("open"), index)
        high = _item_at(quotes.get("high"), index)
        low = _item_at(quotes.get("low"), index)
        close = _item_at(quotes.get("close"), index)
        volume = _item_at(quotes.get("volume"), index, default=0)
        if None in (open_price, high, low, close):
            continue
        if min(open_price, high, low, close) <= 0:
            continue
        bar_ts = _to_exchange_datetime(int(raw_ts), timezone_name)
        if bar_ts.second != 0 or bar_ts.microsecond != 0:
            continue
        volume_int = int(volume or 0)
        bars.append(
            MinuteBar(
                ts=bar_ts,
                open=float(open_price),
                high=float(high),
                low=float(low),
                close=float(close),
                volume=volume_int,
                # Yahoo's chart API does not expose turnover amount; use a close*volume proxy for VWAP.
                amount=float(close) * volume_int,
            )
        )
    validate_minute_bars(bars)
    return bars


def _item_at(values, index: int, default=None):
    if not values or index >= len(values):
        return default
    return values[index]


def _to_exchange_datetime(raw_ts: int, timezone_name: str) -> datetime:
    try:
        exchange_tz = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        exchange_tz = timezone.utc
    return datetime.fromtimestamp(raw_ts, tz=timezone.utc).astimezone(exchange_tz).replace(tzinfo=None)
