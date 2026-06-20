from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from research.model_audit import DEFAULT_MODEL_AUDIT_BASELINE_PATH, MODEL_AUDIT_BASELINE_REVIEW_TOKEN


def test_cli_audit_baseline_update_previews_without_writing(tmp_path) -> None:
    baseline_path = _drifted_baseline(tmp_path)
    before = baseline_path.read_text(encoding="utf-8")

    completed = subprocess.run(
        [sys.executable, "-m", "app.cli", "audit-baseline-update", "--baseline", str(baseline_path)],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        check=True,
    )

    payload = json.loads(completed.stdout)

    assert payload["status"] == "REVIEW_REQUIRED"
    assert payload["required_review_token"] == MODEL_AUDIT_BASELINE_REVIEW_TOKEN
    assert baseline_path.read_text(encoding="utf-8") == before


def test_cli_audit_baseline_update_writes_with_review_token(tmp_path) -> None:
    baseline_path = _drifted_baseline(tmp_path)
    before = baseline_path.read_text(encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "app.cli",
            "audit-baseline-update",
            "--baseline",
            str(baseline_path),
            "--review-token",
            MODEL_AUDIT_BASELINE_REVIEW_TOKEN,
            "--review-note",
            "cli test reviewed audit deltas",
        ],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        check=True,
    )

    payload = json.loads(completed.stdout)

    assert payload["status"] == "UPDATED"
    assert payload["threshold_change_count"] >= 1
    assert baseline_path.read_text(encoding="utf-8") != before
    assert "not evidence of profitability" in payload["report_note"]


def _drifted_baseline(tmp_path) -> Path:
    payload = json.loads(Path(DEFAULT_MODEL_AUDIT_BASELINE_PATH).read_text(encoding="utf-8"))
    payload["trigger_thresholds"]["sb_trigger_deviation"] = 0.123
    path = tmp_path / "locked_oos_audit_baseline_v1.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return path