from __future__ import annotations

import argparse
import json
import os
import time
from copy import copy
from dataclasses import asdict

from app.broker_import import BROKER_FILL_PROMOTION_REVIEW_TOKEN, build_broker_fill_promotion_preview, default_broker_fill_export_path, load_broker_fill_export, promote_broker_fill_after_review, reconcile_manual_fills_with_broker_export, supported_broker_fill_columns
from app.closeout_signoff import CLOSEOUT_SIGNOFF_REVIEW_TOKEN, build_closeout_signoff_preview, write_closeout_signoff_after_review
from app.end_of_day_review import build_end_of_day_review_report
from app.execution_journal import build_execution_journal_report, load_execution_journal_records, save_execution_journal_report
from app.execution_sensitivity import build_execution_sensitivity_report
from app.monitoring import alert_signature, should_send_alert
from app.manual_fills import (
    default_manual_fills_path,
    load_manual_fills,
    make_manual_fill,
    manual_pair_id,
    record_manual_fill,
)
from app.notifications import NotificationConfig, Notifier, format_prompt_notification
from app.order_ticket import build_pre_trade_order_ticket
from app.post_trade_review import build_post_trade_review_report
from app.session_closeout import build_session_closeout_report
from app.session_risk import build_live_session_risk_usage_report
from app.position_reconciliation import (
    BrokerPositionSnapshot,
    default_position_reconciliation_path,
    load_broker_position_snapshot,
    reconcile_position_state,
    save_broker_position_snapshot,
)
from app.position_state import PositionSnapshot, default_position_state_path, load_position_snapshot
from core.fee_model import FeeConfig, FeeModel
from core.fee_profiles import (
    CUSTOM_FEE_PROFILE_ID,
    ZERO_FEE_PROFILE_ID,
    fee_config_from_profile,
    normalize_fee_profile_id,
)
from core.inventory_ledger import InventoryLedger
from data.adapters import load_minute_csv
from data.eastmoney import fetch_intraday_minute_bars
from data.yahoo import fetch_yahoo_intraday_bars, normalize_yahoo_symbol
from research.evaluation import compare_to_no_trade
from research.evaluation_report import DEFAULT_LOCKED_OOS_SCENARIOS, DEFAULT_SCENARIOS, build_evaluation_report
from research.model_audit import (
    DEFAULT_MODEL_AUDIT_BASELINE_PATH,
    MODEL_AUDIT_BASELINE_REVIEW_TOKEN,
    build_model_audit_baseline_update_preview,
    build_model_change_audit_report,
    update_model_audit_baseline_after_review,
)
from research.oos_capture import capture_locked_oos_from_source
from research.prompts import (
    PromptConfig,
    PromptContext,
    derive_lot_qty,
    evaluate_latest_prompt,
    scan_prompts,
)
from research.replay import replay_sell_then_buy
from research.risk_limits import risk_limit_preset_ids, rules_with_risk_limit_preset
from research.scenarios import get_scenario
from research.strategies import SellThenBuyBaselineStrategy, SellThenBuyConfig
from research.threshold_experiments import available_threshold_experiment_ids, build_threshold_experiment_report
from research.trigger_engine import PositionState, RulesConfig, TriggerEngine, zero_fee_model


