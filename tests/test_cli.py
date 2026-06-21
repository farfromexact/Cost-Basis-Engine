from types import SimpleNamespace

from app.cli import _args_with_position_state, _data_source_from_snapshot, _fee_config_from_args, _fee_profile_id_from_args, _market_source_from_args, _rules_config_from_args
from app.position_state import PositionSnapshot, load_position_snapshot, save_position_snapshot
from core.fee_profiles import DEFAULT_A_SHARE_FEE_PROFILE_ID, DEFAULT_US_FEE_PROFILE_ID, ZERO_FEE_PROFILE_ID


def test_cli_fee_config_is_explicitly_configurable() -> None:
    args = SimpleNamespace(
        fee_profile="custom_manual",
        ignore_fees=False,
        buy_commission_rate=0.1,
        sell_commission_rate=0.2,
        min_commission=3.0,
        stamp_tax_rate=0.4,
        transfer_fee_rate=0.5,
        other_fee_rate=0.6,
        buy_slippage_rate=0.7,
        sell_slippage_rate=0.8,
        a_share_handling_fee_bps=1.1,
        a_share_management_fee_bps=1.2,
        a_share_transfer_fee_bps=1.3,
        a_share_stamp_duty_sell_bps=1.4,
        a_share_broker_commission_bps=1.5,
        a_share_min_commission_cny=1.6,
        us_sec_fee_per_million=2.1,
        us_finra_taf_per_share=2.2,
        us_finra_taf_cap_per_trade=2.3,
        us_broker_commission_per_share=2.4,
        us_broker_min_commission=2.5,
        us_platform_fee_per_order=2.6,
    )

    config = _fee_config_from_args(args)

    assert config.buy_commission_rate == 0.1
    assert config.sell_commission_rate == 0.2
    assert config.min_commission == 3.0
    assert config.stamp_tax_rate == 0.4
    assert config.transfer_fee_rate == 0.5
    assert config.other_fee_rate == 0.6
    assert config.buy_slippage_rate == 0.7
    assert config.sell_slippage_rate == 0.8
    assert config.market == "A_SHARE"
    assert config.a_share_handling_fee_bps == 1.1
    assert config.a_share_broker_commission_bps == 1.5
    assert config.a_share_min_commission_cny == 1.6


def test_cli_us_custom_fee_components_are_configurable() -> None:
    args = SimpleNamespace(
        fee_profile="custom_manual",
        ignore_fees=False,
        data_source="us_yahoo",
        buy_commission_rate=0.0,
        sell_commission_rate=0.0,
        min_commission=0.0,
        stamp_tax_rate=0.0,
        transfer_fee_rate=0.0,
        other_fee_rate=0.0,
        buy_slippage_rate=0.0002,
        sell_slippage_rate=0.0003,
        us_sec_fee_per_million=30.0,
        us_finra_taf_per_share=0.0002,
        us_finra_taf_cap_per_trade=8.0,
        us_broker_commission_per_share=0.005,
        us_broker_min_commission=1.0,
        us_platform_fee_per_order=0.5,
    )

    config = _fee_config_from_args(args)

    assert config.market == "US_EQUITY"
    assert config.us_sec_fee_per_million == 30.0
    assert config.us_finra_taf_per_share == 0.0002
    assert config.us_finra_taf_cap_per_trade == 8.0
    assert config.us_broker_commission_per_share == 0.005
    assert config.us_broker_min_commission == 1.0
    assert config.us_platform_fee_per_order == 0.5


def test_cli_default_fee_profile_is_costed_not_zero_fee() -> None:
    args = SimpleNamespace(
        fee_profile=None,
        ignore_fees=False,
        data_source="eastmoney",
        buy_commission_rate=0.0,
        sell_commission_rate=0.0,
        min_commission=0.0,
        stamp_tax_rate=0.0,
        transfer_fee_rate=0.0,
        other_fee_rate=0.0,
        buy_slippage_rate=0.0,
        sell_slippage_rate=0.0,
    )

    config = _fee_config_from_args(args)

    assert _fee_profile_id_from_args(args) == DEFAULT_A_SHARE_FEE_PROFILE_ID
    assert config.buy_commission_rate > 0
    assert config.sell_commission_rate > 0
    assert config.buy_slippage_rate > 0


def test_cli_us_yahoo_uses_us_fee_profile_and_rules() -> None:
    args = SimpleNamespace(
        fee_profile=None,
        ignore_fees=False,
        data_source="us_yahoo",
        max_t_ratio=0.10,
        max_single_trade_qty=None,
        risk_preset="balanced",
    )

    rules = _rules_config_from_args(args)

    assert _fee_profile_id_from_args(args) == DEFAULT_US_FEE_PROFILE_ID
    assert _market_source_from_args(args) == "US / Yahoo Finance"
    assert rules.lot_size == 1
    assert rules.start_time == "09:30"
    assert rules.close_time == "16:00"
    assert rules.price_limit_pct == 1.00


