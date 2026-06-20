from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

from core.models import MinuteBar
from data.validation import validate_minute_bars


def load_minute_csv(path: str | Path) -> list[MinuteBar]:
    rows: list[MinuteBar] = []
    with Path(path).open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            rows.append(
                MinuteBar(
                    ts=datetime.fromisoformat(row["ts"]),
                    open=float(row["open"]),
                    high=float(row["high"]),
                    low=float(row["low"]),
                    close=float(row["close"]),
                    volume=int(row["volume"]),
                    amount=float(row["amount"]),
                )
            )
    validate_minute_bars(rows)
    return rows