def main() -> None:
    parser = argparse.ArgumentParser(prog="cost-basis-engine")
    subparsers = parser.add_subparsers(dest="command", required=True)

    replay_parser = subparsers.add_parser("replay")
    replay_parser.add_argument("--scenario", default="mean_revert")
    replay_parser.add_argument("--csv")
    replay_parser.add_argument("--symbol")
    replay_parser.add_argument("--target-qty", type=int, required=True)
    replay_parser.add_argument("--settled-sellable-qty", type=int, required=True)
    replay_parser.add_argument("--trade-qty", type=int, default=100)
    replay_parser.add_argument("--cash", type=float, default=0.0)
    replay_parser.add_argument("--sell-deviation", type=float, default=0.003)
    replay_parser.add_argument("--buyback-deviation", type=float, default=-0.001)
    _add_fee_args(replay_parser)

    evaluate_parser = subparsers.add_parser("evaluate")
    evaluate_parser.add_argument("--scenarios", nargs="+", default=list(DEFAULT_SCENARIOS))
    evaluate_parser.add_argument("--locked-oos", action="store_true", help="Evaluate only locked out-of-sample datasets.")
    evaluate_parser.add_argument("--target-qty", type=int, default=1000)
    evaluate_parser.add_argument("--settled-sellable-qty", type=int, default=1000)
    evaluate_parser.add_argument("--purchasable-qty", type=int)
    evaluate_parser.add_argument("--trade-qty", type=int, default=100)
    _add_fee_args(evaluate_parser)
    audit_parser = subparsers.add_parser("audit")
    audit_parser.add_argument("--baseline", default=str(DEFAULT_MODEL_AUDIT_BASELINE_PATH))
    audit_parser.add_argument("--target-qty", type=int, default=151400)
    audit_parser.add_argument("--settled-sellable-qty", type=int, default=151400)
    audit_parser.add_argument("--purchasable-qty", type=int, default=15100)
    audit_parser.add_argument("--trade-qty", type=int, default=15100)
    _add_fee_args(audit_parser)

    baseline_update_parser = subparsers.add_parser("audit-baseline-update")
    baseline_update_parser.add_argument("--baseline", default=str(DEFAULT_MODEL_AUDIT_BASELINE_PATH))
    baseline_update_parser.add_argument("--review-token", help=f"Required to write: {MODEL_AUDIT_BASELINE_REVIEW_TOKEN}")
    baseline_update_parser.add_argument("--review-note", default="")
    baseline_update_parser.add_argument("--target-qty", type=int, default=151400)
    baseline_update_parser.add_argument("--settled-sellable-qty", type=int, default=151400)
    baseline_update_parser.add_argument("--purchasable-qty", type=int, default=15100)
    baseline_update_parser.add_argument("--trade-qty", type=int, default=15100)
    _add_fee_args(baseline_update_parser)

    capture_oos_parser = subparsers.add_parser("capture-oos")
    capture_oos_parser.add_argument("--source", choices=["csv", "eastmoney", "yahoo"], required=True)
    capture_oos_parser.add_argument("--symbol", required=True)
    capture_oos_parser.add_argument("--date", required=True, help="Trading date as YYYYMMDD or YYYY-MM-DD.")
    capture_oos_parser.add_argument("--csv", help="Input CSV path when --source csv is used.")
    capture_oos_parser.add_argument("--output-dir", default="datasets/oos")
    capture_oos_parser.add_argument("--min-bars", type=int, default=200)
    capture_oos_parser.add_argument("--scenario")
    capture_oos_parser.add_argument("--dataset-id")
    capture_oos_parser.add_argument("--label")
    capture_oos_parser.add_argument("--overwrite", action="store_true")
    capture_oos_parser.add_argument("--yahoo-range", default="5d")

    threshold_parser = subparsers.add_parser("threshold-experiments")
    threshold_parser.add_argument("--experiments", nargs="+", choices=list(available_threshold_experiment_ids()))
    threshold_parser.add_argument("--baseline", default=str(DEFAULT_MODEL_AUDIT_BASELINE_PATH))
    threshold_parser.add_argument("--target-qty", type=int, default=151400)
    threshold_parser.add_argument("--settled-sellable-qty", type=int, default=151400)
    threshold_parser.add_argument("--purchasable-qty", type=int, default=15100)
    threshold_parser.add_argument("--trade-qty", type=int, default=15100)
    _add_fee_args(threshold_parser)

    prompt_parser = subparsers.add_parser("prompt")
    _add_prompt_args(prompt_parser)
    _add_position_state_args(prompt_parser)

    monitor_parser = subparsers.add_parser("monitor")
    _add_prompt_args(monitor_parser)
    monitor_parser.add_argument("--interval-seconds", type=float, default=60.0)
    monitor_parser.add_argument("--once", action="store_true")
    monitor_parser.add_argument("--max-iterations", type=int)
    monitor_parser.add_argument(
        "--notify-provider",
        choices=["console", "webhook", "bark", "pushplus"],
        default=os.getenv("CBE_NOTIFY_PROVIDER", "console"),
    )
    monitor_parser.add_argument("--notify-url", default=os.getenv("CBE_NOTIFY_URL"))
    monitor_parser.add_argument("--notify-token", default=os.getenv("CBE_NOTIFY_TOKEN"))
    monitor_parser.add_argument("--notify-dry-run", action="store_true")
    _add_position_state_args(monitor_parser)

    fills_parser = subparsers.add_parser("fills")
    fills_parser.add_argument("--record", action="store_true")
    fills_parser.add_argument("--path")
    fills_parser.add_argument("--symbol")
    fills_parser.add_argument("--pair-id")
    fills_parser.add_argument("--open-pair-side", choices=["SB", "BS"])
    fills_parser.add_argument("--open-pair-price", type=float)
    fills_parser.add_argument("--qty", type=int)
    fills_parser.add_argument("--side", choices=["BUY", "SELL"])
    fills_parser.add_argument("--price", type=float)
    fills_parser.add_argument("--ts")
    fills_parser.add_argument("--fees", type=float, default=0.0)
    fills_parser.add_argument("--slippage", type=float, default=0.0)
    fills_parser.add_argument("--note", default="Manual fill recorded by user.")


    broker_import_parser = subparsers.add_parser("broker-import")
    broker_import_parser.add_argument("--path", required=True, help="Broker-confirmed fill export in CSV or JSON format.")
    broker_import_parser.add_argument("--manual-fills-path")
    broker_import_parser.add_argument("--symbol")

    broker_promote_parser = subparsers.add_parser("broker-promote")
    broker_promote_parser.add_argument("--path", required=True, help="Broker-confirmed fill export in CSV or JSON format.")
    broker_promote_parser.add_argument("--manual-fills-path")
    broker_promote_parser.add_argument("--broker-fill-id", required=True)
    broker_promote_parser.add_argument("--pair-id", required=True)
    broker_promote_parser.add_argument("--review-token", help=f"Required to write: {BROKER_FILL_PROMOTION_REVIEW_TOKEN}")
    broker_promote_parser.add_argument("--note", default="Broker-confirmed fill promoted after operator review.")
    trigger_parser = subparsers.add_parser("trigger")
    trigger_parser.add_argument("--scenario", default="mean_revert")
    trigger_parser.add_argument("--csv")
    trigger_parser.add_argument("--symbol")
    trigger_parser.add_argument("--data-source", choices=["eastmoney", "yahoo"], default=None)
    trigger_parser.add_argument("--held-qty", type=int)
    trigger_parser.add_argument("--settled-sellable-qty", type=int)
    trigger_parser.add_argument("--purchasable-qty", type=int)
    trigger_parser.add_argument("--open-pair-side", choices=["SB", "BS"])
    trigger_parser.add_argument("--open-pair-price", type=float)
    trigger_parser.add_argument("--open-pair-qty", type=int)
    trigger_parser.add_argument("--max-t-ratio", type=float)
    trigger_parser.add_argument("--max-single-trade-qty", type=int)
    trigger_parser.add_argument("--risk-preset", choices=list(risk_limit_preset_ids()), default=None)
    trigger_parser.add_argument("--closeout-signoff-review-token", help=f"Required to write EOD signoff: {CLOSEOUT_SIGNOFF_REVIEW_TOKEN}")
    trigger_parser.add_argument("--closeout-signoff-note", default="")
    trigger_parser.add_argument("--closeout-signoff-dir")
    _add_fee_args(trigger_parser)
    _add_position_state_args(trigger_parser)

    args = parser.parse_args()

    if args.command == "replay":
        bars = _load_bars_from_args(args)
        ledger = InventoryLedger(
            target_qty=args.target_qty,
            settled_sellable_qty=args.settled_sellable_qty,
            cash_available=args.cash,
        )
        strategy = SellThenBuyBaselineStrategy(
            SellThenBuyConfig(
                trade_qty=args.trade_qty,
                sell_deviation=args.sell_deviation,
                buyback_deviation=args.buyback_deviation,
            )
        )
        result = replay_sell_then_buy(
            bars=bars,
            ledger=ledger,
            strategy=strategy,
            fee_model=FeeModel(_fee_config_from_args(args)),
        )
        comparison = compare_to_no_trade(result.metrics)
        payload = {
            "data": _data_label(args),
            "fee_profile": _fee_profile_id_from_args(args),
            "metrics": result.metrics.as_dict(),
            "comparison": asdict(comparison),
            "fills": [fill.__dict__ | {"side": fill.side.value} for fill in result.fills],
            "closed_pairs": len(result.closed_pairs),
            "open_pairs": len(result.open_pairs),
            "capability_note": "research replay only; no brokerage connection; no profit claim",
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    elif args.command == "evaluate":
        report = build_evaluation_report(
            scenario_names=list(DEFAULT_LOCKED_OOS_SCENARIOS) if args.locked_oos else args.scenarios,
            target_qty=args.target_qty,
            settled_sellable_qty=args.settled_sellable_qty,
            purchasable_qty=args.purchasable_qty,
            trade_qty=args.trade_qty,
            fee_model=FeeModel(_fee_config_from_args(args)),
        )
        payload = report.as_dict()
        payload["fee_profile"] = _fee_profile_id_from_args(args)
        print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    elif args.command == "audit":
        report = build_model_change_audit_report(
            baseline_path=args.baseline,
            target_qty=args.target_qty,
            settled_sellable_qty=args.settled_sellable_qty,
            purchasable_qty=args.purchasable_qty,
            trade_qty=args.trade_qty,
            fee_model=FeeModel(_fee_config_from_args(args)),
        )
        payload = report.as_dict()
        payload["fee_profile"] = _fee_profile_id_from_args(args)
        print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    elif args.command == "audit-baseline-update":
        try:
            if args.review_token:
                result = update_model_audit_baseline_after_review(
                    baseline_path=args.baseline,
                    review_token=args.review_token,
                    reviewer_note=args.review_note,
                    target_qty=args.target_qty,
                    settled_sellable_qty=args.settled_sellable_qty,
                    purchasable_qty=args.purchasable_qty,
                    trade_qty=args.trade_qty,
                    fee_model=FeeModel(_fee_config_from_args(args)),
                )
            else:
                result = build_model_audit_baseline_update_preview(
                    baseline_path=args.baseline,
                    target_qty=args.target_qty,
                    settled_sellable_qty=args.settled_sellable_qty,
                    purchasable_qty=args.purchasable_qty,
                    trade_qty=args.trade_qty,
                    fee_model=FeeModel(_fee_config_from_args(args)),
                )
        except ValueError as exc:
            raise SystemExit(str(exc)) from exc
        payload = result.as_dict()
        payload["fee_profile"] = _fee_profile_id_from_args(args)
        print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    elif args.command == "capture-oos":
        result = capture_locked_oos_from_source(
            source=args.source,
            symbol=args.symbol,
            date=args.date,
            csv_path=args.csv,
            output_dir=args.output_dir,
            min_bars=args.min_bars,
            scenario=args.scenario,
            dataset_id=args.dataset_id,
            label=args.label,
            overwrite=args.overwrite,
            yahoo_range=args.yahoo_range,
        )
        print(json.dumps(result.as_dict(), ensure_ascii=False, indent=2, default=str))
    elif args.command == "threshold-experiments":
        report = build_threshold_experiment_report(
            experiment_ids=args.experiments,
            baseline_path=args.baseline,
            target_qty=args.target_qty,
            settled_sellable_qty=args.settled_sellable_qty,
            purchasable_qty=args.purchasable_qty,
            trade_qty=args.trade_qty,
            fee_model=FeeModel(_fee_config_from_args(args)),
        )
        payload = report.as_dict()
        payload["fee_profile"] = _fee_profile_id_from_args(args)
        print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    elif args.command == "prompt":
        args = _args_with_position_state(args)
        bars = _load_bars_from_args(args)
        context = _prompt_context_from_args(args, bars[-1].close)
        config = _prompt_config_from_args(args)
        latest = evaluate_latest_prompt(bars, context, config)
        payload = {
            "data": _data_label(args),
            "latest_prompt": latest.as_dict(),
            "context": {
                "target_qty": context.target_qty,
                "settled_sellable_qty": context.settled_sellable_qty,
                "trade_qty": context.trade_qty,
                "cash_available": context.cash_available,
                "open_pair_side": context.open_pair_side,
                "open_pair_price": context.open_pair_price,
                "open_pair_qty": context.open_pair_qty,
            },
            "config": config.__dict__,
            "capability_note": "intraday prompt only; no brokerage connection; BS cash check requires --cash",
        }
        if args.scan:
            payload["scan_prompts"] = [
                prompt.as_dict()
                for prompt in scan_prompts(bars, context, config, max_prompts=args.max_prompts)
            ]
        print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    elif args.command == "monitor":
        _run_monitor(args)
    elif args.command == "fills":
        _run_fills_command(args)
    elif args.command == "broker-import":
        _run_broker_import_command(args)
    elif args.command == "broker-promote":
        _run_broker_promote_command(args)
    elif args.command == "trigger":
        args = _args_with_position_state(args)
        if args.held_qty is None:
            raise SystemExit("trigger requires --held-qty or saved position state")
        bars = _load_bars_from_args(args)
        rules = _rules_config_from_args(args)
        fee_model = FeeModel(_fee_config_from_args(args))
        engine = TriggerEngine(rules=rules, fee_model=fee_model)
        position = PositionState(
            target_qty=args.held_qty,
            current_total_qty=args.held_qty,
            settled_sellable_qty=args.settled_sellable_qty if args.settled_sellable_qty is not None else args.held_qty,
            purchasable_qty=args.purchasable_qty if args.purchasable_qty is not None else 0,
            open_pair_side=args.open_pair_side,
            open_pair_price=args.open_pair_price,
            open_pair_qty=args.open_pair_qty,
        )
        intent = engine.evaluate(_data_label(args), bars, position)
        payload = intent.as_dict()
        payload["fee_profile"] = _fee_profile_id_from_args(args)
        try:
            broker_snapshot = load_broker_position_snapshot(default_position_reconciliation_path())
        except ValueError as exc:
            broker_snapshot = None
            payload["broker_snapshot_error"] = str(exc)
        ticket = build_pre_trade_order_ticket(
            intent=intent,
            broker_snapshot=broker_snapshot,
            fee_model=fee_model,
            rules=rules,
        )
        sensitivity_report = build_execution_sensitivity_report(intent)
        try:
            manual_fills = load_manual_fills(default_manual_fills_path())
        except ValueError as exc:
            manual_fills = []
            payload["manual_fills_error"] = str(exc)
        manual_fill_symbol = _manual_fill_symbol_from_args(args)
        post_trade_review = build_post_trade_review_report(ticket, sensitivity_report, manual_fills)
        risk_usage = build_live_session_risk_usage_report(
            symbol=manual_fill_symbol,
            fills=manual_fills,
            target_qty=args.held_qty,
            reference_price=float(intent.reference_price or 0.0),
            preset_id=rules.risk_preset_id,
            session_date=bars[-1].ts if bars else None,
            as_of=bars[-1].ts if bars else None,
        )
        broker_export_path = default_broker_fill_export_path()
        broker_fills = []
        if broker_export_path.exists():
            try:
                broker_fills = load_broker_fill_export(broker_export_path)
            except ValueError as exc:
                payload["broker_fill_export_error"] = str(exc)
        broker_reconciliation = reconcile_manual_fills_with_broker_export(manual_fills, broker_fills, symbol=manual_fill_symbol)
        execution_journal = build_execution_journal_report(
            intent=intent,
            ticket=ticket,
            manual_fills=manual_fills,
            post_trade_review=post_trade_review,
            broker_reconciliation=broker_reconciliation,
            risk_usage=risk_usage,
        )
        session_closeout = build_session_closeout_report(
            symbol=manual_fill_symbol,
            manual_fills=manual_fills,
            broker_reconciliation=broker_reconciliation,
            risk_usage=risk_usage,
            session_date=bars[-1].ts if bars else None,
        )
        payload["pre_trade_order_ticket"] = ticket.as_dict()
        payload["execution_sensitivity"] = sensitivity_report.as_dict()
        payload["post_trade_review"] = post_trade_review.as_dict()
        payload["broker_fill_reconciliation"] = broker_reconciliation.as_dict()
        payload["live_session_risk_usage"] = risk_usage.as_dict()
        payload["session_closeout"] = session_closeout.as_dict()
        journal_path = save_execution_journal_report(execution_journal)
        recent_journals = load_execution_journal_records(symbol=execution_journal.symbol, limit=5)
        end_of_day_review = build_end_of_day_review_report(session_closeout, recent_journals)
        closeout_signoff_preview = build_closeout_signoff_preview(
            session_closeout,
            review_token=args.closeout_signoff_review_token,
            directory=args.closeout_signoff_dir,
        )
        payload["execution_journal"] = execution_journal.as_dict()
        payload["execution_journal_path"] = str(journal_path)
        payload["end_of_day_review"] = end_of_day_review.as_dict()
        payload["closeout_signoff_preview"] = closeout_signoff_preview.as_dict()
        if args.closeout_signoff_review_token:
            try:
                signoff_path = write_closeout_signoff_after_review(
                    session_closeout,
                    end_of_day_review,
                    review_token=args.closeout_signoff_review_token,
                    directory=args.closeout_signoff_dir,
                    reviewer_note=args.closeout_signoff_note,
                )
            except ValueError as exc:
                raise SystemExit(str(exc)) from exc
            payload["closeout_signoff_path"] = str(signoff_path)
        payload["recent_execution_journals"] = [
            {
                "saved_at": row.get("saved_at", ""),
                "journal_id": row.get("journal_id", ""),
                "status": row.get("status", ""),
                "timestamp": row.get("timestamp", ""),
                "path": row.get("path", ""),
            }
            for row in recent_journals
        ]
        print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))


