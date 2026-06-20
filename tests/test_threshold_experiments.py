from pathlib import Path

from core.fee_model import FeeModel
from research.model_audit import DEFAULT_MODEL_AUDIT_BASELINE_PATH
from research.threshold_experiments import (
    available_threshold_experiment_ids,
    build_threshold_experiment_report,
    rules_with_threshold_overrides,
)
from research.trigger_engine import RulesConfig


def test_threshold_experiment_report_reads_but_does_not_modify_baseline() -> None:
    baseline_path = DEFAULT_MODEL_AUDIT_BASELINE_PATH
    before = Path(baseline_path).read_text(encoding="utf-8")

    report = build_threshold_experiment_report(experiment_ids=["more_selective"], fee_model=FeeModel())

    after = Path(baseline_path).read_text(encoding="utf-8")
    result = report.experiments[0]

    assert before == after
    assert report.baseline_id == "locked_oos_audit_baseline_v1"
    assert report.locked_oos_count >= 5
    assert result.experiment_id == "more_selective"
    assert result.audit_status == "REVIEW"
    assert result.threshold_changes
    assert "never modified" in report.report_note
    assert "profitability" in report.report_note


def test_threshold_experiment_unknown_id_fails() -> None:
    try:
        build_threshold_experiment_report(experiment_ids=["not_real"])
    except ValueError as exc:
        assert "unknown threshold experiment" in str(exc)
    else:
        raise AssertionError("unknown experiment should fail")


def test_rules_with_threshold_overrides_validates_fields() -> None:
    rules = rules_with_threshold_overrides(RulesConfig(), {"sb_trigger_deviation": 0.01})

    assert rules.sb_trigger_deviation == 0.01
    assert "more_sensitive" in available_threshold_experiment_ids()

    try:
        rules_with_threshold_overrides(RulesConfig(), {"bad_field": 1})
    except ValueError as exc:
        assert "unknown RulesConfig override" in str(exc)
    else:
        raise AssertionError("unknown override should fail")