from app.dashboard import (
    _build_threshold_experiment_comparison_table,
    _build_threshold_experiment_metric_delta_table,
)
from research.threshold_experiments import build_threshold_experiment_report


def test_dashboard_threshold_experiment_comparison_table_shows_aggregate_deltas() -> None:
    report = build_threshold_experiment_report(experiment_ids=["more_selective"])

    table = _build_threshold_experiment_comparison_table(report)

    assert list(table["experiment_id"]) == ["more_selective"]
    assert table.iloc[0]["locked_oos_count"] >= 5
    assert table.iloc[0]["threshold_change_count"] >= 1
    assert table.iloc[0]["metric_change_count"] >= 1
    assert table.iloc[0]["delta_trigger_count"] < 0
    assert "signal deltas only" in table.iloc[0]["caveat"]


def test_dashboard_threshold_experiment_metric_delta_table_splits_scenario_metrics() -> None:
    report = build_threshold_experiment_report(experiment_ids=["more_sensitive"])

    table = _build_threshold_experiment_metric_delta_table(report)

    assert not table.empty
    assert {"experiment_id", "scenario", "metric", "baseline", "current", "delta", "status"}.issubset(table.columns)
    assert "more_sensitive" in set(table["experiment_id"])
    assert "trigger_count" in set(table["metric"]) or "watch_count" in set(table["metric"])