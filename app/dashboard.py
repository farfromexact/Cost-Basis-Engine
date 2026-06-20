from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


def _refresh_project_modules_after_deploy() -> None:
    project_prefixes = ("app.", "core.", "data.", "research.")
    for module_name in list(sys.modules):
        if module_name != __name__ and module_name.startswith(project_prefixes):
            sys.modules.pop(module_name, None)


_refresh_project_modules_after_deploy()

import time
from datetime import datetime

import altair as alt
import pandas as pd
import streamlit as st

from app.broker_import import BrokerFillPromotionPreview, BrokerImportReconciliationReport, default_broker_fill_export_path, load_broker_fill_export, reconcile_manual_fills_with_broker_export, supported_broker_fill_columns
from app.closeout_signoff import CloseoutSignoffPreview, build_closeout_signoff_preview
from app.end_of_day_review import EndOfDayReviewReport, build_end_of_day_review_report, build_end_of_day_review_table
from app.execution_journal import ExecutionJournalReport, build_execution_journal_history_table, load_execution_journal_records, save_execution_journal_report, build_execution_journal_report
from core.fee_model import FeeConfig, FeeModel
from app.execution_sensitivity import ExecutionSensitivityReport, build_execution_sensitivity_report
from app.manual_fills import (
    build_execution_checklist,
    default_manual_fills_path,
    expected_next_fill_side,
    load_manual_fills,
    make_manual_fill,
    manual_pair_id,
    record_manual_fill,
)
from core.fee_profiles import (
    CUSTOM_FEE_PROFILE_ID,
    ZERO_FEE_PROFILE_ID,
    default_fee_profile_id,
    fee_model_from_profile,
    fee_profile_choices,
    fee_profile_description,
    fee_profile_label,
    normalize_fee_profile_id,
)
from data.eastmoney import fetch_intraday_minute_bars
from data.yahoo import fetch_yahoo_intraday_bars, normalize_yahoo_symbol
from app.order_ticket import PreTradeOrderTicket, build_pre_trade_order_ticket
from app.post_trade_review import PostTradeReviewReport, build_post_trade_review_report
from app.session_closeout import SessionCloseoutPairAttribution, SessionCloseoutReport, build_session_closeout_report
from app.session_risk import LiveSessionRiskUsageReport, build_live_session_risk_usage_report
from app.position_state import PositionSnapshot, default_position_state_path, load_position_snapshot, save_position_snapshot
from app.position_reconciliation import (
    BrokerPositionSnapshot,
    PositionReconciliationReport,
    default_position_reconciliation_path,
    load_broker_position_snapshot,
    reconcile_position_state,
    save_broker_position_snapshot,
)
from research.data_quality import DataQualityReport, build_data_quality_report
from research.decision_summary import DecisionSummary, build_decision_summary
from research.evaluation_report import DEFAULT_LOCKED_OOS_SCENARIOS, DEFAULT_SCENARIOS, EvaluationReport, build_evaluation_report
from research.model_audit import (
    MODEL_AUDIT_BASELINE_REVIEW_TOKEN,
    ModelAuditBaselineUpdatePreview,
    ModelChangeAuditReport,
    build_model_audit_baseline_update_preview,
    build_model_change_audit_report,
    update_model_audit_baseline_after_review,
)
from research.opportunity_lifecycle import scan_opportunity_lifecycle
from research.risk_limits import DEFAULT_RISK_LIMIT_PRESET_ID, risk_limit_description, risk_limit_label, risk_limit_preset, risk_limit_preset_ids, rules_with_risk_limit_preset
from research.source_disclosure import DataSourceDisclosure, build_data_source_disclosure
from research.threshold_experiments import ThresholdExperimentReport, build_threshold_experiment_report
from research.trigger_engine import (
    ActionType,
    PositionState,
    RulesConfig,
    TradeIntent,
    TriggerEngine,
    zero_fee_model,
)


ACTION_LABELS = {
    ActionType.NO_TRADE: "No Trade",
    ActionType.WATCH_SELL_TO_BUY: "Watch S->B",
    ActionType.TRIGGER_SELL_TO_BUY: "Trigger S->B",
    ActionType.WATCH_BUY_TO_SELL: "Watch B->S",
    ActionType.TRIGGER_BUY_TO_SELL: "Trigger B->S",
    ActionType.MANAGE_OPEN_PAIR: "Manage Open Pair",
    ActionType.FORCE_CLOSE_OR_RESTORE: "Force Close/Restore",
}

REGIME_LABELS = {
    "MEAN_REVERTING": "Mean Reversion",
    "TREND_UP": "Trend Up",
    "TREND_DOWN": "Trend Down",
    "EVENT_DRIVEN": "Event Driven",
    "ILLIQUID": "Illiquid",
    "LIMIT_RISK": "Limit Risk",
    "LATE_SESSION": "Late Session",
    "NO_TRADE": "No Trade",
}

SIDE_LABELS = {
    "SELL_TO_BUY": "S->B",
    "BUY_TO_SELL": "B->S",
    "NONE": "None",
}


_MARKET_A_SHARE = "A-share / Eastmoney"
_MARKET_KOREA = "Korea / Yahoo Finance"
_PAGE_INTRADAY = "Intraday trading"
_PAGE_EXECUTION = "Execution / EOD review"
_PAGE_RESEARCH = "Research / Audit"
_REPLAY_TIME_KEY = "intraday_replay_time"
_PRICE_CHART_WIDGET_VERSION_KEY = "intraday_price_chart_widget_version"