def _run_reconciliation_command(args) -> None:
    path = args.path or default_position_reconciliation_path()
    state_path = args.position_state or default_position_state_path()
    try:
        persisted = load_position_snapshot(state_path)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    if persisted is None:
        raise SystemExit("reconcile requires a saved position state; use the dashboard or --position-state first")
    if args.record:
        broker_snapshot = _broker_snapshot_from_args(args, persisted)
        save_broker_position_snapshot(broker_snapshot, path)
    else:
        try:
            broker_snapshot = load_broker_position_snapshot(path)
        except ValueError as exc:
            raise SystemExit(str(exc)) from exc
    report = reconcile_position_state(persisted, broker_snapshot)
    payload = {
        "path": str(path),
        "position_state": str(state_path),
        "persisted": persisted.as_dict(),
        "broker_snapshot": broker_snapshot.as_dict() if broker_snapshot else None,
        "reconciliation": report.as_dict(),
        "capability_note": "manual broker snapshot reconciliation only; no brokerage API connection or execution proof",
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))


def _broker_snapshot_from_args(args, persisted: PositionSnapshot | None = None) -> BrokerPositionSnapshot:
    required = ["total_qty", "sellable_qty", "purchasable_qty"]
    missing = [name for name in required if getattr(args, name, None) in (None, "")]
    if missing:
        raise SystemExit("reconcile --record requires " + ", ".join(f"--{name.replace('_', '-')}" for name in missing))
    market_source = args.market_source or (persisted.market_source if persisted else None)
    symbol = args.symbol or (persisted.symbol if persisted else None)
    if not market_source:
        raise SystemExit("reconcile --record requires --market-source or saved position state")
    if not symbol:
        raise SystemExit("reconcile --record requires --symbol or saved position state")
    return BrokerPositionSnapshot(
        market_source=market_source,
        symbol=symbol,
        total_qty=args.total_qty,
        sellable_qty=args.sellable_qty,
        purchasable_qty=args.purchasable_qty,
        cash_available=args.cash_available,
        as_of=args.as_of or "",
        note=args.note or "",
    )

