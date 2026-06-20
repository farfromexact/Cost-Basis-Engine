from __future__ import annotations

import json
import time
from datetime import datetime
from http.client import RemoteDisconnected
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from core.models import MinuteBar
from data.validation import validate_minute_bars


EASTMONEY_TRENDS_URL = "https://push2his.eastmoney.com/api/qt/stock/trends2/get"


def fetch_intraday_minute_bars(
    symbol: str,
    timeout: float = 10.0,
    retries: int = 3,
) -> list[MinuteBar]:
    secid = infer_secid(symbol)
    query = urlencode(
        {
            "fields1": "f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f11,f12,f13",
            "fields2": "f51,f52,f53,f54,f55,f56,f57,f58",
            "ut": "fa5fd1943c7b386f172d6893dbfba10b",
            "ndays": "1",
            "iscr": "0",
            "iscca": "0",
            "secid": secid,
        }
    )
    request = Request(
        f"{EASTMONEY_TRENDS_URL}?{query}",
        headers={"User-Agent": "cost-basis-engine/0.1"},
    )
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            with urlopen(request, timeout=timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
            return parse_eastmoney_trends(payload)
        except (OSError, RemoteDisconnected) as exc:
            last_error = exc
            if attempt < retries - 1:
                time.sleep(0.5 * (attempt + 1))
                continue
            break
    raise RuntimeError(f"failed to fetch Eastmoney minute bars for {symbol}: {last_error}") from last_error


def infer_secid(symbol: str) -> str:
    normalized = symbol.strip().upper()
    if "." in normalized:
        suffix, code = normalized.split(".", 1) if normalized[0].isalpha() else normalized.rsplit(".", 1)
        if suffix in {"SH", "SSE"} or code in {"SH", "SSE"}:
            stock_code = code if suffix in {"SH", "SSE"} else suffix
            return f"1.{stock_code}"
        if suffix in {"SZ", "SZSE"} or code in {"SZ", "SZSE"}:
            stock_code = code if suffix in {"SZ", "SZSE"} else suffix
            return f"0.{stock_code}"
        if normalized.startswith(("0.", "1.")):
            return normalized
    if len(normalized) != 6 or not normalized.isdigit():
        raise ValueError("symbol must be a 6-digit A-share code, e.g. 600519 or 000001")
    if normalized.startswith("6"):
        return f"1.{normalized}"
    if normalized.startswith(("0", "3")):
        return f"0.{normalized}"
    raise ValueError("cannot infer exchange; use 600xxx for SSE or 000/300xxx for SZSE")


def parse_eastmoney_trends(payload: dict) -> list[MinuteBar]:
    data = payload.get("data") or {}
    trends = data.get("trends") or []
    bars = [_parse_trend_row(row) for row in trends]
    validate_minute_bars(bars)
    return bars


def _parse_trend_row(row: str) -> MinuteBar:
    parts = row.split(",")
    if len(parts) < 7:
        raise ValueError(f"unexpected Eastmoney trend row: {row}")
    ts = datetime.strptime(parts[0], "%Y-%m-%d %H:%M")
    open_price = float(parts[1])
    close = float(parts[2])
    high = float(parts[3])
    low = float(parts[4])
    # Eastmoney trend volume is reported in lots (hands), not individual shares.
    volume = int(float(parts[5])) * 100
    amount = float(parts[6])
    return MinuteBar(
        ts=ts,
        open=open_price,
        high=high,
        low=low,
        close=close,
        volume=volume,
        amount=amount,
    )
