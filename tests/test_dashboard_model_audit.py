from app.dashboard import _build_model_audit_change_table
from research.model_audit import build_model_change_audit_report
from research.trigger_engine import RulesConfig


def test_dashboard_model_audit_table_shows_ok_row_when_unchanged() -> None:
    report = build_model_change_audit_report()

    table = _build_model_audit_change_table(report)

    assert list(table.columns) == ["category", "name", "baseline", "current", "delta", "status"]
    assert table.iloc[0]["status"] == "OK"
    assert table.iloc[0]["name"] == "baseline_match"


def test_dashboard_model_audit_table_flattens_threshold_changes() -> None:
    report = build_model_change_audit_report(rules=RulesConfig(sb_trigger_deviation=0.012))

    table = _build_model_audit_change_table(report)

    assert "threshold" in set(table["category"])
    assert "sb_trigger_deviation" in set(table["name"])
    assert "CHANGED" in set(table["status"])