def _run_broker_promote_command(args) -> None:
    broker_fills = load_broker_fill_export(args.path)
    manual_path = args.manual_fills_path or default_manual_fills_path()
    manual_fills = load_manual_fills(manual_path)
    preview = build_broker_fill_promotion_preview(
        manual_fills=manual_fills,
        broker_fills=broker_fills,
        broker_fill_id=args.broker_fill_id,
        pair_id=args.pair_id,
        review_token=args.review_token,
    )
    payload = {
        "path": args.path,
        "manual_fills_path": str(manual_path),
        "promotion": preview.as_dict(),
    }
    if args.review_token:
        promoted = promote_broker_fill_after_review(
            manual_fills=manual_fills,
            broker_fills=broker_fills,
            broker_fill_id=args.broker_fill_id,
            pair_id=args.pair_id,
            review_token=args.review_token,
            note=args.note,
        )
        record_manual_fill(promoted, manual_path)
        payload["recorded"] = promoted.as_dict()
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))



def _run_broker_import_command(args) -> None:
    broker_fills = load_broker_fill_export(args.path)
    manual_fills = load_manual_fills(args.manual_fills_path or default_manual_fills_path())
    report = reconcile_manual_fills_with_broker_export(manual_fills, broker_fills, symbol=args.symbol)
    payload = {
        "path": args.path,
        "manual_fills_path": args.manual_fills_path or str(default_manual_fills_path()),
        "supported_columns": list(supported_broker_fill_columns()),
        "report": report.as_dict(),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))



