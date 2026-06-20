from core.fee_model import FeeConfig, FeeModel
from research.dataset_registry import SPLIT_IN_SAMPLE, SPLIT_OUT_OF_SAMPLE
from research.evaluation_report import DEFAULT_LOCKED_OOS_SCENARIOS, DEFAULT_SCENARIOS, build_evaluation_report, build_locked_oos_evaluation_report


def test_evaluation_report_compares_required_baselines_across_scenarios() -> None:
    report = build_evaluation_report(fee_model=_cheap_fee_model())
    payload = report.as_dict()

    assert [row["scenario"] for row in payload["scenarios"]] == list(DEFAULT_SCENARIOS)
    assert payload["split_summary"]["in_sample"] == len(DEFAULT_SCENARIOS)
    assert payload["split_summary"]["out_of_sample"] == 0
    assert "out-of-sample" in payload["report_note"]
    assert "no profitability claim" in payload["report_note"]
    for row in payload["scenarios"]:
        assert row["dataset_split"] == SPLIT_IN_SAMPLE
        assert row["dataset_id"]
        assert row["dataset_locked"] is False
        assert not row["is_out_of_sample"]
        assert row["no_trade_baseline"]["label"] == "no_trade"
        assert row["no_trade_baseline"]["excess_pnl_vs_hold"] == 0.0
        assert "trade_count" in row["simple_interpretable_baseline"]
        assert "strategy_excess_pnl" in row["simple_vs_no_trade"]
        assert "latest_action" in row["trigger_engine_signal"]
        assert "no same-minute fill" in row["trigger_engine_signal"]["note"]
        assert "not inferred from trigger signals" in row["capability_note"]
        assert "split=in_sample" in row["capability_note"]


def test_locked_oos_evaluation_report_uses_hash_locked_real_datasets() -> None:
    report = build_locked_oos_evaluation_report(
        target_qty=151400,
        settled_sellable_qty=151400,
        purchasable_qty=15100,
        trade_qty=15100,
        fee_model=_cheap_fee_model(),
    ).as_dict()

    assert set(row["scenario"] for row in report["scenarios"]) == set(DEFAULT_LOCKED_OOS_SCENARIOS)
    assert report["split_summary"]["in_sample"] == 0
    assert report["split_summary"]["out_of_sample"] == len(DEFAULT_LOCKED_OOS_SCENARIOS)
    assert report["split_summary"]["locked_out_of_sample"] == len(DEFAULT_LOCKED_OOS_SCENARIOS)
    assert len(report["scenarios"]) >= 4
    for row in report["scenarios"]:
        assert row["dataset_split"] == SPLIT_OUT_OF_SAMPLE
        assert row["is_out_of_sample"] is True
        assert row["dataset_locked"] is True
        assert row["dataset_kind"] == "csv"
        assert row["dataset_content_sha256"]
        assert row["bar_count"] >= 200
        assert "locked=True" in row["capability_note"]
    assert "profitability" in report["report_note"]


def test_evaluation_report_preserves_known_synthetic_baseline_behavior() -> None:
    report = build_evaluation_report(fee_model=_cheap_fee_model()).as_dict()
    by_name = {row["scenario"]: row for row in report["scenarios"]}

    assert by_name["mean_revert"]["simple_interpretable_baseline"]["closed_t_net_pnl"] > 0
    assert by_name["one_way_up"]["simple_interpretable_baseline"]["unclosed_pair_rate"] == 1.0
    assert by_name["low_liquidity"]["simple_interpretable_baseline"]["trade_count"] == 0
    assert by_name["mean_revert"]["trigger_engine_signal"]["trigger_count"] >= 0
    assert "profitability claim" in report["report_note"]


def _cheap_fee_model() -> FeeModel:
    return FeeModel(
        FeeConfig(
            min_commission=0.0,
            buy_commission_rate=0.0,
            sell_commission_rate=0.0,
            stamp_tax_rate=0.0,
            transfer_fee_rate=0.0,
            buy_slippage_rate=0.0,
            sell_slippage_rate=0.0,
        )
    )
