from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

from core.models import MinuteBar
from research.oos_capture import capture_locked_oos_dataset


def test_cli_capture_oos_csv_source_outputs_registry_snippet(tmp_path) -> None:
    source_dir = tmp_path / "source"
    capture_locked_oos_dataset(
        bars=_bars("2026-06-19", 5),
        symbol="000001",
        date="20260619",
        source="csv",
        output_dir=source_dir,
        min_bars=5,
    )
    source_csv = source_dir / "000001_20260619_csv_intraday.csv"
    output_dir = tmp_path / "out"

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "app.cli",
            "capture-oos",
            "--source",
            "csv",
            "--symbol",
            "300750",
            "--date",
            "20260619",
            "--csv",
            str(source_csv),
            "--output-dir",
            str(output_dir),
            "--min-bars",
            "5",
        ],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        check=True,
    )

    payload = json.loads(completed.stdout)

    assert payload["path"].endswith("300750_20260619_csv_intraday.csv")
    assert payload["registry_record"]["split"] == "out_of_sample"
    assert payload["registry_record"]["locked"] is True
    assert payload["content_sha256"] == payload["registry_record"]["content_sha256"]
    assert "Manual registry review is still required" in payload["capability_note"]


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