def _run_fills_command(args) -> None:
    path = args.path or default_manual_fills_path()
    if args.record:
        fill = _manual_fill_from_args(args)
        record_manual_fill(fill, path)
        print(json.dumps({"recorded": fill.as_dict(), "path": str(path)}, ensure_ascii=False, indent=2, default=str))
        return
    fills = load_manual_fills(path)
    if args.symbol:
        fills = [fill for fill in fills if fill.symbol == args.symbol]
    print(json.dumps({"fills": [fill.as_dict() for fill in fills], "path": str(path)}, ensure_ascii=False, indent=2, default=str))


def _manual_fill_from_args(args):
    required = ["symbol", "side", "qty", "price"]
    missing = [name for name in required if getattr(args, name, None) in (None, "")]
    if missing:
        raise SystemExit("fills --record requires " + ", ".join(f"--{name.replace('_', '-')}" for name in missing))
    pair_id = args.pair_id or manual_pair_id(args.symbol, args.open_pair_side, args.open_pair_price, args.qty)
    return make_manual_fill(
        symbol=args.symbol,
        pair_id=pair_id,
        side=args.side,
        qty=args.qty,
        price=args.price,
        ts=args.ts,
        fees=args.fees,
        slippage=args.slippage,
        note=args.note,
    )

def _add_fee_args(parser) -> None:
    parser.add_argument("--fee-profile", default=None, help="Fee profile id; use zero_fee_research only for explicit research checks.")
    parser.add_argument("--ignore-fees", action="store_true", help="Explicitly use zero fees/slippage for research sensitivity only.")
    parser.add_argument("--buy-commission-rate", type=float, default=0.00025)
    parser.add_argument("--sell-commission-rate", type=float, default=0.00025)
    parser.add_argument("--min-commission", type=float, default=5.0)
    parser.add_argument("--stamp-tax-rate", type=float, default=0.0005)
    parser.add_argument("--transfer-fee-rate", type=float, default=0.00001)
    parser.add_argument("--other-fee-rate", type=float, default=0.0)
    parser.add_argument("--buy-slippage-rate", type=float, default=0.0001)
    parser.add_argument("--sell-slippage-rate", type=float, default=0.0001)


