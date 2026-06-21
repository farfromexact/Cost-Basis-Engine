import app.dashboard as dashboard
from core.fee_model import FeeModel
from research.model_audit import (
    DEFAULT_MODEL_AUDIT_BASELINE_PATH,
    build_model_audit_baseline,
    build_model_change_audit_report,
)
from research.trigger_engine import RulesConfig


def test_dashboard_model_audit_table_shows_ok_row_when_unchanged(monkeypatch) -> None:
    baseline = build_model_audit_baseline(fee_model=FeeModel())
    monkeypatch.setattr("research.model_audit.load_model_audit_baseline", lambda path=DEFAULT_MODEL_AUDIT_BASELINE_PATH: baseline)
    report = build_model_change_audit_report(fee_model=FeeModel())

    table = dashboard._build_model_audit_change_table(report)

    assert list(table.columns) == ["category", "name", "baseline", "current", "delta", "status"]
    assert table.iloc[0]["status"] == "OK"
    assert table.iloc[0]["name"] == "baseline_match"
    assert "no baseline update is needed" in report.review_guidance


def test_dashboard_model_audit_table_shows_locked_baseline_review() -> None:
    report = build_model_change_audit_report(fee_model=FeeModel())

    table = dashboard._build_model_audit_change_table(report)

    assert report.status == "REVIEW"
    assert not table.empty
    assert "human review gate" in report.review_guidance


def test_dashboard_model_audit_table_flattens_threshold_changes() -> None:
    report = build_model_change_audit_report(rules=RulesConfig(sb_trigger_deviation=0.012))

    table = dashboard._build_model_audit_change_table(report)

    assert "threshold" in set(table["category"])
    assert "sb_trigger_deviation" in set(table["name"])
    assert "CHANGED" in set(table["status"])


def test_dashboard_custom_fee_config_preserves_market(monkeypatch) -> None:
    class FakeColumn:
        def number_input(self, _label, **kwargs):
            return kwargs["value"]

    class FakeStreamlit:
        session_state = {}
        captions = []

        def columns(self, _count):
            return [FakeColumn(), FakeColumn()]

        def caption(self, text):
            self.captions.append(text)

    fake_st = FakeStreamlit()
    monkeypatch.setattr(dashboard, "st", fake_st)

    config = dashboard._custom_fee_config_from_sidebar(
        dashboard.FeeConfig(
            market="US_EQUITY",
            us_broker_commission_per_share=0.005,
            us_broker_min_commission=1.0,
            us_platform_fee_per_order=0.5,
        )
    )

    assert config.market == "US_EQUITY"
    assert config.us_broker_commission_per_share == 0.005
    assert config.us_broker_min_commission == 1.0
    assert config.us_platform_fee_per_order == 0.5
    assert any("break-even" in caption for caption in fake_st.captions)