def main() -> None:
    st.set_page_config(page_title="Cost Basis Engine", page_icon="chart_with_downwards_trend", layout="wide")
    st.markdown(
        """
        <style>
        .block-container { padding-top: 1rem; }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.title("Cost Basis Engine")
    st.caption("Regime -> Deviation -> Inventory -> TradeIntent")
    state_path = default_position_state_path()

    with st.sidebar:
        st.header("Inputs")
        persist_position_state = st.checkbox(
            "Persist position state",
            value=False,
            help="Opt in to load/save sidebar inventory context. Leave off to keep this module idle during reruns.",
        )
        if persist_position_state:
            saved_state = _load_position_state_for_dashboard(state_path)
            default_state = saved_state or PositionSnapshot()
            st.caption(f"State file: {state_path}")
        else:
            saved_state = None
            default_state = PositionSnapshot()
            st.caption("Position persistence idle: no state file is loaded or saved during reruns.")
        market_options = [_MARKET_A_SHARE, _MARKET_KOREA]
        saved_market = default_state.market_source if default_state.market_source in market_options else _MARKET_A_SHARE
        market_source = st.selectbox("Market / data source", market_options, index=market_options.index(saved_market))
        is_korea = market_source.startswith("Korea")
        source_matches_saved = default_state.market_source == market_source
        fallback_symbol = "005930.KS" if is_korea else "603236"
        default_symbol = default_state.symbol if source_matches_saved and default_state.symbol else fallback_symbol
        symbol_help = "Examples: 005930.KS, 005935.KS" if is_korea else "Examples: 603236, 000001"
        qty_step = 1 if is_korea else 100
        default_held_qty = int(default_state.held_qty) if source_matches_saved else (1000 if is_korea else 151400)
        default_purchasable_qty = int(default_state.purchasable_qty) if source_matches_saved else (100 if is_korea else 15100)

        symbol = st.text_input("Symbol", value=default_symbol, help=symbol_help, key=f"symbol_{'kr' if is_korea else 'cn'}")
        held_qty = st.number_input("Target / held quantity", min_value=0, value=default_held_qty, step=qty_step)
        purchasable_qty = st.number_input("Purchasable quantity", min_value=0, value=default_purchasable_qty, step=qty_step)
        compact_mode = st.checkbox("Compact mode", value=False, help="Show only the main decision and primary chart.")
        show_chart_markers = st.checkbox(
            "Show chart signal markers",
            value=False,
            help="Off by default so dense SB/BS markers do not obscure the price chart.",
        )

        with st.expander("Advanced", expanded=False):
            default_settled_qty = int(default_state.settled_sellable_qty) if source_matches_saved else int(held_qty)
            default_max_t_ratio = float(default_state.max_t_ratio) if source_matches_saved else 0.10
            default_max_single_trade_qty = int(default_state.max_single_trade_qty or 0) if source_matches_saved else 0
            default_open_pair_side = default_state.open_pair_side if source_matches_saved and default_state.open_pair_side in {"SB", "BS"} else "None"
            default_open_pair_price = float(default_state.open_pair_price or 0.0) if source_matches_saved else 0.0
            default_open_pair_qty = int(default_state.open_pair_qty or 0) if source_matches_saved else 0

            settled_sellable_qty = st.number_input("Settled sellable quantity", min_value=0, value=default_settled_qty, step=qty_step)
            max_t_ratio = st.slider("Max single T ratio", min_value=0.01, max_value=0.30, value=default_max_t_ratio, step=0.01)
            max_single_trade_qty = st.number_input("Max single trade quantity (0 = unlimited)", min_value=0, value=default_max_single_trade_qty, step=qty_step)
            risk_options = list(risk_limit_preset_ids())
            saved_risk_preset = default_state.risk_limit_preset_id if source_matches_saved else DEFAULT_RISK_LIMIT_PRESET_ID
            if saved_risk_preset not in risk_options:
                saved_risk_preset = DEFAULT_RISK_LIMIT_PRESET_ID
            risk_limit_preset_id = st.selectbox("Risk-limit preset", risk_options, index=risk_options.index(saved_risk_preset), format_func=risk_limit_label)
            st.caption(risk_limit_description(risk_limit_preset_id))

            st.subheader("Fees and slippage")
            fee_options = fee_profile_choices(market_source)
            default_fee_profile = _dashboard_fee_profile_id(default_state, market_source, source_matches_saved)
            if default_fee_profile not in fee_options:
                fee_options.append(default_fee_profile)
            fee_profile_id = st.selectbox(
                "Fee profile",
                fee_options,
                index=fee_options.index(default_fee_profile),
                format_func=fee_profile_label,
                help="Zero-fee is research-only and must be selected explicitly.",
            )
            custom_fee_config = _custom_fee_config_from_sidebar(FeeConfig()) if fee_profile_id == CUSTOM_FEE_PROFILE_ID else None
            st.caption(fee_profile_description(fee_profile_id))
            if fee_profile_id == ZERO_FEE_PROFILE_ID:
                st.warning("Zero-fee mode is for mechanics/sensitivity only; do not treat it as live guidance.")
            ignore_fees = fee_profile_id == ZERO_FEE_PROFILE_ID
            marker_cooldown_minutes = st.number_input("Signal marker cooldown minutes", min_value=1, value=10, step=1)

            st.subheader("Open pair (optional)")
            open_pair_side = st.selectbox("Open pair side", ["None", "SB", "BS"], index=["None", "SB", "BS"].index(default_open_pair_side))
            open_pair_price = st.number_input("Open pair first-leg price", min_value=0.0, value=default_open_pair_price, step=0.01)
            open_pair_qty = st.number_input("Open pair quantity", min_value=0, value=default_open_pair_qty, step=qty_step)
        st.divider()
        dashboard_page = st.radio(
            "Page",
            [_PAGE_INTRADAY, _PAGE_EXECUTION, _PAGE_RESEARCH],
            index=0,
            help="Intraday keeps refresh lightweight; execution and research pages load slower workflows only when opened.",
        )
        auto_refresh = st.checkbox("Auto refresh", value=False)
        refresh_seconds = st.number_input("Refresh interval seconds", min_value=10, value=60, step=10)
    if not symbol.strip():
        st.warning("Enter a symbol.")
        return

    current_position_state = PositionSnapshot(
        symbol=symbol.strip(),
        market_source=market_source,
        held_qty=int(held_qty),
        settled_sellable_qty=int(settled_sellable_qty),
        purchasable_qty=int(purchasable_qty),
        max_t_ratio=float(max_t_ratio),
        max_single_trade_qty=int(max_single_trade_qty) or None,
        risk_limit_preset_id=risk_limit_preset_id,
        fee_profile_id=fee_profile_id,
        ignore_fees=bool(ignore_fees),
        open_pair_side=None if open_pair_side == "None" else open_pair_side,
        open_pair_price=float(open_pair_price) if open_pair_price else None,
        open_pair_qty=int(open_pair_qty) if open_pair_qty else None,
    )
    if persist_position_state:
        _save_position_state_for_dashboard(current_position_state, state_path)

    try:
        normalized_symbol = _normalize_symbol(market_source, symbol.strip())
        bars = _fetch_bars(market_source, normalized_symbol)
        intent = _evaluate_intent(
            symbol=normalized_symbol,
            market_source=market_source,
            bars=bars,
            held_qty=int(held_qty),
            settled_sellable_qty=int(settled_sellable_qty),
            purchasable_qty=int(purchasable_qty),
            max_t_ratio=float(max_t_ratio),
            max_single_trade_qty=int(max_single_trade_qty) or None,
            risk_limit_preset_id=risk_limit_preset_id,
            ignore_fees=bool(ignore_fees),
            open_pair_side=None if open_pair_side == "None" else open_pair_side,
            open_pair_price=float(open_pair_price) if open_pair_price else None,
            open_pair_qty=int(open_pair_qty) if open_pair_qty else None,
            fee_profile_id=fee_profile_id,
            custom_fee_config=custom_fee_config,
        )
    except Exception as exc:
        st.error(f"Fetch or calculation failed: {type(exc).__name__}: {exc}")
        return

    market_df = _build_market_frame(bars)
    replay_time = _get_replay_time_from_session(market_df)
    display_bars = bars
    display_market_df = market_df
    display_intent = intent
    display_signal_markers = pd.DataFrame()
    if replay_time is not None:
        display_bars = _bars_until_replay_time(bars, replay_time)
        display_market_df = _build_market_frame(display_bars)
        display_intent = _evaluate_intent(
            symbol=normalized_symbol,
            market_source=market_source,
            bars=display_bars,
            held_qty=int(held_qty),
            settled_sellable_qty=int(settled_sellable_qty),
            purchasable_qty=int(purchasable_qty),
            max_t_ratio=float(max_t_ratio),
            max_single_trade_qty=int(max_single_trade_qty) or None,
            risk_limit_preset_id=risk_limit_preset_id,
            ignore_fees=bool(ignore_fees),
            open_pair_side=None if open_pair_side == "None" else open_pair_side,
            open_pair_price=float(open_pair_price) if open_pair_price else None,
            open_pair_qty=int(open_pair_qty) if open_pair_qty else None,
            fee_profile_id=fee_profile_id,
            custom_fee_config=custom_fee_config,
        )
    st.subheader("Trading decision")
    _render_intent_compact(display_intent)
    if not compact_mode:
        _render_decision_summary(build_decision_summary(display_intent))
    source_disclosure = build_data_source_disclosure(market_source)
    data_quality_now = display_bars[-1].ts if replay_time is not None else datetime.now()
    data_quality_report = build_data_quality_report(display_bars, market_source=market_source, now=data_quality_now)
    _render_status_strip(source_disclosure, data_quality_report, display_intent)
    st.caption(_data_caption(market_source, normalized_symbol, display_bars))
    _render_replay_mode_banner(replay_time)
    if dashboard_page == _PAGE_INTRADAY:
        st.caption("Execution panels and research/audit modules are lazy-loaded on separate pages to keep intraday refreshes light.")
        st.subheader("Intraday market")
        _render_market_ratio_metrics(display_market_df, display_intent)
        display_signal_markers = _scan_signal_markers(
            symbol=normalized_symbol,
            market_source=market_source,
            bars=display_bars,
            held_qty=int(held_qty),
            settled_sellable_qty=int(settled_sellable_qty),
            purchasable_qty=int(purchasable_qty),
            max_t_ratio=float(max_t_ratio),
            max_single_trade_qty=int(max_single_trade_qty) or None,
            risk_limit_preset_id=risk_limit_preset_id,
            ignore_fees=bool(ignore_fees),
            open_pair_side=None if open_pair_side == "None" else open_pair_side,
            open_pair_price=float(open_pair_price) if open_pair_price else None,
            open_pair_qty=int(open_pair_qty) if open_pair_qty else None,
            fee_profile_id=fee_profile_id,
            custom_fee_config=custom_fee_config,
            marker_cooldown_minutes=int(marker_cooldown_minutes),
        )
        _render_price_chart(market_df, display_signal_markers, display_intent, show_markers=show_chart_markers)
        _render_signal_summary(display_signal_markers)
        if not compact_mode:
            _render_data_risk_details(source_disclosure, data_quality_report, display_intent)
            _render_layers(display_intent)
    elif dashboard_page == _PAGE_EXECUTION:
        _render_data_risk_details(source_disclosure, data_quality_report, display_intent)
        st.subheader("Execution / EOD review")
        st.caption(
            "This page lazy-loads manual fills, broker reconciliation, execution journal, closeout review, "
            "post-trade review, live risk usage, and EOD signoff panels."
        )
        if replay_time is not None:
            st.caption(
                "Replay-at-time only rewinds market/model state above. Execution/accounting panels remain live/current "
                "because manual fills, broker imports, journals, and account snapshots are not time-versioned."
            )
        manual_fills_path = default_manual_fills_path()
        manual_fills = _load_manual_fills_for_dashboard(manual_fills_path)
        _render_manual_execution_panel(
            symbol=normalized_symbol,
            open_pair_side=None if open_pair_side == "None" else open_pair_side,
            open_pair_price=float(open_pair_price) if open_pair_price else None,
            open_pair_qty=int(open_pair_qty) if open_pair_qty else None,
            latest_price=float(intent.reference_price),
            fills=manual_fills,
            path=manual_fills_path,
        )
        broker_export_path = default_broker_fill_export_path()
        broker_fills = []
        if broker_export_path.exists():
            try:
                broker_fills = load_broker_fill_export(broker_export_path)
            except ValueError:
                broker_fills = []
        broker_reconciliation = reconcile_manual_fills_with_broker_export(manual_fills, broker_fills, symbol=normalized_symbol)
        _render_broker_import_reconciliation_panel(
            symbol=normalized_symbol,
            manual_fills=manual_fills,
            path=broker_export_path,
        )
        rules = _rules_for_market(market_source, float(max_t_ratio), int(max_single_trade_qty) or None, risk_limit_preset_id)
        fee_model = _fee_model_for_execution(market_source, bool(ignore_fees), fee_profile_id, custom_fee_config)
        broker_snapshot = _load_broker_position_snapshot_for_dashboard(default_position_reconciliation_path())
        ticket = build_pre_trade_order_ticket(intent, broker_snapshot, fee_model, rules)
        sensitivity_report = build_execution_sensitivity_report(intent)
        post_trade_review = build_post_trade_review_report(ticket, sensitivity_report, manual_fills)

        live_session_risk = build_live_session_risk_usage_report(
            symbol=normalized_symbol,
            fills=manual_fills,
            target_qty=int(held_qty),
            reference_price=float(intent.reference_price or 0.0),
            preset_id=risk_limit_preset_id,
            session_date=bars[-1].ts if bars else None,
            as_of=bars[-1].ts if bars else None,
        )
        execution_journal = build_execution_journal_report(
            intent=intent,
            ticket=ticket,
            manual_fills=manual_fills,
            post_trade_review=post_trade_review,
            broker_reconciliation=broker_reconciliation,
            risk_usage=live_session_risk,
        )
        session_closeout = build_session_closeout_report(
            symbol=normalized_symbol,
            manual_fills=manual_fills,
            broker_reconciliation=broker_reconciliation,
            risk_usage=live_session_risk,
            session_date=bars[-1].ts if bars else None,
        )
        _render_pre_trade_order_ticket_panel(ticket)
        _render_execution_sensitivity_panel(sensitivity_report)
        _render_post_trade_review_panel(post_trade_review)
        _render_live_session_risk_usage_panel(live_session_risk)
        _render_session_closeout_panel(session_closeout)
        journal_path = save_execution_journal_report(execution_journal)
        recent_journals = load_execution_journal_records(symbol=execution_journal.symbol, limit=5)
        end_of_day_review = build_end_of_day_review_report(session_closeout, recent_journals)
        _render_end_of_day_review_panel(end_of_day_review)
        _render_execution_journal_panel(execution_journal, journal_path=journal_path, recent_journals=recent_journals)
    else:
        _render_data_risk_details(source_disclosure, data_quality_report, display_intent)
        _render_research_audit_page(
            market_source=market_source,
            held_qty=int(held_qty),
            settled_sellable_qty=int(settled_sellable_qty),
            purchasable_qty=int(purchasable_qty),
            max_t_ratio=float(max_t_ratio),
            max_single_trade_qty=int(max_single_trade_qty) or None,
            risk_limit_preset_id=risk_limit_preset_id,
            fee_profile_id=fee_profile_id,
            custom_fee_config=custom_fee_config,
        )

    if auto_refresh:
        time.sleep(int(refresh_seconds))
        st.rerun()


def _evaluate_intent(
    symbol: str,
    market_source: str,
    bars,
    held_qty: int,
    settled_sellable_qty: int,
    purchasable_qty: int,
    max_t_ratio: float,
    max_single_trade_qty: int | None,
    ignore_fees: bool,
    open_pair_side: str | None,
    open_pair_price: float | None,
    open_pair_qty: int | None,
    fee_profile_id: str | None = None,
    custom_fee_config: FeeConfig | None = None,
    risk_limit_preset_id: str | None = None,
) -> TradeIntent:
    rules = _rules_for_market(market_source, max_t_ratio, max_single_trade_qty, risk_limit_preset_id)
    fee_model = _fee_model_for_execution(market_source, ignore_fees, fee_profile_id, custom_fee_config)
    engine = TriggerEngine(rules=rules, fee_model=fee_model)
    position = PositionState(
        target_qty=held_qty,
        current_total_qty=held_qty,
        settled_sellable_qty=settled_sellable_qty,
        purchasable_qty=purchasable_qty,
        open_pair_side=open_pair_side,
        open_pair_price=open_pair_price,
        open_pair_qty=open_pair_qty,
    )
    return engine.evaluate(symbol, bars, position)


def _scan_signal_markers(
    symbol: str,
    market_source: str,
    bars,
    held_qty: int,
    settled_sellable_qty: int,
    purchasable_qty: int,
    max_t_ratio: float,
    max_single_trade_qty: int | None,
    ignore_fees: bool,
    open_pair_side: str | None,
    open_pair_price: float | None,
    open_pair_qty: int | None,
    risk_limit_preset_id: str | None = None,
    marker_cooldown_minutes: int = 10,
    fee_profile_id: str | None = None,
    custom_fee_config: FeeConfig | None = None,
) -> pd.DataFrame:
    rules = _rules_for_market(market_source, max_t_ratio, max_single_trade_qty, risk_limit_preset_id)
    fee_model = _fee_model_for_execution(market_source, ignore_fees, fee_profile_id, custom_fee_config)
    position = PositionState(
        target_qty=held_qty,
        current_total_qty=held_qty,
        settled_sellable_qty=settled_sellable_qty,
        purchasable_qty=purchasable_qty,
        open_pair_side=open_pair_side,
        open_pair_price=open_pair_price,
        open_pair_qty=open_pair_qty,
    )
    events = scan_opportunity_lifecycle(
        symbol=symbol,
        bars=bars,
        position=position,
        rules=rules,
        fee_model=fee_model,
        marker_cooldown_minutes=marker_cooldown_minutes,
    )
    rows = [event.as_dict() for event in events]
    if not rows:
        return pd.DataFrame(rows)
    markers = pd.DataFrame(rows)
    markers["time"] = pd.to_datetime(markers["time"])
    return markers


def _signal_marker_row(intent: TradeIntent) -> dict | None:
    action = intent.action_type
    labels = {
        ActionType.WATCH_SELL_TO_BUY: ("Watch S->B", "Watch", "S->B"),
        ActionType.TRIGGER_SELL_TO_BUY: ("SB", "Trigger", "S->B"),
        ActionType.WATCH_BUY_TO_SELL: ("Watch B->S", "Watch", "B->S"),
        ActionType.TRIGGER_BUY_TO_SELL: ("BS", "Trigger", "B->S"),
    }
    if action not in labels:
        return None
    label, level, side = labels[action]
    feature = intent.feature_snapshot
    return {
        "time": pd.to_datetime(intent.timestamp),
        "price": intent.reference_price,
        "signal": label,
        "level": level,
        "side": side,
        "action": ACTION_LABELS[action],
        "confidence": intent.confidence,
        "suggested_qty": intent.suggested_qty,
        "vwap_deviation_pct": (feature.vwap_deviation * 100) if feature else 0.0,
        "net_edge": intent.estimated_net_edge,
        "reason": "; ".join(intent.reasons[:2]) if intent.reasons else intent.next_action,
    }


def _current_intent_marker_row(intent: TradeIntent, market_df: pd.DataFrame) -> dict:
    latest = market_df.iloc[-1]
    feature = intent.feature_snapshot
    action_label = ACTION_LABELS.get(intent.action_type, intent.action_type.value)
    reason_parts = list(intent.reasons[:2]) if intent.reasons else []
    if not reason_parts and intent.blockers:
        reason_parts = list(intent.blockers[:2])
    reason = "; ".join(reason_parts) if reason_parts else intent.next_action
    return {
        "time": pd.to_datetime(intent.timestamp or latest["time"]),
        "price": float(intent.reference_price or latest["close"]),
        "label": f"Current: {action_label}",
        "action": action_label,
        "side": SIDE_LABELS.get(intent.side.value, intent.side.value),
        "confidence": intent.confidence,
        "suggested_qty": intent.suggested_qty,
        "suggested_ratio_pct": intent.suggested_ratio * 100,
        "vwap_deviation_pct": (feature.vwap_deviation * 100) if feature else float(latest["vwap_deviation_pct"]),
        "net_edge": intent.estimated_net_edge,
        "reason": reason,
        "note": "Current decision from the latest closed minute; no fill or realized PnL is inferred.",
    }


def _normalize_symbol(market_source: str, symbol: str) -> str:
    if market_source.startswith("Korea"):
        return normalize_yahoo_symbol(symbol)
    return symbol


def _fetch_bars(market_source: str, symbol: str):
    if market_source.startswith("Korea"):
        return fetch_yahoo_intraday_bars(symbol)
    return fetch_intraday_minute_bars(symbol)



def _load_position_state_for_dashboard(path) -> PositionSnapshot | None:
    try:
        return load_position_snapshot(path)
    except ValueError as exc:
        st.sidebar.warning(str(exc))
        return None


def _save_position_state_for_dashboard(snapshot: PositionSnapshot, path) -> None:
    try:
        save_position_snapshot(snapshot, path)
    except OSError as exc:
        st.sidebar.warning(f"Could not persist position state: {exc}")

def _build_execution_sensitivity_table(report: ExecutionSensitivityReport) -> pd.DataFrame:
    return pd.DataFrame([band.as_dict() for band in report.bands])


def _render_execution_sensitivity_panel(report: ExecutionSensitivityReport) -> None:
    st.subheader("Execution-quality sensitivity")
    if report.status == "OK":
        st.success(report.summary)
    elif report.status == "WARN":
        st.warning(report.summary)
    elif report.status == "BLOCKED":
        st.error(report.summary)
    else:
        st.info(report.summary)
    cols = st.columns(4)
    cols[0].metric("Baseline net edge", f"{report.baseline_net_edge:.2f}")
    cols[1].metric("Worst stressed edge", f"{report.worst_net_edge:.2f}")
    cols[2].metric("Side", report.side)
    cols[3].metric("Qty", f"{report.qty}")
    table = _build_execution_sensitivity_table(report)
    if table.empty:
        st.caption("No actionable first-leg ticket is active, so no slippage sensitivity is shown.")
    else:
        st.dataframe(table, hide_index=True, width="stretch")
        st.caption("Bands stress the trigger-engine gross edge against higher slippage and adverse fill bps; no execution or fill is inferred.")

def _build_pre_trade_order_ticket_table(ticket: PreTradeOrderTicket) -> pd.DataFrame:
    return pd.DataFrame([check.as_dict() for check in ticket.checks])


def _render_pre_trade_order_ticket_panel(ticket: PreTradeOrderTicket) -> None:
    st.subheader("Pre-trade order ticket checklist")
    if ticket.status == "OK":
        st.success(ticket.summary)
    elif ticket.status == "WARN":
        st.warning(ticket.summary)
    elif ticket.status == "BLOCKED":
        st.error(ticket.summary)
    else:
        st.info(ticket.summary)
    cols = st.columns(4)
    cols[0].metric("Side", ticket.side)
    cols[1].metric("Qty", f"{ticket.qty}")
    cols[2].metric("Limit/ref price", f"{ticket.limit_price:.4f}")
    cols[3].metric("Cash required", f"{ticket.cash_required:.2f}")
    st.dataframe(_build_pre_trade_order_ticket_table(ticket), hide_index=True, width="stretch")
    st.caption("Checklist only: confirm broker preview, price band, available holdings/cash, and fees before submitting any order.")

def _build_execution_journal_table(report: ExecutionJournalReport) -> pd.DataFrame:
    return pd.DataFrame([item.as_dict() for item in report.items])



def _render_execution_journal_panel(report: ExecutionJournalReport, journal_path=None, recent_journals=None) -> None:
    st.subheader("Session execution journal")
    if report.status == "OK":
        st.success(report.summary)
    elif report.status == "BLOCKED":
        st.error(report.summary)
    else:
        st.warning(report.summary)
    cols = st.columns(4)
    cols[0].metric("Action", report.action_type)
    cols[1].metric("Manual fills", f"{report.manual_fill_count}")
    cols[2].metric("Broker matches", f"{report.broker_matched_count}")
    cols[3].metric("Journal status", report.status)
    st.dataframe(_build_execution_journal_table(report), hide_index=True, width="stretch")
    if journal_path:
        st.caption(f"Persisted journal: {journal_path}")
    history = build_execution_journal_history_table(recent_journals or [])
    if history:
        st.dataframe(pd.DataFrame(history), hide_index=True, width="stretch")
    st.caption("Journal links existing artifacts for audit only; it does not route orders, infer fills, or update accounting.")



def _build_broker_import_reconciliation_table(report: BrokerImportReconciliationReport) -> pd.DataFrame:
    return pd.DataFrame([item.as_dict() for item in report.items])



def _build_broker_fill_promotion_preview_table(preview: BrokerFillPromotionPreview) -> pd.DataFrame:
    return pd.DataFrame([check.as_dict() for check in preview.checks])



def _render_broker_import_reconciliation_panel(symbol: str, manual_fills, path) -> None:
    st.subheader("Broker fill import reconciliation")
    st.caption("Optional scaffold: place a broker-confirmed CSV/JSON export at the configured path to reconcile it against manual fills.")
    if not path.exists():
        st.info(f"No broker export found at {path}. Supported columns: {', '.join(supported_broker_fill_columns())}.")
        return
    try:
        broker_fills = load_broker_fill_export(path)
        report = reconcile_manual_fills_with_broker_export(manual_fills, broker_fills, symbol=symbol)
    except ValueError as exc:
        st.warning(str(exc))
        return
    if report.status == "OK":
        st.success(report.summary)
    elif report.status == "BLOCKED":
        st.error(report.summary)
    else:
        st.warning(report.summary)
    cols = st.columns(4)
    cols[0].metric("Matched", f"{report.matched_count}")
    cols[1].metric("Broker-only", f"{report.broker_only_count}")
    cols[2].metric("Manual-only", f"{report.manual_only_count}")
    cols[3].metric("Ambiguous", f"{report.ambiguous_count}")
    table = _build_broker_import_reconciliation_table(report)
    if not table.empty:
        st.dataframe(table, hide_index=True, width="stretch")
    st.caption("Broker exports are reconciliation evidence only; rows are not automatically imported as manual fills.")



def _build_live_session_risk_usage_table(report: LiveSessionRiskUsageReport) -> pd.DataFrame:
    return pd.DataFrame([check.as_dict() for check in report.checks])



def _build_session_closeout_table(report: SessionCloseoutReport) -> pd.DataFrame:
    return pd.DataFrame([check.as_dict() for check in report.checks])



def _build_session_closeout_pair_table(report: SessionCloseoutReport) -> pd.DataFrame:
    return pd.DataFrame([pair.as_dict() for pair in report.pair_attributions])



def _build_end_of_day_review_table(report: EndOfDayReviewReport) -> pd.DataFrame:
    return pd.DataFrame(build_end_of_day_review_table(report))




def _build_closeout_signoff_preview_table(preview: CloseoutSignoffPreview) -> pd.DataFrame:
    return pd.DataFrame([check.as_dict() for check in preview.checks])


def _render_closeout_signoff_panel(preview: CloseoutSignoffPreview) -> None:
    st.subheader("Reviewed closeout signoff export")
    if preview.status == "READY":
        st.success(preview.summary)
    elif preview.status == "BLOCKED":
        st.error(preview.summary)
    elif preview.status == "REVIEW_REQUIRED":
        st.warning(preview.summary)
    else:
        st.info(preview.summary)
    cols = st.columns(4)
    cols[0].metric("Closeout", preview.closeout_status)
    cols[1].metric("Countable", "YES" if preview.closeout_countable else "NO")
    cols[2].metric("Reduction", f"{preview.countable_cost_basis_reduction:.2f}")
    cols[3].metric("Export", preview.status)
    st.dataframe(_build_closeout_signoff_preview_table(preview), hide_index=True, width="stretch")
    st.caption(f"CLI export path: {preview.signoff_path}. {preview.capability_note}")
def _render_end_of_day_review_panel(report: EndOfDayReviewReport) -> None:
    st.subheader("Compact end-of-day review")
    if report.status == "OK":
        st.success(report.summary)
    elif report.status == "BLOCKED":
        st.error(report.summary)
    elif report.status == "WARN":
        st.warning(report.summary)
    else:
        st.info(report.summary)
    cols = st.columns(4)
    cols[0].metric("Closeout", report.closeout_status)
    cols[1].metric("Recent journals", f"{report.recent_journal_count}")
    cols[2].metric("Blocked journals", f"{report.blocked_journal_count}")
    cols[3].metric("Countable", "YES" if report.closeout_countable else "NO")
    st.dataframe(_build_end_of_day_review_table(report), hide_index=True, width="stretch")
    st.caption("Compact review compares current closeout with recent persisted journals; closeout gates remain authoritative.")



def _render_session_closeout_panel(report: SessionCloseoutReport) -> None:
    st.subheader("End-of-day session closeout")
    if report.status == "OK":
        st.success(report.summary)
    elif report.status == "BLOCKED":
        st.error(report.summary)
    elif report.status == "WARN":
        st.warning(report.summary)
    else:
        st.info(report.summary)
    cols = st.columns(4)
    cols[0].metric("Closed pairs", f"{report.closed_pair_count}")
    cols[1].metric("Open pairs", f"{report.open_pair_count}")
    cols[2].metric("Net qty delta", f"{report.net_position_delta_qty}")
    cols[3].metric("Countable reduction", f"{report.countable_cost_basis_reduction:.2f}")
    st.dataframe(_build_session_closeout_table(report), hide_index=True, width="stretch")
    pair_table = _build_session_closeout_pair_table(report)
    if not pair_table.empty:
        st.dataframe(pair_table, hide_index=True, width="stretch")
    st.caption("Closeout gates cost-basis accounting: broker reconciliation, restored inventory, no open risk breach, and fees/slippage deducted.")



def _render_live_session_risk_usage_panel(report: LiveSessionRiskUsageReport) -> None:
    st.subheader("Live-session risk usage")
    if report.status == "OK":
        st.success(report.summary)
    elif report.status == "BLOCKED":
        st.error(report.summary)
    else:
        st.warning(report.summary)
    cols = st.columns(4)
    cols[0].metric("Manual fills", f"{report.manual_fill_count}")
    cols[1].metric("Turnover qty", f"{report.gross_turnover_qty}")
    cols[2].metric("Open exposure", f"{report.open_pair_notional:.2f}")
    cols[3].metric("Max open age", f"{report.max_open_pair_age_minutes:.1f}m")
    st.dataframe(_build_live_session_risk_usage_table(report), hide_index=True, width="stretch")
    st.caption("Usage is counted from manual broker fills only. Preset limits are guardrails, not performance evidence.")



def _build_post_trade_review_table(report: PostTradeReviewReport) -> pd.DataFrame:
    return pd.DataFrame([check.as_dict() for check in report.checks])



def _render_post_trade_review_panel(report: PostTradeReviewReport) -> None:
    st.subheader("Post-trade review")
    if report.status == "OK":
        st.success(report.summary)
    elif report.status == "BLOCKED":
        st.error(report.summary)
    elif report.status == "NO_FILL":
        st.info(report.summary)
    else:
        st.warning(report.summary)
    cols = st.columns(4)
    cols[0].metric("Fill qty", f"{report.fill_qty}/{report.expected_qty}")
    cols[1].metric("Avg fill", f"{report.fill_avg_price:.4f}")
    cols[2].metric("Ticket price diff", f"{report.price_diff_vs_ticket:.4f}")
    cols[3].metric("Worst stressed edge", f"{report.worst_sensitivity_net_edge:.2f}")
    st.dataframe(_build_post_trade_review_table(report), hide_index=True, width="stretch")
    st.caption("Manual broker fills only: no order routing, no inferred fills, and no cost-basis reduction until both legs close, target inventory is restored, and fees/slippage are deducted.")



def _load_broker_position_snapshot_for_dashboard(path) -> BrokerPositionSnapshot | None:
    try:
        return load_broker_position_snapshot(path)
    except ValueError as exc:
        st.warning(str(exc))
        return None


def _build_position_reconciliation_table(report: PositionReconciliationReport) -> pd.DataFrame:
    return pd.DataFrame([item.as_dict() for item in report.items])


def _render_position_reconciliation_panel(
    persisted: PositionSnapshot,
    broker_snapshot: BrokerPositionSnapshot | None,
    path,
) -> None:
    st.subheader("Broker position reconciliation")
    st.caption("Persisted sidebar state is not brokerage truth. Record the current broker/account snapshot before relying on sizing.")
    report = reconcile_position_state(persisted, broker_snapshot)
    if report.status == "OK":
        st.success(report.summary)
    elif report.status == "BLOCKED":
        st.error(report.summary)
    else:
        st.warning(report.summary)
    st.dataframe(_build_position_reconciliation_table(report), hide_index=True, width="stretch")
    st.caption(f"Reconciliation file: {path}")

    with st.form("broker_position_reconciliation_form"):
        st.write("Record broker/manual position snapshot")
        broker_market_source = st.text_input("Broker market/source", value=persisted.market_source)
        broker_symbol = st.text_input("Broker symbol", value=persisted.symbol)
        total_qty = st.number_input("Broker total quantity", min_value=0, value=int(persisted.held_qty), step=1)
        sellable_qty = st.number_input("Broker sellable quantity", min_value=0, value=int(persisted.settled_sellable_qty), step=1)
        purchasable_qty = st.number_input("Broker purchasable quantity", min_value=0, value=int(persisted.purchasable_qty), step=1)
        cash_available = st.number_input("Broker cash available", min_value=0.0, value=0.0, step=100.0)
        as_of = st.text_input("Broker snapshot time", value=datetime.now().isoformat(timespec="seconds"))
        note = st.text_input("Reconciliation note", value="Manual broker/account screen check.")
        submitted = st.form_submit_button("Record broker snapshot")
    if submitted:
        snapshot = BrokerPositionSnapshot(
            market_source=broker_market_source,
            symbol=broker_symbol,
            total_qty=int(total_qty),
            sellable_qty=int(sellable_qty),
            purchasable_qty=int(purchasable_qty),
            cash_available=float(cash_available),
            as_of=as_of,
            note=note,
        )
        try:
            save_broker_position_snapshot(snapshot, path)
            st.success("Recorded broker snapshot. Refresh to update reconciliation status.")
        except (OSError, ValueError) as exc:
            st.warning(str(exc))

def _load_manual_fills_for_dashboard(path):
    try:
        return load_manual_fills(path)
    except ValueError as exc:
        st.warning(str(exc))
        return []


def _render_manual_execution_panel(
    symbol: str,
    open_pair_side: str | None,
    open_pair_price: float | None,
    open_pair_qty: int | None,
    latest_price: float,
    fills,
    path,
) -> None:
    st.subheader("Manual execution checklist")
    st.caption("Signals and lifecycle markers are decision support only. Record actual broker fills here before treating a pair as closed.")
    checklist = build_execution_checklist(symbol, open_pair_side, open_pair_price, open_pair_qty, fills)
    st.dataframe(pd.DataFrame([item.as_dict() for item in checklist.items]), hide_index=True, width="stretch")
    st.caption(f"Pair id: {checklist.pair_id}; status: {checklist.status}; fill file: {path}")
    if not open_pair_side:
        return

    next_side = expected_next_fill_side(open_pair_side, fills, checklist.pair_id)
    if next_side is None:
        st.success("Both manual legs have been recorded for this pair. Verify inventory and broker fees before claiming cost-basis reduction.")
        return

    with st.form("manual_fill_record_form"):
        st.write(f"Record manual {next_side.value} fill for {checklist.pair_id}")
        fill_qty = st.number_input("Fill quantity", min_value=1, value=max(1, int(open_pair_qty or 1)), step=1)
        fill_price = st.number_input("Fill price", min_value=0.01, value=float(latest_price or open_pair_price or 0.01), step=0.01)
        fees = st.number_input("Broker fees", min_value=0.0, value=0.0, step=0.01)
        slippage = st.number_input("Slippage / price impact", min_value=0.0, value=0.0, step=0.01)
        note = st.text_input("Manual fill note", value="Manual fill recorded from broker/order screen.")
        submitted = st.form_submit_button("Record manual fill")
    if submitted:
        fill = make_manual_fill(
            symbol=symbol,
            pair_id=checklist.pair_id,
            side=next_side,
            qty=int(fill_qty),
            price=float(fill_price),
            fees=float(fees),
            slippage=float(slippage),
            note=note,
        )
        try:
            record_manual_fill(fill, path)
            st.success(f"Recorded manual {fill.side.value} fill. Refresh to update checklist.")
        except ValueError as exc:
            st.warning(str(exc))



def _build_risk_limit_preset_table(preset_id: str | None) -> pd.DataFrame:
    preset = risk_limit_preset(preset_id)
    return pd.DataFrame(
        [
            {
                "preset_id": preset.preset_id,
                "label": preset.label,
                "max_daily_turnover_ratio": preset.max_daily_turnover_ratio,
                "max_single_pair_turnover_ratio": preset.max_daily_turnover_ratio / 2.0,
                "max_open_pair_minutes": preset.max_open_pair_minutes,
                "max_same_day_capital_at_risk_ratio": preset.max_same_day_capital_at_risk_ratio,
                "description": preset.description,
            }
        ]
    )
def _dashboard_fee_profile_id(snapshot: PositionSnapshot, market_source: str, source_matches_saved: bool) -> str:
    if source_matches_saved:
        if snapshot.ignore_fees:
            return ZERO_FEE_PROFILE_ID
        return normalize_fee_profile_id(snapshot.fee_profile_id, market_source)
    return default_fee_profile_id(market_source)


def _custom_fee_config_from_sidebar(default: FeeConfig) -> FeeConfig:
    c1, c2 = st.columns(2)
    buy_commission_rate = c1.number_input("Buy commission rate", min_value=0.0, value=float(default.buy_commission_rate), step=0.00001, format="%.5f")
    sell_commission_rate = c2.number_input("Sell commission rate", min_value=0.0, value=float(default.sell_commission_rate), step=0.00001, format="%.5f")
    min_commission = c1.number_input("Minimum commission", min_value=0.0, value=float(default.min_commission), step=0.5)
    stamp_tax_rate = c2.number_input("Sell stamp/tax rate", min_value=0.0, value=float(default.stamp_tax_rate), step=0.0001, format="%.5f")
    transfer_fee_rate = c1.number_input("Transfer fee rate", min_value=0.0, value=float(default.transfer_fee_rate), step=0.00001, format="%.5f")
    other_fee_rate = c2.number_input("Other fee rate", min_value=0.0, value=float(default.other_fee_rate), step=0.00001, format="%.5f")
    buy_slippage_rate = c1.number_input("Buy slippage rate", min_value=0.0, value=float(default.buy_slippage_rate), step=0.00001, format="%.5f")
    sell_slippage_rate = c2.number_input("Sell slippage rate", min_value=0.0, value=float(default.sell_slippage_rate), step=0.00001, format="%.5f")
    return FeeConfig(
        buy_commission_rate=buy_commission_rate,
        sell_commission_rate=sell_commission_rate,
        min_commission=min_commission,
        stamp_tax_rate=stamp_tax_rate,
        transfer_fee_rate=transfer_fee_rate,
        other_fee_rate=other_fee_rate,
        buy_slippage_rate=buy_slippage_rate,
        sell_slippage_rate=sell_slippage_rate,
    )


def _fee_model_for_execution(
    market_source: str,
    ignore_fees: bool,
    fee_profile_id: str | None = None,
    custom_fee_config: FeeConfig | None = None,
) -> FeeModel:
    if ignore_fees and fee_profile_id is None:
        return zero_fee_model()
    profile_id = ZERO_FEE_PROFILE_ID if ignore_fees else fee_profile_id
    return fee_model_from_profile(profile_id, custom_config=custom_fee_config, market_source=market_source)


def _build_model_audit_change_table(report: ModelChangeAuditReport) -> pd.DataFrame:
    rows = [change.as_dict() for change in report.threshold_changes + report.metric_changes]
    if not rows:
        rows = [
            {
                "category": "model_audit",
                "name": "baseline_match",
                "baseline": report.baseline_id,
                "current": report.baseline_id,
                "delta": 0,
                "status": "OK",
            }
        ]
    return pd.DataFrame(rows)


def _render_model_change_audit_report(report: ModelChangeAuditReport) -> None:
    st.subheader("Model-change audit")
    if report.status == "OK":
        st.success(report.summary)
    else:
        st.warning(report.summary)
    cols = st.columns(3)
    cols[0].metric("Audit status", report.status)
    cols[1].metric("Locked OOS rows", f"{report.locked_oos_count}")
    cols[2].metric("Changes", f"{len(report.threshold_changes) + len(report.metric_changes)}")
    st.dataframe(_build_model_audit_change_table(report), hide_index=True, width="stretch")
    st.caption(report.report_note)


def _build_model_audit_baseline_update_table(preview: ModelAuditBaselineUpdatePreview) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "status": preview.status,
                "baseline_id": preview.baseline_id,
                "locked_oos_count": preview.locked_oos_count,
                "threshold_change_count": preview.threshold_change_count,
                "metric_change_count": preview.metric_change_count,
                "required_review_token": preview.required_review_token,
                "can_update_without_token": preview.can_update,
            }
        ]
    )


def _render_model_audit_baseline_update_panel(preview: ModelAuditBaselineUpdatePreview) -> None:
    st.subheader("Audit baseline update review")
    if preview.status == "NO_UPDATE_NEEDED":
        st.info("No baseline update is needed because the canonical audit matches the stored baseline.")
    else:
        st.warning(preview.audit_summary)
    st.dataframe(_build_model_audit_baseline_update_table(preview), hide_index=True, width="stretch")
    st.caption(preview.report_note)
    with st.expander("Explicit baseline update gate", expanded=preview.status == "REVIEW_REQUIRED"):
        st.write("Baseline writes are disabled unless audit deltas have been reviewed and the exact token is entered.")
        st.code(MODEL_AUDIT_BASELINE_REVIEW_TOKEN)
        review_token = st.text_input("Review token", value="", type="password")
        reviewer_note = st.text_input("Reviewer note", value="")
        if st.button("Update audit baseline after review", disabled=preview.status != "REVIEW_REQUIRED"):
            try:
                result = update_model_audit_baseline_after_review(
                    review_token=review_token,
                    reviewer_note=reviewer_note,
                )
                st.success(result.report_note)
                st.json(result.as_dict())
            except ValueError as exc:
                st.error(str(exc))




def _build_threshold_experiment_comparison_table(report: ThresholdExperimentReport) -> pd.DataFrame:
    rows = []
    for experiment in report.experiments:
        deltas = experiment.aggregate_metric_deltas
        rows.append(
            {
                "experiment_id": experiment.experiment_id,
                "label": experiment.label,
                "audit_status": experiment.audit_status,
                "locked_oos_count": report.locked_oos_count,
                "threshold_change_count": len(experiment.threshold_changes),
                "metric_change_count": len(experiment.metric_changes),
                "delta_trigger_count": deltas.get("trigger_count", 0.0),
                "delta_watch_count": deltas.get("watch_count", 0.0),
                "delta_no_trade_count": deltas.get("no_trade_count", 0.0),
                "changed_thresholds": ", ".join(sorted(experiment.threshold_overrides)),
                "caveat": "locked-OOS signal deltas only; no fills, PnL, or profitability claim",
            }
        )
    return pd.DataFrame(rows)


def _build_threshold_experiment_metric_delta_table(report: ThresholdExperimentReport) -> pd.DataFrame:
    rows = []
    for experiment in report.experiments:
        for change in experiment.metric_changes:
            scenario, metric = _split_metric_change_name(change.name)
            rows.append(
                {
                    "experiment_id": experiment.experiment_id,
                    "scenario": scenario,
                    "metric": metric,
                    "baseline": change.baseline,
                    "current": change.current,
                    "delta": change.delta,
                    "status": change.status,
                }
            )
    return pd.DataFrame(rows)


def _split_metric_change_name(name: str) -> tuple[str, str]:
    if "." not in name:
        return name, ""
    scenario, metric = name.rsplit(".", 1)
    return scenario, metric


def _render_threshold_experiment_comparison(report: ThresholdExperimentReport) -> None:
    st.subheader("Locked-OOS threshold experiments")
    st.caption(
        "What-if comparison against the locked-OOS audit baseline. "
        "Deltas are signal counts only and do not imply better execution or profitability."
    )
    st.dataframe(_build_threshold_experiment_comparison_table(report), hide_index=True, width="stretch")
    with st.expander("Per-scenario experiment deltas", expanded=False):
        detail = _build_threshold_experiment_metric_delta_table(report)
        if detail.empty:
            st.info("No locked-OOS metric deltas for the selected experiments.")
        else:
            st.dataframe(detail, hide_index=True, width="stretch")
        st.caption(report.report_note)


def _render_research_audit_page(
    market_source: str,
    held_qty: int,
    settled_sellable_qty: int,
    purchasable_qty: int,
    max_t_ratio: float,
    max_single_trade_qty: int | None,
    risk_limit_preset_id: str | None,
    fee_profile_id: str | None,
    custom_fee_config: FeeConfig | None,
) -> None:
    st.subheader("Research / Audit")
    st.caption(
        "Research modules are idle by default. Run them only when you want locked-OOS validation, "
        "threshold what-if review, model-change audit, or baseline governance."
    )
    if held_qty <= 0:
        st.warning("Enter a positive target / held quantity before running evaluation or threshold experiments.")

    can_run_position_sized_research = held_qty > 0
    if st.button("Run scenario evaluation / locked-OOS", disabled=not can_run_position_sized_research):
        _render_scenario_evaluation_report(
            market_source=market_source,
            held_qty=held_qty,
            settled_sellable_qty=settled_sellable_qty,
            purchasable_qty=purchasable_qty,
            max_t_ratio=max_t_ratio,
            max_single_trade_qty=max_single_trade_qty,
            risk_limit_preset_id=risk_limit_preset_id,
            fee_profile_id=fee_profile_id,
            custom_fee_config=custom_fee_config,
        )
    else:
        st.caption("Scenario evaluation is idle.")

    if st.button("Run locked-OOS threshold experiments", disabled=not can_run_position_sized_research):
        _render_locked_oos_threshold_experiments(
            market_source=market_source,
            held_qty=held_qty,
            settled_sellable_qty=settled_sellable_qty,
            purchasable_qty=purchasable_qty,
            max_t_ratio=max_t_ratio,
            max_single_trade_qty=max_single_trade_qty,
            risk_limit_preset_id=risk_limit_preset_id,
            fee_profile_id=fee_profile_id,
            custom_fee_config=custom_fee_config,
        )
    else:
        st.caption("Threshold experiments are idle.")

    if st.button("Run model-change audit"):
        try:
            _render_model_change_audit_report(build_model_change_audit_report())
        except Exception as exc:
            st.warning(f"Model-change audit unavailable: {type(exc).__name__}: {exc}")
    else:
        st.caption("Model-change audit is idle.")

    if st.button("Load audit baseline update review"):
        try:
            _render_model_audit_baseline_update_panel(build_model_audit_baseline_update_preview())
        except Exception as exc:
            st.warning(f"Audit baseline update review unavailable: {type(exc).__name__}: {exc}")
    else:
        st.caption("Audit baseline update review is idle.")


def _render_scenario_evaluation_report(
    market_source: str,
    held_qty: int,
    settled_sellable_qty: int,
    purchasable_qty: int,
    max_t_ratio: float,
    max_single_trade_qty: int | None,
    risk_limit_preset_id: str | None,
    fee_profile_id: str | None,
    custom_fee_config: FeeConfig | None,
) -> None:
    st.subheader("Scenario evaluation")
    st.caption(
        "Registered research comparison: no-trade baseline, simple S->B replay baseline, "
        "trigger-engine signal diagnostics, and locked OOS rows when available. This is not live-symbol performance evidence."
    )
    trade_qty = _evaluation_trade_qty(market_source, held_qty, max_t_ratio, max_single_trade_qty, risk_limit_preset_id)
    fee_model = _fee_model_for_execution(market_source, False, fee_profile_id, custom_fee_config)
    try:
        report = build_evaluation_report(
            scenario_names=tuple(DEFAULT_SCENARIOS) + tuple(DEFAULT_LOCKED_OOS_SCENARIOS),
            target_qty=held_qty,
            settled_sellable_qty=settled_sellable_qty,
            purchasable_qty=purchasable_qty,
            trade_qty=trade_qty,
            fee_model=fee_model,
        )
        table = _build_evaluation_table(report)
        st.dataframe(table, hide_index=True, width="stretch")
        st.caption(report.report_note)
        with st.expander("Evaluation assumptions"):
            st.write(f"Synthetic trade quantity: {trade_qty:,}")
            st.write("No-trade baseline is always shown as zero incremental trading PnL.")
            st.write("Simple S->B replay is an interpretable baseline, not a production strategy claim.")
            st.write("Trigger-engine rows are signal diagnostics only; fills and realized PnL are not inferred.")
            st.dataframe(_build_risk_limit_preset_table(risk_limit_preset_id), hide_index=True, width="stretch")
    except Exception as exc:
        st.error(f"Scenario evaluation unavailable: {type(exc).__name__}: {exc}")


def _render_locked_oos_threshold_experiments(
    market_source: str,
    held_qty: int,
    settled_sellable_qty: int,
    purchasable_qty: int,
    max_t_ratio: float,
    max_single_trade_qty: int | None,
    risk_limit_preset_id: str | None,
    fee_profile_id: str | None,
    custom_fee_config: FeeConfig | None,
) -> None:
    trade_qty = _evaluation_trade_qty(market_source, held_qty, max_t_ratio, max_single_trade_qty, risk_limit_preset_id)
    fee_model = _fee_model_for_execution(market_source, False, fee_profile_id, custom_fee_config)
    try:
        _render_threshold_experiment_comparison(
            build_threshold_experiment_report(
                target_qty=held_qty,
                settled_sellable_qty=settled_sellable_qty,
                purchasable_qty=purchasable_qty,
                trade_qty=trade_qty,
                fee_model=fee_model,
            )
        )
    except Exception as exc:
        st.warning(f"Locked-OOS threshold experiments unavailable: {type(exc).__name__}: {exc}")


def _render_evaluation_report(
    market_source: str,
    held_qty: int,
    settled_sellable_qty: int,
    purchasable_qty: int,
    max_t_ratio: float,
    max_single_trade_qty: int | None,
    risk_limit_preset_id: str | None,
    fee_profile_id: str | None,
    custom_fee_config: FeeConfig | None,
) -> None:
    st.subheader("Scenario evaluation")
    st.caption(
        "Registered research comparison: no-trade baseline, simple S->B replay baseline, "
        "trigger-engine signal diagnostics, and locked OOS rows when available. This is not live-symbol performance evidence."
    )
    if held_qty <= 0:
        st.warning("Enter a positive target / held quantity to render scenario evaluation.")
    else:
        trade_qty = _evaluation_trade_qty(market_source, held_qty, max_t_ratio, max_single_trade_qty, risk_limit_preset_id)
        fee_model = _fee_model_for_execution(market_source, False, fee_profile_id, custom_fee_config)
        try:
            report = build_evaluation_report(
                scenario_names=tuple(DEFAULT_SCENARIOS) + tuple(DEFAULT_LOCKED_OOS_SCENARIOS),
                target_qty=held_qty,
                settled_sellable_qty=settled_sellable_qty,
                purchasable_qty=purchasable_qty,
                trade_qty=trade_qty,
                fee_model=fee_model,
            )
            table = _build_evaluation_table(report)
            st.dataframe(table, hide_index=True, width="stretch")
            st.caption(report.report_note)
            with st.expander("Evaluation assumptions"):
                st.write(f"Synthetic trade quantity: {trade_qty:,}")
                st.write("No-trade baseline is always shown as zero incremental trading PnL.")
                st.write("Simple S->B replay is an interpretable baseline, not a production strategy claim.")
                st.write("Trigger-engine rows are signal diagnostics only; fills and realized PnL are not inferred.")
                st.dataframe(_build_risk_limit_preset_table(risk_limit_preset_id), hide_index=True, width="stretch")
        except Exception as exc:
            st.error(f"Scenario evaluation unavailable: {type(exc).__name__}: {exc}")
        try:
            _render_threshold_experiment_comparison(
                build_threshold_experiment_report(
                    target_qty=held_qty,
                    settled_sellable_qty=settled_sellable_qty,
                    purchasable_qty=purchasable_qty,
                    trade_qty=trade_qty,
                    fee_model=fee_model,
                )
            )
        except Exception as exc:
            st.warning(f"Locked-OOS threshold experiments unavailable: {type(exc).__name__}: {exc}")
    try:
        audit_report = build_model_change_audit_report()
        _render_model_change_audit_report(audit_report)
    except Exception as exc:
        st.warning(f"Model-change audit unavailable: {type(exc).__name__}: {exc}")
    try:
        _render_model_audit_baseline_update_panel(build_model_audit_baseline_update_preview())
    except Exception as exc:
        st.warning(f"Audit baseline update review unavailable: {type(exc).__name__}: {exc}")


def _build_evaluation_table(report: EvaluationReport) -> pd.DataFrame:
    rows = []
    for item in report.scenarios:
        simple = item.simple_interpretable_baseline
        comparison = item.simple_vs_no_trade
        trigger = item.trigger_engine_signal
        rows.append(
            {
                "scenario": item.scenario,
                "dataset_split": item.dataset_split,
                "dataset_id": item.dataset_id,
                "dataset_locked": item.dataset_locked,
                "dataset_kind": item.dataset_kind,
                "bars": item.bar_count,
                "no_trade_excess_pnl": item.no_trade_baseline.get("excess_pnl_vs_hold", 0.0),
                "simple_excess_pnl": simple.get("excess_pnl_vs_hold", 0.0),
                "simple_closed_t_net_pnl": simple.get("closed_t_net_pnl", 0.0),
                "simple_trades": simple.get("trade_count", 0),
                "simple_unclosed_pair_rate": simple.get("unclosed_pair_rate", 0.0),
                "simple_vs_no_trade": comparison.get("strategy_excess_pnl", 0.0),
                "trigger_latest_action": trigger.latest_action,
                "trigger_count": trigger.trigger_count,
                "watch_count": trigger.watch_count,
                "no_trade_count": trigger.no_trade_count,
                "caveat": "split-labeled; signal-only; no fills or realized PnL inferred",
            }
        )
    return pd.DataFrame(rows)


def _evaluation_trade_qty(
    market_source: str,
    held_qty: int,
    max_t_ratio: float,
    max_single_trade_qty: int | None,
    risk_limit_preset_id: str | None = None,
) -> int:
    lot_size = 1 if market_source.startswith("Korea") else 100
    raw_qty = max_single_trade_qty if max_single_trade_qty is not None else int(held_qty * max_t_ratio)
    preset = risk_limit_preset(risk_limit_preset_id)
    risk_cap_qty = int(held_qty * min(preset.max_daily_turnover_ratio / 2.0, preset.max_same_day_capital_at_risk_ratio))
    raw_qty = min(raw_qty, risk_cap_qty)
    rounded = (max(0, raw_qty) // lot_size) * lot_size
    if rounded > 0:
        return rounded
    return min(held_qty, lot_size) if held_qty > 0 else lot_size
def _rules_for_market(
    market_source: str,
    max_t_ratio: float,
    max_single_trade_qty: int | None,
    risk_limit_preset_id: str | None = None,
) -> RulesConfig:
    if market_source.startswith("Korea"):
        base_rules = _make_rules_config(
            {
                "lot_size": 1,
                "minimum_order_qty": 1,
                "max_t_ratio": max_t_ratio,
                "max_single_trade_qty": max_single_trade_qty,
                "start_time": "09:15",
                "latest_open_time": "15:05",
                "force_restore_time": "15:20",
                "close_time": "15:30",
                "price_limit_pct": 0.30,
            }
        )
    else:
        base_rules = _make_rules_config({"max_t_ratio": max_t_ratio, "max_single_trade_qty": max_single_trade_qty})
    return rules_with_risk_limit_preset(base_rules, risk_limit_preset_id)
def _make_rules_config(values: dict) -> RulesConfig:
    supported_fields = getattr(RulesConfig, "__dataclass_fields__", {})
    if not supported_fields:
        return RulesConfig(**values)
    return RulesConfig(**{key: value for key, value in values.items() if key in supported_fields})


def _data_caption(market_source: str, symbol: str, bars) -> str:
    latest = bars[-1]
    if market_source.startswith("Korea"):
        return f"Yahoo Finance: {symbol}; latest minute {latest.ts}; price {latest.close:.2f} KRW."
    return f"Eastmoney: {symbol}; latest minute {latest.ts}; price {latest.close:.2f} RMB."


def _render_intent(intent: TradeIntent) -> None:
    label = ACTION_LABELS[intent.action_type]
    if intent.action_type in {ActionType.TRIGGER_SELL_TO_BUY, ActionType.TRIGGER_BUY_TO_SELL}:
        st.success(f"{label} | confidence {intent.confidence}")
    elif intent.action_type in {ActionType.MANAGE_OPEN_PAIR, ActionType.FORCE_CLOSE_OR_RESTORE}:
        st.warning(f"{label} | confidence {intent.confidence}")
    else:
        st.info(f"{label} | confidence {intent.confidence}")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Reference price", f"{intent.reference_price:.2f}")
    c2.metric("Suggested qty", f"{intent.suggested_qty}")
    c3.metric("Estimated net edge", f"{intent.estimated_net_edge:.2f}")
    c4.metric("Cost reduction/share", f"{intent.expected_cost_reduction_per_share:.4f}")
    st.write(f"Next action: {intent.next_action}")
    _render_list("Reasons", intent.reasons)
    _render_list("Blockers", intent.blockers)
    _render_list("Warnings", intent.warnings)


def _render_intent_compact(intent: TradeIntent) -> None:
    label = ACTION_LABELS[intent.action_type]
    if intent.action_type in {ActionType.TRIGGER_SELL_TO_BUY, ActionType.TRIGGER_BUY_TO_SELL}:
        st.success(label)
    elif intent.action_type in {ActionType.MANAGE_OPEN_PAIR, ActionType.FORCE_CLOSE_OR_RESTORE}:
        st.warning(label)
    else:
        st.info(label)
    col1, col2, col3 = st.columns(3)
    col1.metric("Confidence", f"{intent.confidence}")
    col2.metric("Suggested qty", f"{intent.suggested_qty}")
    col3.metric("Cost reduction/share", f"{intent.expected_cost_reduction_per_share:.4f}")
    st.markdown(f"**Next action:** {intent.next_action}")
    if intent.reasons:
        st.caption("Key reasons: " + "; ".join(intent.reasons[:2]))
    if intent.blockers:
        st.warning("Primary blocker: " + intent.blockers[0])


def _render_decision_summary(summary: DecisionSummary) -> None:
    st.subheader("Decision summary")
    top = st.columns(3)
    _render_summary_section(top[0], "Recommendation", summary.recommendation)
    _render_summary_section(top[1], "Invalidation", summary.invalidation)
    _render_summary_section(top[2], "Position impact", summary.position_impact)
    bottom = st.columns(2)
    _render_summary_section(bottom[0], "Evidence", summary.evidence)
    _render_summary_section(bottom[1], "Caveats", summary.caveats)


def _render_summary_section(column, title: str, rows: list[str]) -> None:
    with column:
        with st.container(border=True):
            st.markdown(f"**{title}**")
            for row in rows:
                st.write(row)

def _build_source_disclosure_table(disclosure: DataSourceDisclosure) -> pd.DataFrame:
    return pd.DataFrame(disclosure.as_table_rows())


def _status_strip_payload(disclosure: DataSourceDisclosure, report: DataQualityReport, intent: TradeIntent) -> dict[str, str]:
    actionable = intent.action_type in {ActionType.TRIGGER_SELL_TO_BUY, ActionType.TRIGGER_BUY_TO_SELL, ActionType.FORCE_CLOSE_OR_RESTORE}
    if report.status == "BAD":
        status = "BAD"
    elif actionable and not disclosure.broker_confirmed:
        status = "WARN"
    elif report.status in {"WARN", "UNKNOWN"} or not disclosure.broker_confirmed:
        status = "WARN"
    else:
        status = "OK"
    return {
        "data": disclosure.source_grade,
        "broker_confirmed": "Yes" if disclosure.broker_confirmed else "No",
        "latest_bar": report.latest_ts,
        "status": status,
        "bars": str(report.bar_count),
    }


def _should_expand_data_risk_details(disclosure: DataSourceDisclosure, report: DataQualityReport, intent: TradeIntent) -> bool:
    actionable = intent.action_type in {ActionType.TRIGGER_SELL_TO_BUY, ActionType.TRIGGER_BUY_TO_SELL, ActionType.FORCE_CLOSE_OR_RESTORE}
    return report.status == "BAD" or (actionable and not disclosure.broker_confirmed)


def _render_status_strip(disclosure: DataSourceDisclosure, report: DataQualityReport, intent: TradeIntent) -> None:
    payload = _status_strip_payload(disclosure, report, intent)
    message = (
        f"Data: {payload['data']} | Broker confirmed: {payload['broker_confirmed']} | "
        f"Latest bar: {payload['latest_bar']} | Bars: {payload['bars']} | Status: {payload['status']}"
    )
    if payload["status"] == "OK":
        st.success(message)
    elif payload["status"] == "BAD":
        st.error(message)
    else:
        st.warning(message)


def _render_data_risk_details(disclosure: DataSourceDisclosure, report: DataQualityReport, intent: TradeIntent) -> None:
    expanded = _should_expand_data_risk_details(disclosure, report, intent)
    with st.expander("Data source caveats", expanded=expanded):
        _render_data_source_disclosure(disclosure)
    with st.expander("Data quality details", expanded=expanded):
        _render_data_quality(report)


def _render_data_source_disclosure(disclosure: DataSourceDisclosure) -> None:
    st.warning(disclosure.summary())
    cols = st.columns(3)
    cols[0].metric("Source grade", disclosure.source_grade)
    cols[1].metric("Broker confirmed", "Yes" if disclosure.broker_confirmed else "No")
    cols[2].metric("Delay status", disclosure.delay_status)
    st.dataframe(_build_source_disclosure_table(disclosure), hide_index=True, width="stretch")
    st.caption("Live guidance remains decision support until broker-confirmed market data, holdings, and executions are checked.")

def _render_data_quality(report: DataQualityReport) -> None:
    message = f"{report.status}: {report.confidence_note}"
    if report.status == "OK":
        st.success(message)
    elif report.status == "BAD":
        st.error(message)
    else:
        st.warning(message)

    cols = st.columns(3)
    cols[0].metric("Bars", f"{report.bar_count}")
    cols[1].metric("Latest bar", report.latest_ts)
    cols[2].metric("Checks", f"{len(report.checks)}")

    with st.expander("Data quality details", expanded=report.status != "OK"):
        st.dataframe(
            pd.DataFrame([check.as_dict() for check in report.checks]),
            hide_index=True,
            width="stretch",
        )
        for caveat in report.caveats:
            st.warning(caveat)

def _render_market(
    bars,
    intent: TradeIntent,
    market_source: str,
    signal_markers: pd.DataFrame,
    show_chart_markers: bool = False,
    chart_df: pd.DataFrame | None = None,
) -> None:
    st.subheader("Intraday market")
    if market_source.startswith("Korea"):
        st.caption("Yahoo minute turnover is approximated from close * volume; use it as a prototype signal only.")
    df = _build_market_frame(bars)
    plot_df = chart_df if chart_df is not None else df
    _render_market_ratio_metrics(df, intent)
    _render_signal_summary(signal_markers)
    if chart_df is not None and len(chart_df) != len(df):
        st.caption(
            f"Chart shows full session context ({len(chart_df)} bars); model metrics and yellow marker use bars through {pd.Timestamp(df.iloc[-1]['time']):%H:%M} only."
        )
    _render_price_chart(plot_df, signal_markers, intent, show_markers=show_chart_markers)
    _render_ratio_chart(plot_df)
    _render_signal_detail(signal_markers)
    with st.expander("TradeIntent JSON"):
        st.json(intent.as_dict())


def _render_layers(intent: TradeIntent) -> None:
    st.subheader("Decision layers")
    st.caption("Read order: regime, price deviation, then inventory and capital constraints.")
    payload = intent.as_dict()
    col1, col2, col3 = st.columns(3)
    with col1:
        _render_regime_card(payload.get("regime_decision"))
    with col2:
        _render_deviation_card(payload.get("deviation_decision"))
    with col3:
        _render_inventory_card(payload.get("inventory_decision"))
    with st.expander("Raw layer JSON"):
        tabs = st.tabs(["Regime", "Deviation", "Inventory"])
        with tabs[0]:
            st.json(payload.get("regime_decision") or {})
        with tabs[1]:
            st.json(payload.get("deviation_decision") or {})
            with tabs[2]:
                st.json(payload.get("inventory_decision") or {})


def _get_replay_time_from_session(market_df: pd.DataFrame) -> pd.Timestamp | None:
    raw = st.session_state.get(_REPLAY_TIME_KEY)
    if not raw:
        return None
    selected = pd.to_datetime(raw, errors="coerce")
    if pd.isna(selected):
        st.session_state.pop(_REPLAY_TIME_KEY, None)
        return None
    return _nearest_closed_minute(pd.Timestamp(selected), market_df)


def _bars_until_replay_time(bars, replay_time: pd.Timestamp):
    selected = pd.Timestamp(replay_time)
    replay_bars = [bar for bar in bars if pd.Timestamp(bar.ts) <= selected]
    return replay_bars or bars[:1]


def _nearest_closed_minute(selected: pd.Timestamp, market_df: pd.DataFrame) -> pd.Timestamp | None:
    if market_df.empty:
        return None
    times = list(pd.to_datetime(market_df["time"]))
    nearest = min(times, key=lambda value: abs(pd.Timestamp(value) - selected))
    return pd.Timestamp(nearest)


def _render_replay_mode_banner(replay_time: pd.Timestamp | None) -> None:
    if replay_time is None:
        st.caption("Live mode: showing the latest closed minute.")
        return
    st.info(
        f"Replay mode: showing model state as of selected closed minute {replay_time:%H:%M}. "
        "No future bars after this time are used."
    )
    if st.button("Back to Live", key="back_to_live"):
        st.session_state.pop(_REPLAY_TIME_KEY, None)
        st.session_state[_PRICE_CHART_WIDGET_VERSION_KEY] = int(st.session_state.get(_PRICE_CHART_WIDGET_VERSION_KEY, 0)) + 1
        st.rerun()


def _build_market_frame(bars) -> pd.DataFrame:
    vwap_values = [_safe_vwap(bars[: index + 1]) for index in range(len(bars))]
    day_open = bars[0].open
    rows = []
    for bar, vwap in zip(bars, vwap_values):
        rows.append(
            {
                "time": bar.ts,
                "close": bar.close,
                "vwap": vwap,
                "day_open": day_open,
                "close_vs_open_pct": (bar.close / day_open - 1.0) * 100,
                "vwap_deviation_pct": (bar.close / vwap - 1.0) * 100 if vwap else 0.0,
                "volume": bar.volume,
            }
        )
    return pd.DataFrame(rows)


def _render_market_ratio_metrics(df: pd.DataFrame, intent: TradeIntent) -> None:
    latest = df.iloc[-1]
    high = float(df["close"].max())
    low = float(df["close"].min())
    open_price = float(df.iloc[0]["day_open"])
    amplitude_pct = (high / low - 1.0) * 100 if low else 0.0
    session_date = pd.Timestamp(latest["time"]).date()

    cols = st.columns(4)
    cols[0].metric("Close vs open", _fmt_pct(float(latest["close_vs_open_pct"])))
    cols[1].metric("VWAP deviation", _fmt_pct(float(latest["vwap_deviation_pct"])))
    cols[2].metric("Intraday amplitude", _fmt_pct(amplitude_pct))
    cols[3].metric("Suggested ratio", _fmt_pct_unsigned(intent.suggested_ratio * 100), help="Suggested qty / target qty")
    st.caption(f"Session {session_date}; bars {len(df)}; latest {latest['close']:.2f}; open {open_price:.2f}; VWAP {latest['vwap']:.2f}.")


def _render_signal_summary(signal_markers: pd.DataFrame) -> None:
    if signal_markers.empty:
        st.caption("No SB/BS lifecycle opportunities in the scanned minutes.")
        return
    if "state" in signal_markers.columns:
        counts = signal_markers["state"].value_counts().to_dict()
        st.caption(
            "Opportunity lifecycle scan: "
            f"watch {counts.get('WATCH', 0)}, probe {counts.get('PROBE', 0)}, add {counts.get('ADD', 0)}, "
            f"confirm {counts.get('CONFIRM', 0)}, close-ready {counts.get('CLOSE_READY', 0)}, "
            f"forced {counts.get('FORCED_DECISION', 0)}, expired {counts.get('EXPIRED', 0)}, blocked {counts.get('BLOCKED', 0)}. "
            "Signal-only; no fills or realized PnL are inferred."
        )
        return
    counts = signal_markers["signal"].value_counts().to_dict()
    st.caption(
        "Signal scan: "
        f"SB {counts.get('SB', 0)}, BS {counts.get('BS', 0)}, "
        f"Watch S->B {counts.get('Watch S->B', 0)}, Watch B->S {counts.get('Watch B->S', 0)}."
    )


def _render_price_chart(df: pd.DataFrame, signal_markers: pd.DataFrame, intent: TradeIntent, show_markers: bool = False) -> None:
    chart_df = df[["time", "close", "vwap"]].melt("time", var_name="line", value_name="price")
    chart_df["line"] = chart_df["line"].map({"close": "Price", "vwap": "VWAP"})
    base = (
        alt.Chart(chart_df)
        .mark_line(strokeWidth=2)
        .encode(
            x=alt.X("time:T", title="Time"),
            y=alt.Y("price:Q", title="Price", scale=alt.Scale(zero=False)),
            color=alt.Color("line:N", title="", scale=alt.Scale(domain=["Price", "VWAP"], range=["#2563eb", "#d97706"])),
            tooltip=[
                alt.Tooltip("time:T", title="Time", format="%H:%M"),
                alt.Tooltip("line:N", title="Line"),
                alt.Tooltip("price:Q", title="Price", format=",.2f"),
            ],
        )
        .properties(height=260)
    )
    current_marker = pd.DataFrame([_current_intent_marker_row(intent, df)])
    current_rule = (
        alt.Chart(current_marker)
        .mark_rule(color="#facc15", strokeDash=[6, 4], strokeWidth=2)
        .encode(
            x=alt.X("time:T", title="Time"),
            tooltip=[
                alt.Tooltip("time:T", title="Latest closed minute", format="%H:%M"),
                alt.Tooltip("action:N", title="Current action"),
                alt.Tooltip("price:Q", title="Reference price", format=",.2f"),
                alt.Tooltip("confidence:Q", title="Confidence"),
                alt.Tooltip("suggested_qty:Q", title="Qty", format=","),
                alt.Tooltip("suggested_ratio_pct:Q", title="Suggested ratio %", format=".2f"),
                alt.Tooltip("vwap_deviation_pct:Q", title="VWAP dev %", format=".3f"),
                alt.Tooltip("net_edge:Q", title="Net edge", format=",.2f"),
                alt.Tooltip("reason:N", title="Reason"),
                alt.Tooltip("note:N", title="Caveat"),
            ],
        )
    )
    current_point = (
        alt.Chart(current_marker)
        .mark_point(filled=True, size=260, color="#facc15", stroke="#111827", strokeWidth=1.5)
        .encode(
            x=alt.X("time:T", title="Time"),
            y=alt.Y("price:Q", title="Price", scale=alt.Scale(zero=False)),
            shape=alt.Shape("side:N", title="Current side", scale=alt.Scale(domain=["S->B", "B->S", "None"], range=["triangle-down", "triangle-up", "circle"])),
            tooltip=[
                alt.Tooltip("time:T", title="Latest closed minute", format="%H:%M"),
                alt.Tooltip("action:N", title="Current action"),
                alt.Tooltip("price:Q", title="Reference price", format=",.2f"),
                alt.Tooltip("confidence:Q", title="Confidence"),
                alt.Tooltip("suggested_qty:Q", title="Qty", format=","),
                alt.Tooltip("reason:N", title="Reason"),
            ],
        )
    )
    current_label = (
        alt.Chart(current_marker)
        .mark_text(dy=-24, align="right", dx=-8, fontWeight="bold", fontSize=13, color="#facc15")
        .encode(
            x="time:T",
            y="price:Q",
            text="label:N",
        )
    )
    selection_df = df[["time", "close"]].copy()
    selection_df["time_key"] = pd.to_datetime(selection_df["time"]).dt.strftime("%Y-%m-%d %H:%M:%S")
    minute_selection = alt.selection_point(name="minute_select", fields=["time_key"], nearest=True, on="click", empty=False)
    click_rules = (
        alt.Chart(selection_df)
        .mark_rule(strokeWidth=12, opacity=0.001)
        .encode(
            x=alt.X("time:T", title="Time"),
            tooltip=[
                alt.Tooltip("time:T", title="Click to replay at", format="%H:%M"),
                alt.Tooltip("close:Q", title="Close", format=",.2f"),
            ],
        )
        .add_params(minute_selection)
    )
    chart = base + current_rule + current_point + current_label + click_rules
    if show_markers and not signal_markers.empty:
        has_state = "state" in signal_markers.columns
        visible_markers = signal_markers if has_state else signal_markers[signal_markers["level"] == "Trigger"]
        if visible_markers.empty:
            visible_markers = signal_markers
        color_encoding = (
            alt.Color(
                "state:N",
                title="State",
                scale=alt.Scale(
                    domain=["WATCH", "PROBE", "ADD", "CONFIRM", "CLOSE_READY", "FORCED_DECISION", "EXPIRED", "BLOCKED"],
                    range=["#64748b", "#2563eb", "#7c3aed", "#16a34a", "#22c55e", "#f59e0b", "#a16207", "#dc2626"],
                ),
            )
            if has_state
            else alt.Color(
                "signal:N",
                title="Signal",
                scale=alt.Scale(domain=["SB", "BS", "Watch S->B", "Watch B->S"], range=["#dc2626", "#16a34a", "#ea580c", "#65a30d"]),
            )
        )
        label_color = (
            alt.Color(
                "state:N",
                legend=None,
                scale=alt.Scale(
                    domain=["WATCH", "PROBE", "ADD", "CONFIRM", "CLOSE_READY", "FORCED_DECISION", "EXPIRED", "BLOCKED"],
                    range=["#64748b", "#2563eb", "#7c3aed", "#16a34a", "#22c55e", "#f59e0b", "#a16207", "#dc2626"],
                ),
            )
            if has_state
            else alt.Color("signal:N", legend=None, scale=alt.Scale(domain=["SB", "BS"], range=["#dc2626", "#16a34a"]))
        )
        tooltip = [
            alt.Tooltip("time:T", title="Time", format="%H:%M"),
            alt.Tooltip("action:N", title="Action"),
            alt.Tooltip("price:Q", title="Price", format=",.2f"),
            alt.Tooltip("confidence:Q", title="Confidence"),
            alt.Tooltip("suggested_qty:Q", title="Qty", format=","),
            alt.Tooltip("vwap_deviation_pct:Q", title="VWAP dev %", format=".3f"),
            alt.Tooltip("anchor_type:N", title="Anchor"),
            alt.Tooltip("exhaustion_score:Q", title="Exhaustion", format=".1f"),
            alt.Tooltip("liquidity_score:Q", title="Liquidity", format=".1f"),
            alt.Tooltip("net_edge:Q", title="Net edge", format=",.2f"),
            alt.Tooltip("target_price:Q", title="Target", format=",.2f"),
            alt.Tooltip("invalidation_price:Q", title="Invalidation", format=",.2f"),
            alt.Tooltip("reason_codes:N", title="Reason codes"),
            alt.Tooltip("blocked_reasons:N", title="Blocked reasons"),
            alt.Tooltip("why_not_earlier:N", title="Why not earlier"),
            alt.Tooltip("reason:N", title="Reason"),
        ]
        if has_state:
            tooltip.insert(1, alt.Tooltip("state:N", title="State"))
            tooltip.append(alt.Tooltip("note:N", title="Caveat"))
        points = (
            alt.Chart(visible_markers)
            .mark_point(filled=True, opacity=0.9)
            .encode(
                x=alt.X("time:T", title="Time"),
                y=alt.Y("price:Q", title="Price", scale=alt.Scale(zero=False)),
                color=color_encoding,
                shape=alt.Shape("side:N", title="Side", scale=alt.Scale(domain=["S->B", "B->S"], range=["triangle-down", "triangle-up"])),
                size=alt.Size("level:N", title="Level", scale=alt.Scale(domain=["Watch", "Probe", "Add", "Confirm", "Lifecycle"], range=[70, 170, 210, 230, 150])),
                tooltip=tooltip,
            )
        )
        trigger_labels = visible_markers if has_state else visible_markers[visible_markers["level"] == "Trigger"]
        labels = (
            alt.Chart(trigger_labels)
            .mark_text(dy=-16, fontWeight="bold", fontSize=13)
            .encode(
                x="time:T",
                y="price:Q",
                text="state:N" if has_state else "signal:N",
                color=label_color,
            )
        )
        chart = chart + points + labels
    chart_event = st.altair_chart(
        chart,
        width="stretch",
        key=_price_chart_widget_key(),
        on_select="rerun",
        selection_mode=["minute_select"],
    )
    _update_replay_time_from_chart_event(chart_event, df)


def _render_signal_detail(signal_markers: pd.DataFrame) -> None:
    if signal_markers.empty:
        return
    detail = signal_markers.copy()
    detail["time"] = detail["time"].dt.strftime("%H:%M")
    detail["vwap_deviation"] = detail["vwap_deviation_pct"].map(lambda value: f"{value:+.3f}%")
    detail["edge"] = detail["net_edge"].map(lambda value: f"{value:,.2f}")
    if "exhaustion_score" in detail.columns:
        detail["exhaustion"] = detail["exhaustion_score"].map(lambda value: f"{float(value):.1f}")
    if "liquidity_score" in detail.columns:
        detail["liquidity"] = detail["liquidity_score"].map(lambda value: f"{float(value):.1f}")
    detail = detail.rename(
        columns={
            "action": "action",
            "price": "price",
            "confidence": "confidence",
            "suggested_qty": "suggested_qty",
            "reason": "reason",
        }
    )
    columns = [
        column
        for column in [
            "time",
            "state",
            "signal",
            "action",
            "price",
            "confidence",
            "suggested_qty",
            "vwap_deviation",
            "anchor_type",
            "deviation_score",
            "exhaustion",
            "liquidity",
            "edge_after_cost",
            "target_price",
            "invalidation_price",
            "inventory_before",
            "inventory_after_if_executed",
            "reason_codes",
            "blocked_reasons",
            "why_not_earlier",
            "edge",
            "reason",
            "note",
        ]
        if column in detail.columns
    ]
    with st.expander("Signal details"):
        st.dataframe(
            detail[columns],
            hide_index=True,
            width="stretch",
        )



def _price_chart_widget_key() -> str:
    version = int(st.session_state.get(_PRICE_CHART_WIDGET_VERSION_KEY, 0))
    return f"intraday_price_chart_v2_{version}"


def _update_replay_time_from_chart_event(chart_event, market_df: pd.DataFrame) -> None:
    selected_time = _selected_time_from_chart_event(chart_event)
    if selected_time is None:
        return
    replay_time = _nearest_closed_minute(selected_time, market_df)
    if replay_time is None:
        return
    replay_time_text = replay_time.isoformat()
    if st.session_state.get(_REPLAY_TIME_KEY) == replay_time_text:
        return
    st.session_state[_REPLAY_TIME_KEY] = replay_time_text
    st.rerun()


def _selected_time_from_chart_event(chart_event) -> pd.Timestamp | None:
    payload = _chart_selection_payload(chart_event)
    candidate = _selection_time_candidate(payload)
    if candidate is None:
        return None
    if isinstance(candidate, (int, float)):
        if candidate > 1_000_000_000_000:
            selected = pd.to_datetime(candidate, unit="ms", errors="coerce")
        else:
            selected = pd.to_datetime(candidate, errors="coerce")
    else:
        selected = pd.to_datetime(candidate, errors="coerce")
    if pd.isna(selected):
        return None
    return pd.Timestamp(selected)


def _chart_selection_payload(chart_event):
    if chart_event is None:
        return None
    selection = getattr(chart_event, "selection", None)
    if selection is None and isinstance(chart_event, dict):
        selection = chart_event.get("selection")
    if selection is None:
        return None
    payload = getattr(selection, "minute_select", None)
    if payload is None and isinstance(selection, dict):
        payload = selection.get("minute_select")
    return payload


def _selection_time_candidate(payload):
    if payload is None:
        return None
    if isinstance(payload, (list, tuple)):
        if not payload:
            return None
        return _selection_time_candidate(payload[0])
    if isinstance(payload, dict):
        if "time_key" in payload:
            value = payload["time_key"]
            if isinstance(value, (list, tuple)):
                return value[0] if value else None
            return value
        if "time" in payload:
            value = payload["time"]
            if isinstance(value, (list, tuple)):
                return value[0] if value else None
            return value
        for value in payload.values():
            candidate = _selection_time_candidate(value)
            if candidate is not None:
                return candidate
        return None
    return payload
def _render_ratio_chart(df: pd.DataFrame) -> None:
    ratio_df = df[["time", "close_vs_open_pct", "vwap_deviation_pct"]].melt("time", var_name="ratio", value_name="pct")
    label_map = {"close_vs_open_pct": "Close vs open", "vwap_deviation_pct": "VWAP deviation"}
    ratio_df["ratio"] = ratio_df["ratio"].map(label_map)
    line = (
        alt.Chart(ratio_df)
        .mark_line(strokeWidth=2)
        .encode(
            x=alt.X("time:T", title="Time"),
            y=alt.Y("pct:Q", title="Percent", axis=alt.Axis(format=".2f")),
            color=alt.Color("ratio:N", title="", scale=alt.Scale(domain=["Close vs open", "VWAP deviation"], range=["#16a34a", "#ca8a04"])),
            tooltip=[
                alt.Tooltip("time:T", title="Time", format="%H:%M"),
                alt.Tooltip("ratio:N", title="Ratio"),
                alt.Tooltip("pct:Q", title="%", format=".3f"),
            ],
        )
    )
    zero = alt.Chart(pd.DataFrame({"pct": [0]})).mark_rule(color="#64748b").encode(y="pct:Q")
    st.altair_chart((line + zero).properties(height=220), width="stretch")


def _render_regime_card(regime: dict | None) -> None:
    with st.container(border=True):
        st.markdown("**1. Regime**")
        if not regime:
            st.info("Not calculated.")
            return
        regime_type = regime.get("regime_type", "")
        blockers = regime.get("blockers") or []
        status = "Blocked" if blockers else "Passed"
        st.metric(status, REGIME_LABELS.get(regime_type, regime_type), delta=f"confidence {regime.get('confidence', 0)}")
        st.write(f"S->B: {_yes_no(regime.get('allow_sell_to_buy'))} | B->S: {_yes_no(regime.get('allow_buy_to_sell'))}")
        _render_compact_rows("Reasons", regime.get("reasons") or ["No reason returned."])
        _render_compact_rows("Blockers", blockers)


def _render_deviation_card(deviation: dict | None) -> None:
    with st.container(border=True):
        st.markdown("**2. Price deviation**")
        if not deviation:
            st.info("Not calculated because regime or deviation did not pass.")
            return
        side = deviation.get("side_candidate", "NONE")
        score = float(deviation.get("deviation_score") or 0.0)
        st.metric("Candidate", SIDE_LABELS.get(side, side), delta=f"score {score:.2f}x")
        c1, c2 = st.columns(2)
        c1.metric("Net edge", f"{float(deviation.get('net_edge_after_fee') or 0):,.2f}")
        c2.metric("Max wait", f"{int(deviation.get('max_wait_minutes') or 0)} min")
        if deviation.get("expected_reversion_zone") is not None:
            st.write(f"Reversion zone: {float(deviation['expected_reversion_zone']):,.2f}")
        if deviation.get("invalidation_price") is not None:
            st.write(f"Invalidation: {float(deviation['invalidation_price']):,.2f}")
        _render_compact_rows("Reasons", deviation.get("reasons") or [])
        _render_compact_rows("Warnings", deviation.get("warnings") or [])


def _render_inventory_card(inventory: dict | None) -> None:
    with st.container(border=True):
        st.markdown("**3. Inventory**")
        if not inventory:
            st.info("Not calculated because the prior layers did not produce an executable side.")
            return
        executable = bool(inventory.get("executable"))
        status = "Executable" if executable else "Not executable"
        qty = int(inventory.get("suggested_qty") or 0)
        st.metric(status, f"{qty:,} shares", delta=_fmt_pct(float(inventory.get("suggested_ratio") or 0) * 100))
        c1, c2 = st.columns(2)
        c1.metric("Capital required", f"{float(inventory.get('capital_required') or 0):,.2f}")
        c2.metric("Sellable after trade", f"{int(inventory.get('sellable_after_trade') or 0):,} shares")
        delta = int(inventory.get("inventory_delta_after_trade") or 0)
        st.write(f"Inventory delta: {delta:+,} shares")
        _render_compact_rows("Reasons", inventory.get("reasons") or [])
        _render_compact_rows("Blockers", inventory.get("blockers") or [])


def _render_compact_rows(title: str, rows: list[str]) -> None:
    if not rows:
        return
    st.write(f"{title}:")
    for row in rows[:4]:
        st.markdown(f"- {row}")
    if len(rows) > 4:
        st.caption(f"{len(rows) - 4} more rows in raw JSON.")


def _render_list(title: str, rows: list[str]) -> None:
    if not rows:
        return
    st.write(f"{title}:")
    for row in rows:
        st.markdown(f"- {row}")


def _yes_no(value: bool | None) -> str:
    return "yes" if value else "no"


def _fmt_pct(value: float) -> str:
    return f"{value:+.2f}%"


def _fmt_pct_unsigned(value: float) -> str:
    return f"{value:.2f}%"


def _safe_vwap(bars) -> float:
    volume = sum(bar.volume for bar in bars)
    if volume <= 0:
        return bars[-1].close
    return sum(bar.amount for bar in bars) / volume


if __name__ == "__main__":
    main()




