def _add_prompt_args(parser) -> None:
    parser.add_argument("--scenario", default="mean_revert")
    parser.add_argument("--csv")
    parser.add_argument("--symbol")
    parser.add_argument("--bankroll", type=float)
    parser.add_argument("--target-qty", type=int)
    parser.add_argument("--settled-sellable-qty", type=int)
    parser.add_argument("--trade-qty", type=int)
    parser.add_argument("--trade-fraction", type=float, default=0.10)
    parser.add_argument("--cash", type=float)
    parser.add_argument("--open-pair-side", choices=["SB", "BS"])
    parser.add_argument("--open-pair-price", type=float)
    parser.add_argument("--open-pair-qty", type=int)
    parser.add_argument("--sb-deviation", type=float, default=0.005)
    parser.add_argument("--bs-deviation", type=float, default=-0.005)
    parser.add_argument("--min-amount-ratio", type=float, default=1.2)
    parser.add_argument("--start-time", default="09:45")
    parser.add_argument("--latest-open-time", default="14:35")
    parser.add_argument("--scan", action="store_true")
    parser.add_argument("--max-prompts", type=int, default=10)


def _add_position_state_args(parser) -> None:
    parser.add_argument("--position-state", default=None, help="Path to shared position state JSON.")
    parser.add_argument("--no-position-state", action="store_true", help="Do not read saved position state.")


