from __future__ import annotations

import json
from pathlib import Path

from core.fee_model import FeeModel
from research.model_audit import (
    DEFAULT_MODEL_AUDIT_BASELINE_PATH,
    MODEL_AUDIT_BASELINE_REVIEW_TOKEN,
    build_model_audit_baseline_update_preview,
    load_model_audit_baseline,
    update_model_audit_baseline_after_review,
)
from research.trigger_engine import RulesConfig


def test_baseline_update_preview_requires_review_for_deltas(tmp_path) -> None:
    baseline_path = _drifted_baseline(tmp_path)
    before = baseline_path.read_text(encoding="utf-8")

    preview = build_model_audit_baseline_update_preview(baseline_path=baseline_path, fee_model=FeeModel())

    assert preview.status == "REVIEW_REQUIRED"
    assert preview.threshold_change_count >= 1
    assert preview.required_review_token == MODEL_AUDIT_BASELINE_REVIEW_TOKEN
    assert preview.can_update is False
    assert baseline_path.read_text(encoding="utf-8") == before


def test_baseline_update_rejects_missing_review_token(tmp_path) -> None:
    baseline_path = _drifted_baseline(tmp_path)
    before = baseline_path.read_text(encoding="utf-8")

    try:
        update_model_audit_baseline_after_review(baseline_path=baseline_path, review_token="", fee_model=FeeModel())
    except ValueError as exc:
        assert "explicit review token" in str(exc)
    else:
        raise AssertionError("baseline update should require a review token")

    assert baseline_path.read_text(encoding="utf-8") == before


def test_baseline_update_writes_only_after_explicit_review(tmp_path) -> None:
    baseline_path = _drifted_baseline(tmp_path)
    before = baseline_path.read_text(encoding="utf-8")

    result = update_model_audit_baseline_after_review(
        baseline_path=baseline_path,
        review_token=MODEL_AUDIT_BASELINE_REVIEW_TOKEN,
        reviewer_note="unit test reviewed audit deltas",
        fee_model=FeeModel(),
    )

    after = baseline_path.read_text(encoding="utf-8")
    updated = load_model_audit_baseline(baseline_path)

    assert result.status == "UPDATED"
    assert before != after
    assert updated.trigger_thresholds["sb_trigger_deviation"] == RulesConfig().sb_trigger_deviation
    assert "unit test reviewed audit deltas" in updated.note
    assert "not profitability evidence" in updated.note


def _drifted_baseline(tmp_path) -> Path:
    payload = json.loads(Path(DEFAULT_MODEL_AUDIT_BASELINE_PATH).read_text(encoding="utf-8"))
    payload["trigger_thresholds"]["sb_trigger_deviation"] = 0.123
    path = tmp_path / "locked_oos_audit_baseline_v1.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return path