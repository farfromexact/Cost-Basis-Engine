from __future__ import annotations

import json
from pathlib import Path

from app.dashboard import _build_model_audit_baseline_update_table
from research.model_audit import DEFAULT_MODEL_AUDIT_BASELINE_PATH, build_model_audit_baseline_update_preview


def test_dashboard_baseline_update_table_shows_review_gate(tmp_path) -> None:
    payload = json.loads(Path(DEFAULT_MODEL_AUDIT_BASELINE_PATH).read_text(encoding="utf-8"))
    payload["trigger_thresholds"]["sb_trigger_deviation"] = 0.123
    baseline_path = tmp_path / "baseline.json"
    baseline_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    preview = build_model_audit_baseline_update_preview(baseline_path=baseline_path)

    table = _build_model_audit_baseline_update_table(preview)

    assert table.iloc[0]["status"] == "REVIEW_REQUIRED"
    assert table.iloc[0]["threshold_change_count"] >= 1
    assert table.iloc[0]["can_update_without_token"] == False
    assert "APPROVE_LOCKED_OOS_BASELINE_UPDATE" in table.iloc[0]["required_review_token"]