def _args_with_position_state(args):
    merged = copy(args)
    if getattr(merged, "no_position_state", False):
        return merged
    state_path = getattr(merged, "position_state", None) or default_position_state_path()
    try:
        snapshot = load_position_snapshot(state_path)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    if snapshot is None:
        return merged
    _merge_position_snapshot(merged, snapshot)
    return merged


def _merge_position_snapshot(args, snapshot: PositionSnapshot) -> None:
    if getattr(args, "symbol", None) is None and snapshot.symbol:
        args.symbol = snapshot.symbol
    if not hasattr(args, "data_source") or getattr(args, "data_source", None) is None:
        args.data_source = _data_source_from_snapshot(snapshot)

    if hasattr(args, "target_qty") and getattr(args, "target_qty", None) is None:
        args.target_qty = snapshot.held_qty
    if hasattr(args, "held_qty") and getattr(args, "held_qty", None) is None:
        args.held_qty = snapshot.held_qty
    if hasattr(args, "settled_sellable_qty") and getattr(args, "settled_sellable_qty", None) is None:
        args.settled_sellable_qty = snapshot.settled_sellable_qty
    if hasattr(args, "purchasable_qty") and getattr(args, "purchasable_qty", None) is None:
        args.purchasable_qty = snapshot.purchasable_qty
    if hasattr(args, "trade_qty") and getattr(args, "trade_qty", None) is None and snapshot.max_single_trade_qty:
        args.trade_qty = snapshot.max_single_trade_qty
    if hasattr(args, "max_t_ratio") and getattr(args, "max_t_ratio", None) is None:
        args.max_t_ratio = snapshot.max_t_ratio
    if hasattr(args, "max_single_trade_qty") and getattr(args, "max_single_trade_qty", None) is None:
        args.max_single_trade_qty = snapshot.max_single_trade_qty
    if hasattr(args, "risk_preset") and getattr(args, "risk_preset", None) is None:
        args.risk_preset = snapshot.risk_limit_preset_id
    if hasattr(args, "fee_profile") and getattr(args, "fee_profile", None) is None:
        args.fee_profile = snapshot.fee_profile_id
    if hasattr(args, "ignore_fees") and not getattr(args, "ignore_fees", False) and snapshot.ignore_fees:
        args.ignore_fees = True

    if getattr(args, "open_pair_side", None) is None:
        args.open_pair_side = snapshot.open_pair_side
    if getattr(args, "open_pair_price", None) is None:
        args.open_pair_price = snapshot.open_pair_price
    if getattr(args, "open_pair_qty", None) is None:
        args.open_pair_qty = snapshot.open_pair_qty


