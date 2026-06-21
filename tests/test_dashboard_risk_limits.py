from app.dashboard import _build_risk_limit_preset_table, _evaluation_trade_qty, _rules_for_market


def test_dashboard_risk_limit_table_shows_required_preset_fields() -> None:
    table = _build_risk_limit_preset_table("defensive")

    assert table.iloc[0]["preset_id"] == "defensive"
    assert table.iloc[0]["max_daily_turnover_ratio"] == 0.10
    assert table.iloc[0]["max_open_pair_minutes"] == 25
    assert table.iloc[0]["max_same_day_capital_at_risk_ratio"] == 0.05


def test_dashboard_evaluation_trade_qty_respects_risk_preset() -> None:
    assert _evaluation_trade_qty("A-share / Eastmoney", 151400, 0.10, None, "balanced") == 15100
    assert _evaluation_trade_qty("A-share / Eastmoney", 151400, 0.10, None, "defensive") == 7500
    assert _evaluation_trade_qty("US / Yahoo Finance", 100, 0.10, None, "balanced") == 10


def test_dashboard_rules_for_market_apply_risk_preset() -> None:
    rules = _rules_for_market("A-share / Eastmoney", 0.10, None, "defensive")

    assert rules.risk_preset_id == "defensive"
    assert rules.max_daily_turnover_ratio == 0.10
    assert rules.max_wait_minutes == 25


def test_dashboard_rules_for_us_yahoo_use_us_market_defaults() -> None:
    rules = _rules_for_market("US / Yahoo Finance", 0.10, None, "balanced")

    assert rules.lot_size == 1
    assert rules.minimum_order_qty == 1
    assert rules.start_time == "09:30"
    assert rules.no_new_trade_after == "15:35"
    assert rules.close_time == "16:00"
    assert rules.price_limit_pct == 1.00