def test_cli_position_snapshot_maps_us_market_to_us_yahoo_source() -> None:
    snapshot = PositionSnapshot(symbol="AAPL", market_source="US / Yahoo Finance")

    assert _data_source_from_snapshot(snapshot) == "us_yahoo"


def test_cli_zero_fee_requires_explicit_flag_or_profile() -> None:
    via_flag = _fee_config_from_args(SimpleNamespace(fee_profile=None, ignore_fees=True, data_source="eastmoney"))
    via_profile = _fee_config_from_args(SimpleNamespace(fee_profile=ZERO_FEE_PROFILE_ID, ignore_fees=False, data_source="eastmoney"))

    assert via_flag.buy_commission_rate == 0.0
    assert via_flag.sell_slippage_rate == 0.0
    assert via_profile.buy_commission_rate == 0.0
    assert via_profile.sell_slippage_rate == 0.0


def test_position_snapshot_round_trips_to_json(tmp_path) -> None:
    path = tmp_path / "position_state.json"
    snapshot = PositionSnapshot(
        market_source="Korea / Yahoo Finance",
        symbol="005930.KS",
        held_qty=1000,
        settled_sellable_qty=800,
        purchasable_qty=120,
        max_t_ratio=0.12,
        max_single_trade_qty=50,
        risk_limit_preset_id="defensive",
        fee_profile_id="korea_prototype_conservative",
        ignore_fees=False,
        open_pair_side="BS",
        open_pair_price=71000.0,
        open_pair_qty=50,
    )

    save_position_snapshot(snapshot, path)
    loaded = load_position_snapshot(path)

    assert loaded is not None
    assert loaded.symbol == "005930.KS"
    assert loaded.market_source == "Korea / Yahoo Finance"
    assert loaded.fee_profile_id == "korea_prototype_conservative"
    assert loaded.risk_limit_preset_id == "defensive"
    assert loaded.open_pair_side == "BS"
    assert loaded.open_pair_price == 71000.0
    assert loaded.updated_at


def test_cli_position_state_fills_missing_prompt_context(tmp_path) -> None:
    path = tmp_path / "position_state.json"
    save_position_snapshot(
        PositionSnapshot(
            market_source="A-share / Eastmoney",
            symbol="603236",
            held_qty=151400,
            settled_sellable_qty=120000,
            purchasable_qty=20000,
            max_t_ratio=0.10,
            max_single_trade_qty=15100,
            risk_limit_preset_id="active",
            fee_profile_id="a_share_low_cost",
            ignore_fees=False,
            open_pair_side="SB",
            open_pair_price=53.98,
            open_pair_qty=15100,
        ),
        path,
    )
    args = SimpleNamespace(
        command="monitor",
        position_state=str(path),
        no_position_state=False,
        symbol=None,
        data_source=None,
        target_qty=None,
        settled_sellable_qty=None,
        trade_qty=None,
        risk_preset=None,
        fee_profile=None,
        ignore_fees=False,
        open_pair_side=None,
        open_pair_price=None,
        open_pair_qty=None,
    )

    merged = _args_with_position_state(args)

    assert merged.symbol == "603236"
    assert merged.data_source == "eastmoney"
    assert merged.target_qty == 151400
    assert merged.settled_sellable_qty == 120000
    assert merged.trade_qty == 15100
    assert merged.fee_profile == "a_share_low_cost"
    assert merged.risk_preset == "active"
    assert merged.open_pair_side == "SB"
    assert merged.open_pair_price == 53.98
    assert merged.open_pair_qty == 15100


def test_cli_explicit_args_override_position_state(tmp_path) -> None:
    path = tmp_path / "position_state.json"
    save_position_snapshot(PositionSnapshot(symbol="603236", held_qty=151400, fee_profile_id="a_share_low_cost"), path)
    args = SimpleNamespace(
        command="trigger",
        position_state=str(path),
        no_position_state=False,
        symbol="000001",
        data_source="eastmoney",
        held_qty=1000,
        settled_sellable_qty=None,
        purchasable_qty=None,
        max_t_ratio=None,
        max_single_trade_qty=None,
        risk_preset=None,
        fee_profile=DEFAULT_A_SHARE_FEE_PROFILE_ID,
        ignore_fees=False,
        open_pair_side=None,
        open_pair_price=None,
        open_pair_qty=None,
    )

    merged = _args_with_position_state(args)

    assert merged.symbol == "000001"
    assert merged.held_qty == 1000
    assert merged.settled_sellable_qty == 151400
    assert merged.purchasable_qty == 15100
    assert merged.fee_profile == DEFAULT_A_SHARE_FEE_PROFILE_ID