def _load_bars_from_args(args):
    sources = [bool(args.csv), bool(args.symbol)]
    if sum(sources) > 1:
        raise SystemExit("use only one real data source: --csv or --symbol")
    if args.csv:
        return load_minute_csv(args.csv)
    if args.symbol:
        if _data_source_from_args(args) == "yahoo":
            return fetch_yahoo_intraday_bars(args.symbol)
        return fetch_intraday_minute_bars(args.symbol)
    return get_scenario(args.scenario)


def _manual_fill_symbol_from_args(args) -> str:
    if getattr(args, "symbol", None):
        if _data_source_from_args(args) == "yahoo":
            return normalize_yahoo_symbol(args.symbol)
        return args.symbol
    return _data_label(args)



def _data_label(args) -> str:
    if args.csv:
        return args.csv
    if args.symbol:
        if _data_source_from_args(args) == "yahoo":
            return f"yahoo:{normalize_yahoo_symbol(args.symbol)}"
        return f"eastmoney:{args.symbol}"
    return f"scenario:{args.scenario}"


def _data_source_from_args(args) -> str:
    return getattr(args, "data_source", None) or "eastmoney"


def _data_source_from_snapshot(snapshot: PositionSnapshot) -> str:
    return "yahoo" if snapshot.market_source.startswith("Korea") else "eastmoney"


def _rules_config_from_args(args) -> RulesConfig:
    max_t_ratio = args.max_t_ratio if args.max_t_ratio is not None else 0.10
    max_single_trade_qty = getattr(args, "max_single_trade_qty", None)
    if _data_source_from_args(args) == "yahoo":
        base_rules = RulesConfig(
            lot_size=1,
            minimum_order_qty=1,
            max_t_ratio=max_t_ratio,
            max_single_trade_qty=max_single_trade_qty,
            start_time="09:15",
            latest_open_time="15:05",
            force_restore_time="15:20",
            close_time="15:30",
            price_limit_pct=0.30,
        )
    else:
        base_rules = RulesConfig(max_t_ratio=max_t_ratio, max_single_trade_qty=max_single_trade_qty)
    return rules_with_risk_limit_preset(base_rules, getattr(args, "risk_preset", None))



def _fee_config_from_args(args) -> FeeConfig:
    profile_id = _fee_profile_id_from_args(args)
    custom_config = FeeConfig(
        buy_commission_rate=getattr(args, "buy_commission_rate", 0.00025),
        sell_commission_rate=getattr(args, "sell_commission_rate", 0.00025),
        min_commission=getattr(args, "min_commission", 5.0),
        stamp_tax_rate=getattr(args, "stamp_tax_rate", 0.0005),
        transfer_fee_rate=getattr(args, "transfer_fee_rate", 0.00001),
        other_fee_rate=getattr(args, "other_fee_rate", 0.0),
        buy_slippage_rate=getattr(args, "buy_slippage_rate", 0.0001),
        sell_slippage_rate=getattr(args, "sell_slippage_rate", 0.0001),
    )
    return fee_config_from_profile(profile_id, custom_config=custom_config, market_source=_market_source_from_args(args))
def _fee_profile_id_from_args(args) -> str:
    if getattr(args, "ignore_fees", False):
        return ZERO_FEE_PROFILE_ID
    return normalize_fee_profile_id(getattr(args, "fee_profile", None), _market_source_from_args(args))


def _market_source_from_args(args) -> str:
    return "Korea / Yahoo Finance" if _data_source_from_args(args) == "yahoo" else "A-share / Eastmoney"


if __name__ == "__main__":
    main()











