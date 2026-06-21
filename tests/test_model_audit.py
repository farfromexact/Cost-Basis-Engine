from core.fee_model import FeeModel
from research.model_audit import (
    DEFAULT_MODEL_AUDIT_BASELINE_PATH,
    build_model_audit_baseline,
    build_model_change_audit_report,
    load_model_audit_baseline,
    trigger_threshold_snapshot,
)
from research.trigger_engine import RulesConfig


def test_model_audit_baseline_loads_thresholds_and_locked_metrics() -> None:
    baseline = load_model_audit_baseline(DEFAULT_MODEL_AUDIT_BASELINE_PATH)

    assert baseline.baseline_id == "locked_oos_audit_baseline_v1"
    assert "sb_trigger_deviation" in baseline.trigger_thresholds
    assert len(baseline.evaluation_metrics) >= 5
    assert all("trigger_count" in metrics for metrics in baseline.evaluation_metrics.values())


def test_model_audit_report_is_ok_when_current_matches_baseline(monkeypatch) -> None:
    baseline = build_model_audit_baseline(fee_model=FeeModel())
    monkeypatch.setitem(
        build_model_change_audit_report.__globals__,
        "load_model_audit_baseline",
        lambda path=DEFAULT_MODEL_AUDIT_BASELINE_PATH: baseline,
    )

    report = build_model_change_audit_report(fee_model=FeeModel())

    assert report.status == "OK"
    assert report.threshold_changes == ()
    assert report.metric_changes == ()
    assert report.locked_oos_count >= 5
    assert "no baseline update is needed" in report.review_guidance
    assert "no profitability" in report.report_note


def test_model_audit_report_requires_review_against_locked_previous_baseline() -> None:
    report = build_model_change_audit_report(fee_model=FeeModel())

    assert report.status == "REVIEW"
    assert report.threshold_changes or report.metric_changes
    assert report.locked_oos_count >= 5
    assert "human review gate" in report.review_guidance
    assert "no profitability" in report.report_note


def test_model_audit_report_flags_threshold_changes() -> None:
    changed_rules = RulesConfig(sb_trigger_deviation=RulesConfig().sb_trigger_deviation * 2)

    report = build_model_change_audit_report(rules=changed_rules, fee_model=FeeModel())

    assert report.status == "REVIEW"
    assert any(change.name == "sb_trigger_deviation" for change in report.threshold_changes)
    assert trigger_threshold_snapshot(changed_rules)["sb_trigger_deviation"] != load_model_audit_baseline().trigger_thresholds["sb_trigger_deviation"]
