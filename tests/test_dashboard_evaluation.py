from app.dashboard import _build_evaluation_table, _evaluation_trade_qty, _fee_model_for_execution
from research.evaluation_report import DEFAULT_LOCKED_OOS_SCENARIOS, DEFAULT_SCENARIOS, build_evaluation_report
from research.trigger_engine import zero_fee_model


def test_dashboard_evaluation_table_flattens_required_comparisons() -> None:
    report = build_evaluation_report(fee_model=zero_fee_model())

    table = _build_evaluation_table(report)

    assert list(table["scenario"]) == list(DEFAULT_SCENARIOS)
    assert "dataset_split" in table.columns
    assert "dataset_id" in table.columns
    assert "dataset_locked" in table.columns
    assert "dataset_kind" in table.columns
    assert "no_trade_excess_pnl" in table.columns
    assert "simple_closed_t_net_pnl" in table.columns
    assert "simple_vs_no_trade" in table.columns
    assert "trigger_latest_action" in table.columns
    assert set(table["dataset_split"]) == {"in_sample"}
    assert set(table["caveat"]) == {"split-labeled; signal-only; no fills or realized PnL inferred"}


def test_dashboard_evaluation_table_can_include_locked_oos_rows() -> None:
    report = build_evaluation_report(
        scenario_names=DEFAULT_LOCKED_OOS_SCENARIOS,
        target_qty=151400,
        settled_sellable_qty=151400,
        purchasable_qty=15100,
        trade_qty=15100,
        fee_model=zero_fee_model(),
    )

    table = _build_evaluation_table(report)

    assert set(table["dataset_split"]) == {"out_of_sample"}
    assert set(table["dataset_locked"]) == {True}
    assert set(table["dataset_kind"]) == {"csv"}
    assert len(table) == len(DEFAULT_LOCKED_OOS_SCENARIOS)
    assert table["bars"].min() >= 200


def test_dashboard_evaluation_trade_qty_respects_market_lot_and_cap() -> None:
    assert _evaluation_trade_qty("A-share / Eastmoney", 151400, 0.10, None) == 15100
    assert _evaluation_trade_qty("A-share / Eastmoney", 151400, 0.10, 12345) == 12300
    assert _evaluation_trade_qty("Korea / Yahoo Finance", 1000, 0.10, None) == 100
    assert _evaluation_trade_qty("Korea / Yahoo Finance", 1000, 0.10, 37) == 37


def test_dashboard_evaluation_renderer_accepts_risk_preset_argument() -> None:
    import inspect
    from app.dashboard import _render_evaluation_report

    assert "risk_limit_preset_id" in inspect.signature(_render_evaluation_report).parameters

def test_dashboard_fee_model_defaults_to_costed_profile() -> None:
    model = _fee_model_for_execution("A-share / Eastmoney", ignore_fees=False, fee_profile_id=None, custom_fee_config=None)

    assert model.config.buy_commission_rate > 0
    assert model.config.sell_commission_rate > 0
    assert model.config.buy_slippage_rate > 0


def test_dashboard_zero_fee_requires_explicit_profile() -> None:
    model = _fee_model_for_execution("A-share / Eastmoney", ignore_fees=True, fee_profile_id=None, custom_fee_config=None)

    assert model.config.buy_commission_rate == 0.0
    assert model.config.sell_slippage_rate == 0.0

