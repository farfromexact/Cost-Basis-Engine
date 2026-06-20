from research.risk_limits import risk_limit_preset, risk_limit_preset_ids, rules_with_risk_limit_preset
from research.trigger_engine import RulesConfig


def test_risk_limit_presets_expose_required_intraday_limits() -> None:
    assert set(risk_limit_preset_ids()) == {"defensive", "balanced", "active"}
    defensive = risk_limit_preset("defensive")

    assert defensive.max_daily_turnover_ratio == 0.10
    assert defensive.max_open_pair_minutes == 25
    assert defensive.max_same_day_capital_at_risk_ratio == 0.05


def test_rules_with_risk_limit_preset_maps_to_trigger_rules() -> None:
    rules = rules_with_risk_limit_preset(RulesConfig(max_t_ratio=0.20), "defensive")

    assert rules.risk_preset_id == "defensive"
    assert rules.max_daily_turnover_ratio == 0.10
    assert rules.max_wait_minutes == 25
    assert rules.max_same_day_capital_at_risk_ratio == 0.05
    assert rules.max_t_ratio == 0.20