def test_cli_trigger_outputs_session_closeout(monkeypatch, capsys, tmp_path) -> None:
    import json
    import sys
    import app.cli as cli

    monkeypatch.setattr(cli, "default_manual_fills_path", lambda: tmp_path / "manual_fills.json")
    monkeypatch.setattr(cli, "default_broker_fill_export_path", lambda: tmp_path / "broker_fills.csv")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "cost-basis-engine",
            "trigger",
            "--scenario",
            "mean_revert",
            "--held-qty",
            "10000",
            "--settled-sellable-qty",
            "10000",
            "--purchasable-qty",
            "10000",
            "--max-t-ratio",
            "0.10",
            "--risk-preset",
            "defensive",
            "--ignore-fees",
            "--no-position-state",
        ],
    )

    cli.main()
    payload = json.loads(capsys.readouterr().out)

    assert payload["session_closeout"]["status"] == "NO_ACTION"
    assert payload["session_closeout"]["countable"] is False
    assert payload["session_closeout"]["countable_cost_basis_reduction"] == 0.0


def test_cli_trigger_outputs_end_of_day_review(monkeypatch, capsys, tmp_path) -> None:
    import json
    import sys
    import app.cli as cli

    monkeypatch.setattr(cli, "default_manual_fills_path", lambda: tmp_path / "manual_fills.json")
    monkeypatch.setattr(cli, "default_broker_fill_export_path", lambda: tmp_path / "broker_fills.csv")
    monkeypatch.setattr(cli, "default_execution_journal_dir", lambda: tmp_path / "execution_journals") if hasattr(cli, "default_execution_journal_dir") else None
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "cost-basis-engine",
            "trigger",
            "--scenario",
            "mean_revert",
            "--held-qty",
            "10000",
            "--settled-sellable-qty",
            "10000",
            "--purchasable-qty",
            "10000",
            "--max-t-ratio",
            "0.10",
            "--risk-preset",
            "defensive",
            "--ignore-fees",
            "--no-position-state",
        ],
    )

    cli.main()
    payload = json.loads(capsys.readouterr().out)

    assert payload["end_of_day_review"]["closeout_status"] == payload["session_closeout"]["status"]
    assert payload["end_of_day_review"]["recent_journal_count"] >= 1
    assert payload["end_of_day_review"]["rows"][0]["item"] == "current_closeout"


def test_cli_trigger_outputs_closeout_signoff_preview(monkeypatch, capsys, tmp_path) -> None:
    import json
    import sys
    import app.cli as cli

    monkeypatch.setattr(cli, "default_manual_fills_path", lambda: tmp_path / "manual_fills.json")
    monkeypatch.setattr(cli, "default_broker_fill_export_path", lambda: tmp_path / "broker_fills.csv")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "cost-basis-engine",
            "trigger",
            "--scenario",
            "mean_revert",
            "--held-qty",
            "10000",
            "--settled-sellable-qty",
            "10000",
            "--purchasable-qty",
            "10000",
            "--max-t-ratio",
            "0.10",
            "--risk-preset",
            "defensive",
            "--ignore-fees",
            "--no-position-state",
            "--closeout-signoff-dir",
            str(tmp_path / "signoffs"),
        ],
    )

    cli.main()
    payload = json.loads(capsys.readouterr().out)

    assert payload["closeout_signoff_preview"]["status"] == "REVIEW_REQUIRED"
    assert payload["closeout_signoff_preview"]["closeout_status"] == "NO_ACTION"
    assert "closeout_signoff_path" not in payload


def test_cli_trigger_writes_closeout_signoff_with_review_token(monkeypatch, capsys, tmp_path) -> None:
    import json
    import sys
    from pathlib import Path

    import app.cli as cli
    from app.closeout_signoff import CLOSEOUT_SIGNOFF_REVIEW_TOKEN

    monkeypatch.setattr(cli, "default_manual_fills_path", lambda: tmp_path / "manual_fills.json")
    monkeypatch.setattr(cli, "default_broker_fill_export_path", lambda: tmp_path / "broker_fills.csv")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "cost-basis-engine",
            "trigger",
            "--scenario",
            "mean_revert",
            "--held-qty",
            "10000",
            "--settled-sellable-qty",
            "10000",
            "--purchasable-qty",
            "10000",
            "--max-t-ratio",
            "0.10",
            "--risk-preset",
            "defensive",
            "--ignore-fees",
            "--no-position-state",
            "--closeout-signoff-review-token",
            CLOSEOUT_SIGNOFF_REVIEW_TOKEN,
            "--closeout-signoff-note",
            "Reviewed no-action closeout.",
            "--closeout-signoff-dir",
            str(tmp_path / "signoffs"),
        ],
    )

    cli.main()
    payload = json.loads(capsys.readouterr().out)

    assert payload["closeout_signoff_preview"]["status"] == "READY"
    written_path = Path(payload["closeout_signoff_path"])
    written = json.loads(written_path.read_text(encoding="utf-8"))
    assert written["review_token_confirmed"] is True
    assert written["closeout"]["status"] == "NO_ACTION"
