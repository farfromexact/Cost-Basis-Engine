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

from app.ui_text import LANGUAGE_LABELS, SUPPORTED_LANGUAGES, normalize_lang, t
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
from app.session_ledger import SessionLedgerSummary, build_session_ledger_summary
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


_ACTION_LABEL_KEYS = {
    ActionType.NO_TRADE: "action.no_trade",
    ActionType.WATCH_SELL_TO_BUY: "action.watch_sb",
    ActionType.TRIGGER_SELL_TO_BUY: "action.trigger_sb",
    ActionType.WATCH_BUY_TO_SELL: "action.watch_bs",
    ActionType.TRIGGER_BUY_TO_SELL: "action.trigger_bs",
    ActionType.MANAGE_OPEN_PAIR: "action.manage_pair",
    ActionType.FORCE_CLOSE_OR_RESTORE: "action.force_close",
}

_REGIME_LABEL_KEYS = {
    "MEAN_REVERTING": "regime.mean_reverting",
    "TREND_UP": "regime.trend_up",
    "TREND_DOWN": "regime.trend_down",
    "EVENT_DRIVEN": "regime.event_driven",
    "ILLIQUID": "regime.illiquid",
    "LIMIT_RISK": "regime.limit_risk",
    "LATE_SESSION": "regime.late_session",
    "NO_TRADE": "regime.no_trade",
}

_SIDE_LABEL_KEYS = {
    "SELL_TO_BUY": "side.sb",
    "BUY_TO_SELL": "side.bs",
    "NONE": "side.none",
}


_MARKET_A_SHARE = "A-share / Eastmoney"
_MARKET_KOREA = "Korea / Yahoo Finance"
_MARKET_US = "US / Yahoo Finance"
_PAGE_INTRADAY = "page.intraday"
_PAGE_EXECUTION = "page.execution"
_PAGE_RESEARCH = "page.research"
_OPEN_PAIR_SIDE_LABELS = {
    "None": "na",
    "SB": "side.sb",
    "BS": "side.bs",
}
_REPLAY_TIME_KEY = "intraday_replay_time"
_PRICE_CHART_WIDGET_VERSION_KEY = "intraday_price_chart_widget_version"
_UI_LANGUAGE_KEY = "ui_language"


def _current_lang() -> str:
    session_state = getattr(st, "session_state", {})
    return normalize_lang(session_state.get(_UI_LANGUAGE_KEY) if hasattr(session_state, "get") else None)


def _L(key: str, **kwargs) -> str:
    return t(_current_lang(), key, **kwargs)


def _action_label(action_type: ActionType) -> str:
    return _L(_ACTION_LABEL_KEYS[action_type])


def _regime_label(regime_type: str) -> str:
    return _L(_REGIME_LABEL_KEYS.get(regime_type, "na"))


def _side_label(side: str) -> str:
    return _L(_SIDE_LABEL_KEYS.get(side, "side.none"))


def _open_pair_side_label(side: str) -> str:
    return _L(_OPEN_PAIR_SIDE_LABELS.get(side, "na"))


def main() -> None:
    current_lang = _current_lang()
    st.set_page_config(page_title=t(current_lang, "page_title"), page_icon="chart_with_downwards_trend", layout="wide")
    st.markdown(
        """
        <style>
        .block-container { padding-top: 1rem; }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.title(_L("app.title"))
    st.caption(_L("app.subtitle"))
    state_path = default_position_state_path()

    with st.sidebar:
        selected_lang = st.selectbox(
            _L("sidebar.language"),
            options=SUPPORTED_LANGUAGES,
            index=list(SUPPORTED_LANGUAGES).index(_current_lang()),
            format_func=lambda value: LANGUAGE_LABELS.get(value, value),
        )
        st.session_state[_UI_LANGUAGE_KEY] = selected_lang
        st.header(_L("sidebar.inputs"))
        persist_position_state = st.checkbox(
            _L("sidebar.persist_state"),
            value=False,
            help=_L("sidebar.persist_state_help"),
        )
        if persist_position_state:
            saved_state = _load_position_state_for_dashboard(state_path)
            default_state = saved_state or PositionSnapshot()
            st.caption(_L("state.file", path=state_path))
        else:
            saved_state = None
            default_state = PositionSnapshot()
            st.caption(_L("sidebar.state_idle"))
        market_options = [_MARKET_A_SHARE, _MARKET_KOREA, _MARKET_US]
        saved_market = default_state.market_source if default_state.market_source in market_options else _MARKET_A_SHARE
        market_source = st.selectbox(_L("sidebar.market_source"), market_options, index=market_options.index(saved_market))
        is_korea = _is_korea_market(market_source)
        is_us = _is_us_market(market_source)
        source_matches_saved = default_state.market_source == market_source
        fallback_symbol = "005930.KS" if is_korea else ("AAPL" if is_us else "603236")
        default_symbol = default_state.symbol if source_matches_saved and default_state.symbol else fallback_symbol
        symbol_help = _L("sidebar.symbol_help_kr") if is_korea else (_L("sidebar.symbol_help_us") if is_us else _L("sidebar.symbol_help_cn"))
        qty_step = _lot_size_for_market(market_source)
        default_held_qty = int(default_state.held_qty) if source_matches_saved else (1000 if is_korea else (100 if is_us else 151400))
        default_purchasable_qty = int(default_state.purchasable_qty) if source_matches_saved else (100 if is_korea else (10 if is_us else 15100))

        symbol_key = "kr" if is_korea else ("us" if is_us else "cn")
        symbol = st.text_input(_L("sidebar.symbol"), value=default_symbol, help=symbol_help, key=f"symbol_{symbol_key}")
        held_qty = st.number_input(_L("sidebar.held_qty"), min_value=0, value=default_held_qty, step=qty_step)
        purchasable_qty = st.number_input(_L("sidebar.purchasable_qty"), min_value=0, value=default_purchasable_qty, step=qty_step)
        compact_mode = st.checkbox(_L("sidebar.compact_mode"), value=False, help=_L("sidebar.compact_mode_help"))
        show_chart_markers = st.checkbox(
            _L("sidebar.show_chart_markers"),
            value=False,
            help=_L("sidebar.show_chart_markers_help"),
        )

        with st.expander(_L("sidebar.advanced"), expanded=False):
            default_settled_qty = int(default_state.settled_sellable_qty) if source_matches_saved else int(held_qty)
            default_max_t_ratio = float(default_state.max_t_ratio) if source_matches_saved else 0.05
            default_max_single_trade_qty = int(default_state.max_single_trade_qty or 0) if source_matches_saved else 0
            default_open_pair_side = default_state.open_pair_side if source_matches_saved and default_state.open_pair_side in {"SB", "BS"} else "None"
            default_open_pair_price = float(default_state.open_pair_price or 0.0) if source_matches_saved else 0.0
            default_open_pair_qty = int(default_state.open_pair_qty or 0) if source_matches_saved else 0

            settled_sellable_qty = st.number_input(_L("sidebar.settled_sellable"), min_value=0, value=default_settled_qty, step=qty_step)
            max_t_ratio = st.slider(_L("sidebar.max_t_ratio"), min_value=0.01, max_value=0.30, value=default_max_t_ratio, step=0.01)
            max_single_trade_qty = st.number_input(_L("sidebar.max_single_trade_qty"), min_value=0, value=default_max_single_trade_qty, step=qty_step)
            risk_options = list(risk_limit_preset_ids())
            saved_risk_preset = default_state.risk_limit_preset_id if source_matches_saved else DEFAULT_RISK_LIMIT_PRESET_ID
            if saved_risk_preset not in risk_options:
                saved_risk_preset = DEFAULT_RISK_LIMIT_PRESET_ID
            risk_limit_preset_id = st.selectbox(_L("sidebar.risk_preset"), risk_options, index=risk_options.index(saved_risk_preset), format_func=risk_limit_label)
            st.caption(risk_limit_description(risk_limit_preset_id))

            st.subheader(_L("sidebar.fees"))
            fee_options = fee_profile_choices(market_source)
            default_fee_profile = _dashboard_fee_profile_id(default_state, market_source, source_matches_saved)
            if default_fee_profile not in fee_options:
                fee_options.append(default_fee_profile)
            fee_profile_id = st.selectbox(
                _L("sidebar.fee_profile"),
                fee_options,
                index=fee_options.index(default_fee_profile),
                format_func=fee_profile_label,
                help=_L("sidebar.fee_help"),
            )
            custom_fee_config = _custom_fee_config_from_sidebar(FeeConfig(market=_fee_market_key(market_source))) if fee_profile_id == CUSTOM_FEE_PROFILE_ID else None
            st.caption(fee_profile_description(fee_profile_id))
            if fee_profile_id == ZERO_FEE_PROFILE_ID:
                st.warning(_L("sidebar.zero_fee_warning"))
            ignore_fees = fee_profile_id == ZERO_FEE_PROFILE_ID
            marker_cooldown_minutes = st.number_input(_L("sidebar.marker_cooldown"), min_value=1, value=10, step=1)

        st.subheader(_L("sidebar.open_pair"))
        open_pair_side = st.selectbox(
            _L("sidebar.open_pair_side"),
            ["None", "SB", "BS"],
            index=["None", "SB", "BS"].index(default_open_pair_side),
            format_func=_open_pair_side_label,
        )
        open_pair_price = st.number_input(_L("sidebar.open_pair_price"), min_value=0.0, value=default_open_pair_price, step=0.01)
        open_pair_qty = st.number_input(_L("sidebar.open_pair_qty"), min_value=0, value=default_open_pair_qty, step=qty_step)
        st.divider()
        dashboard_page = st.radio(
            _L("sidebar.page"),
            [_PAGE_INTRADAY, _PAGE_EXECUTION, _PAGE_RESEARCH],
            format_func=_L,
            index=0,
            help=_L("sidebar.page_help"),
        )
        auto_refresh = st.checkbox(_L("sidebar.auto_refresh"), value=False)
        refresh_seconds = st.number_input(_L("sidebar.refresh_interval"), min_value=10, value=60, step=10)
    if not symbol.strip():
        st.warning(_L("sidebar.enter_symbol"))
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
        st.error(_L("status.fetch_error", error=type(exc).__name__, detail=exc))
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
    st.subheader(_L("panel.trading_decision"))
    _render_intent_compact(display_intent)
    if not compact_mode:
        _render_decision_summary(build_decision_summary(display_intent, lang=_current_lang()))
    source_disclosure = build_data_source_disclosure(market_source)
    data_quality_now = display_bars[-1].ts if replay_time is not None else datetime.now()
    data_quality_report = build_data_quality_report(display_bars, market_source=market_source, now=data_quality_now)
    _render_status_strip(source_disclosure, data_quality_report, display_intent)
    st.caption(_data_caption(market_source, normalized_symbol, display_bars))
    _render_replay_mode_banner(replay_time)
    if dashboard_page == _PAGE_INTRADAY:
        st.caption(_L("status.execution_note"))
        st.subheader(_L("panel.intraday_market"))
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
        st.subheader(_L("panel.execution_review"))
        st.caption(
            _L("panel.execution_caption")
        )
        if replay_time is not None:
            st.caption(_L("status.execution_replay_note"))
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
            broker_fills=broker_fills,
        )
        session_ledger = build_session_ledger_summary(session_closeout)
        _render_pre_trade_order_ticket_panel(ticket)
        _render_execution_sensitivity_panel(sensitivity_report)
        _render_post_trade_review_panel(post_trade_review)
        _render_live_session_risk_usage_panel(live_session_risk)
        _render_session_closeout_panel(session_closeout)
        _render_session_ledger_panel(session_ledger)
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
        ActionType.WATCH_SELL_TO_BUY: (_L("action.watch_sb"), _L("chart.level_watch"), _L("side.sb")),
        ActionType.TRIGGER_SELL_TO_BUY: (_L("action.trigger_sb"), _L("chart.level_trigger"), _L("side.sb")),
        ActionType.WATCH_BUY_TO_SELL: (_L("action.watch_bs"), _L("chart.level_watch"), _L("side.bs")),
        ActionType.TRIGGER_BUY_TO_SELL: (_L("action.trigger_bs"), _L("chart.level_trigger"), _L("side.bs")),
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
        "action": _action_label(action),
        "confidence": intent.confidence,
        "suggested_qty": intent.suggested_qty,
        "vwap_deviation_pct": (feature.vwap_deviation * 100) if feature else 0.0,
        "net_edge": intent.estimated_net_edge,
        "reason": "; ".join(intent.reasons[:2]) if intent.reasons else intent.next_action,
    }


def _current_intent_marker_row(intent: TradeIntent, market_df: pd.DataFrame) -> dict:
    latest = market_df.iloc[-1]
    feature = intent.feature_snapshot
    action_label = _action_label(intent.action_type)
    reason_parts = list(intent.reasons[:2]) if intent.reasons else []
    if not reason_parts and intent.blockers:
        reason_parts = list(intent.blockers[:2])
    reason = "; ".join(reason_parts) if reason_parts else intent.next_action
    return {
        "time": pd.to_datetime(intent.timestamp or latest["time"]),
        "price": float(intent.reference_price or latest["close"]),
        "label": _L("chart.current_label", action=action_label),
        "action": action_label,
        "side": _side_label(intent.side.value),
        "confidence": intent.confidence,
        "suggested_qty": intent.suggested_qty,
        "suggested_ratio_pct": intent.suggested_ratio * 100,
        "vwap_deviation_pct": (feature.vwap_deviation * 100) if feature else float(latest["vwap_deviation_pct"]),
        "net_edge": intent.estimated_net_edge,
        "reason": reason,
        "note": _L("chart.current_note"),
    }


def _normalize_symbol(market_source: str, symbol: str) -> str:
    if _is_yahoo_market(market_source):
        return normalize_yahoo_symbol(symbol)
    return symbol


def _fetch_bars(market_source: str, symbol: str):
    if _is_yahoo_market(market_source):
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
        st.sidebar.warning(_L("sidebar.persist_state_failed", error=exc))

def _build_execution_sensitivity_table(report: ExecutionSensitivityReport) -> pd.DataFrame:
    return pd.DataFrame([band.as_dict() for band in report.bands])


def _render_execution_sensitivity_panel(report: ExecutionSensitivityReport) -> None:
    st.subheader(_L("panel.execution_quality"))
    if report.status == "OK":
        st.success(report.summary)
    elif report.status == "WARN":
        st.warning(report.summary)
    elif report.status == "BLOCKED":
        st.error(report.summary)
    else:
        st.info(report.summary)
    cols = st.columns(4)
    cols[0].metric(_L("execution.baseline_net_edge"), f"{report.baseline_net_edge:.2f}")
    cols[1].metric(_L("execution.worst_stressed_edge"), f"{report.worst_net_edge:.2f}")
    cols[2].metric(_L("panel.side"), report.side)
    cols[3].metric(_L("execution.qty"), f"{report.qty}")
    table = _build_execution_sensitivity_table(report)
    if table.empty:
        st.caption(_L("execution.no_sensitivity_data"))
    else:
        st.dataframe(table, hide_index=True, width="stretch")
        st.caption(_L("execution.sensitivity_caption"))

def _build_pre_trade_order_ticket_table(ticket: PreTradeOrderTicket) -> pd.DataFrame:
    return pd.DataFrame([check.as_dict() for check in ticket.checks])


def _render_pre_trade_order_ticket_panel(ticket: PreTradeOrderTicket) -> None:
    st.subheader(_L("panel.pre_trade_checklist"))
    if ticket.status == "OK":
        st.success(ticket.summary)
    elif ticket.status == "WARN":
        st.warning(ticket.summary)
    elif ticket.status == "BLOCKED":
        st.error(ticket.summary)
    else:
        st.info(ticket.summary)
    cols = st.columns(4)
    cols[0].metric(_L("panel.side"), ticket.side)
    cols[1].metric(_L("execution.qty"), f"{ticket.qty}")
    cols[2].metric(_L("execution.limit_ref_price"), f"{ticket.limit_price:.4f}")
    cols[3].metric(_L("execution.cash_required"), f"{ticket.cash_required:.2f}")
    st.dataframe(_build_pre_trade_order_ticket_table(ticket), hide_index=True, width="stretch")
    st.caption(_L("execution.pre_trade_caption"))

def _build_execution_journal_table(report: ExecutionJournalReport) -> pd.DataFrame:
    return pd.DataFrame([item.as_dict() for item in report.items])



def _render_execution_journal_panel(report: ExecutionJournalReport, journal_path=None, recent_journals=None) -> None:
    st.subheader(_L("panel.execution_journal"))
    if report.status == "OK":
        st.success(report.summary)
    elif report.status == "BLOCKED":
        st.error(report.summary)
    else:
        st.warning(report.summary)
    cols = st.columns(4)
    cols[0].metric(_L("journal.action"), report.action_type)
    cols[1].metric(_L("journal.manual_fills"), f"{report.manual_fill_count}")
    cols[2].metric(_L("journal.broker_matches"), f"{report.broker_matched_count}")
    cols[3].metric(_L("journal.status"), report.status)
    st.dataframe(_build_execution_journal_table(report), hide_index=True, width="stretch")
    if journal_path:
        st.caption(_L("journal.persisted_path", path=journal_path))
    history = build_execution_journal_history_table(recent_journals or [])
    if history:
        st.dataframe(pd.DataFrame(history), hide_index=True, width="stretch")
    st.caption(_L("journal.caption"))



def _build_broker_import_reconciliation_table(report: BrokerImportReconciliationReport) -> pd.DataFrame:
    return pd.DataFrame([item.as_dict() for item in report.items])



def _build_broker_fill_promotion_preview_table(preview: BrokerFillPromotionPreview) -> pd.DataFrame:
    return pd.DataFrame([check.as_dict() for check in preview.checks])



def _render_broker_import_reconciliation_panel(symbol: str, manual_fills, path) -> None:
    st.subheader(_L("panel.broker_import"))
    st.caption(_L("broker_import.caption"))
    if not path.exists():
        st.info(_L("broker_import.missing_export", path=path, cols=", ".join(supported_broker_fill_columns())))
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
    cols[0].metric(_L("broker_import.matched"), f"{report.matched_count}")
    cols[1].metric(_L("broker_import.broker_only"), f"{report.broker_only_count}")
    cols[2].metric(_L("broker_import.manual_only"), f"{report.manual_only_count}")
    cols[3].metric(_L("broker_import.ambiguous"), f"{report.ambiguous_count}")
    table = _build_broker_import_reconciliation_table(report)
    if not table.empty:
        st.dataframe(table, hide_index=True, width="stretch")
    st.caption(_L("broker_import.caption_evidence"))



def _build_live_session_risk_usage_table(report: LiveSessionRiskUsageReport) -> pd.DataFrame:
    return pd.DataFrame([check.as_dict() for check in report.checks])



def _build_session_closeout_table(report: SessionCloseoutReport) -> pd.DataFrame:
    return pd.DataFrame([check.as_dict() for check in report.checks])



def _build_session_closeout_pair_table(report: SessionCloseoutReport) -> pd.DataFrame:
    return pd.DataFrame([pair.as_dict() for pair in report.pair_attributions])


def _build_session_ledger_table(summary: SessionLedgerSummary) -> pd.DataFrame:
    return pd.DataFrame([row.as_dict() for row in summary.rows])



def _build_end_of_day_review_table(report: EndOfDayReviewReport) -> pd.DataFrame:
    return pd.DataFrame(build_end_of_day_review_table(report))




def _build_closeout_signoff_preview_table(preview: CloseoutSignoffPreview) -> pd.DataFrame:
    return pd.DataFrame([check.as_dict() for check in preview.checks])


def _render_closeout_signoff_panel(preview: CloseoutSignoffPreview) -> None:
    st.subheader(_L("panel.closeout_signoff"))
    if preview.status == "READY":
        st.success(preview.summary)
    elif preview.status == "BLOCKED":
        st.error(preview.summary)
    elif preview.status == "REVIEW_REQUIRED":
        st.warning(preview.summary)
    else:
        st.info(preview.summary)
    cols = st.columns(4)
    cols[0].metric(_L("panel.closeout_status"), preview.closeout_status)
    cols[1].metric(_L("panel.countable"), _L("yes") if preview.closeout_countable else _L("no"))
    cols[2].metric(_L("execution.reduction"), f"{preview.countable_cost_basis_reduction:.2f}")
    cols[3].metric(_L("panel.export"), preview.status)
    st.dataframe(_build_closeout_signoff_preview_table(preview), hide_index=True, width="stretch")
    st.caption(_L("closeout.signoff_caption", path=preview.signoff_path, note=preview.capability_note))
def _render_end_of_day_review_panel(report: EndOfDayReviewReport) -> None:
    st.subheader(_L("panel.eod_review"))
    if report.status == "OK":
        st.success(report.summary)
    elif report.status == "BLOCKED":
        st.error(report.summary)
    elif report.status == "WARN":
        st.warning(report.summary)
    else:
        st.info(report.summary)
    cols = st.columns(4)
    cols[0].metric(_L("panel.closeout_status"), report.closeout_status)
    cols[1].metric(_L("eod.recent_journals"), f"{report.recent_journal_count}")
    cols[2].metric(_L("eod.blocked_journals"), f"{report.blocked_journal_count}")
    cols[3].metric(_L("panel.countable"), _L("yes") if report.closeout_countable else _L("no"))
    st.dataframe(_build_end_of_day_review_table(report), hide_index=True, width="stretch")
    st.caption(_L("eod.caption"))



def _render_session_closeout_panel(report: SessionCloseoutReport) -> None:
    st.subheader(_L("panel.session_closeout"))
    if report.status == "OK":
        st.success(report.summary)
    elif report.status == "BLOCKED":
        st.error(report.summary)
    elif report.status == "WARN":
        st.warning(report.summary)
    else:
        st.info(report.summary)
    cols = st.columns(4)
    cols[0].metric(_L("closeout.closed_pairs"), f"{report.closed_pair_count}")
    cols[1].metric(_L("closeout.open_pairs"), f"{report.open_pair_count}")
    cols[2].metric(_L("closeout.net_qty_delta"), f"{report.net_position_delta_qty}")
    cols[3].metric(_L("execution.reduction"), f"{report.countable_cost_basis_reduction:.2f}")
    st.dataframe(_build_session_closeout_table(report), hide_index=True, width="stretch")
    pair_table = _build_session_closeout_pair_table(report)
    if not pair_table.empty:
        st.dataframe(pair_table, hide_index=True, width="stretch")
    st.caption(_L("closeout.caption"))


def _render_session_ledger_panel(summary: SessionLedgerSummary) -> None:
    st.subheader(_L("panel.session_ledger"))
    if summary.status == "OK":
        st.success(summary.summary)
    elif summary.status == "BLOCKED":
        st.error(summary.summary)
    elif summary.status == "WARN":
        st.warning(summary.summary)
    else:
        st.info(summary.summary)
    cols = st.columns(4)
    cols[0].metric(_L("ledger.realized_countable"), f"{summary.realized_countable_reduction:.2f}")
    cols[1].metric(_L("ledger.blocked_pair_cash"), f"{summary.blocked_pair_net_cash:.2f}")
    cols[2].metric(_L("ledger.countable_pairs"), f"{summary.countable_pair_count}")
    cols[3].metric(_L("ledger.no_action_day"), _L("yes") if summary.no_action_day else _L("no"))
    table = _build_session_ledger_table(summary)
    if not table.empty:
        st.dataframe(table, hide_index=True, width="stretch")
    st.caption(_L("ledger.caption"))



def _render_live_session_risk_usage_panel(report: LiveSessionRiskUsageReport) -> None:
    st.subheader(_L("panel.risk_usage"))
    if report.status == "OK":
        st.success(report.summary)
    elif report.status == "BLOCKED":
        st.error(report.summary)
    else:
        st.warning(report.summary)
    cols = st.columns(4)
    cols[0].metric(_L("journal.manual_fills"), f"{report.manual_fill_count}")
    cols[1].metric(_L("risk.gross_turnover_qty"), f"{report.gross_turnover_qty}")
    cols[2].metric(_L("risk.open_exposure"), f"{report.open_pair_notional:.2f}")
    cols[3].metric(_L("risk.max_open_age"), f"{report.max_open_pair_age_minutes:.1f}m")
    st.dataframe(_build_live_session_risk_usage_table(report), hide_index=True, width="stretch")
    st.caption(_L("risk.caption"))



def _build_post_trade_review_table(report: PostTradeReviewReport) -> pd.DataFrame:
    return pd.DataFrame([check.as_dict() for check in report.checks])



def _render_post_trade_review_panel(report: PostTradeReviewReport) -> None:
    st.subheader(_L("panel.post_trade_review"))
    if report.status == "OK":
        st.success(report.summary)
    elif report.status == "BLOCKED":
        st.error(report.summary)
    elif report.status == "NO_FILL":
        st.info(report.summary)
    else:
        st.warning(report.summary)
    cols = st.columns(4)
    cols[0].metric(_L("execution.fill_qty"), f"{report.fill_qty}/{report.expected_qty}")
    cols[1].metric(_L("post_trade.avg_fill"), f"{report.fill_avg_price:.4f}")
    cols[2].metric(_L("post_trade.ticket_price_diff"), f"{report.price_diff_vs_ticket:.4f}")
    cols[3].metric(_L("execution.worst_stressed_edge"), f"{report.worst_sensitivity_net_edge:.2f}")
    st.dataframe(_build_post_trade_review_table(report), hide_index=True, width="stretch")
    st.caption(_L("post_trade.caption"))



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
    st.subheader(_L("panel.position_reconciliation"))
    st.caption(_L("position_recon.caption"))
    report = reconcile_position_state(persisted, broker_snapshot)
    if report.status == "OK":
        st.success(report.summary)
    elif report.status == "BLOCKED":
        st.error(report.summary)
    else:
        st.warning(report.summary)
    st.dataframe(_build_position_reconciliation_table(report), hide_index=True, width="stretch")
    st.caption(_L("position_recon.path", path=path))

    with st.form("broker_position_reconciliation_form"):
        st.write(_L("position_recon.form_title"))
        broker_market_source = st.text_input(_L("position_recon.market_source"), value=persisted.market_source)
        broker_symbol = st.text_input(_L("position_recon.symbol"), value=persisted.symbol)
        total_qty = st.number_input(_L("position_recon.total_qty"), min_value=0, value=int(persisted.held_qty), step=1)
        sellable_qty = st.number_input(_L("position_recon.sellable_qty"), min_value=0, value=int(persisted.settled_sellable_qty), step=1)
        purchasable_qty = st.number_input(_L("position_recon.purchasable_qty"), min_value=0, value=int(persisted.purchasable_qty), step=1)
        cash_available = st.number_input(_L("position_recon.cash_available"), min_value=0.0, value=0.0, step=100.0)
        as_of = st.text_input(_L("position_recon.as_of"), value=datetime.now().isoformat(timespec="seconds"))
        note = st.text_input(_L("position_recon.note"), value=_L("position_recon.default_note"))
        submitted = st.form_submit_button(_L("position_recon.submit"))
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
            st.success(_L("position_recon.saved"))
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
    st.subheader(_L("panel.manual_execution"))
    st.caption(_L("manual.caption_intro"))
    checklist = build_execution_checklist(symbol, open_pair_side, open_pair_price, open_pair_qty, fills)
    st.dataframe(pd.DataFrame([item.as_dict() for item in checklist.items]), hide_index=True, width="stretch")
    st.caption(_L("manual.pair_info", pair_id=checklist.pair_id, status=checklist.status, path=path))
    if not open_pair_side:
        return

    next_side = expected_next_fill_side(open_pair_side, fills, checklist.pair_id)
    if next_side is None:
        st.success(_L("manual.both_legs_recorded"))
        return

    with st.form("manual_fill_record_form"):
        st.write(_L("manual.record_fill_for_pair", side=next_side.value, pair_id=checklist.pair_id))
        fill_qty = st.number_input(_L("manual.fill_qty"), min_value=1, value=max(1, int(open_pair_qty or 1)), step=1)
        fill_price = st.number_input(_L("manual.fill_price"), min_value=0.01, value=float(latest_price or open_pair_price or 0.01), step=0.01)
        fees = st.number_input(_L("manual.broker_fees"), min_value=0.0, value=0.0, step=0.01)
        slippage = st.number_input(_L("manual.slippage"), min_value=0.0, value=0.0, step=0.01)
        note = st.text_input(_L("manual.fill_note"), value=_L("manual.fill_note_default"))
        submitted = st.form_submit_button(_L("manual.submit"))
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
            st.success(_L("manual.recorded_fill", side=fill.side.value))
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
    buy_commission_rate = c1.number_input(_L("fees.buy_commission_rate"), min_value=0.0, value=float(default.buy_commission_rate), step=0.00001, format="%.5f")
    sell_commission_rate = c2.number_input(_L("fees.sell_commission_rate"), min_value=0.0, value=float(default.sell_commission_rate), step=0.00001, format="%.5f")
    min_commission = c1.number_input(_L("fees.minimum_commission"), min_value=0.0, value=float(default.min_commission), step=0.5)
    stamp_tax_rate = c2.number_input(_L("fees.stamp_tax_rate"), min_value=0.0, value=float(default.stamp_tax_rate), step=0.0001, format="%.5f")
    transfer_fee_rate = c1.number_input(_L("fees.transfer_fee_rate"), min_value=0.0, value=float(default.transfer_fee_rate), step=0.00001, format="%.5f")
    other_fee_rate = c2.number_input(_L("fees.other_fee_rate"), min_value=0.0, value=float(default.other_fee_rate), step=0.00001, format="%.5f")
    buy_slippage_rate = c1.number_input(_L("fees.buy_slippage_rate"), min_value=0.0, value=float(default.buy_slippage_rate), step=0.00001, format="%.5f")
    sell_slippage_rate = c2.number_input(_L("fees.sell_slippage_rate"), min_value=0.0, value=float(default.sell_slippage_rate), step=0.00001, format="%.5f")
    a_share_handling_fee_bps = default.a_share_handling_fee_bps
    a_share_management_fee_bps = default.a_share_management_fee_bps
    a_share_transfer_fee_bps = default.a_share_transfer_fee_bps
    a_share_stamp_duty_sell_bps = default.a_share_stamp_duty_sell_bps
    a_share_broker_commission_bps = default.a_share_broker_commission_bps
    a_share_min_commission_cny = default.a_share_min_commission_cny
    us_sec_fee_per_million = default.us_sec_fee_per_million
    us_finra_taf_per_share = default.us_finra_taf_per_share
    us_finra_taf_cap_per_trade = default.us_finra_taf_cap_per_trade
    us_broker_commission_per_share = default.us_broker_commission_per_share
    us_broker_min_commission = default.us_broker_min_commission
    us_platform_fee_per_order = default.us_platform_fee_per_order
    if default.market == "A_SHARE":
        a_share_handling_fee_bps = c1.number_input(_L("fees.a_share_handling_fee_bps"), min_value=0.0, value=float(default.a_share_handling_fee_bps), step=0.001, format="%.3f")
        a_share_management_fee_bps = c2.number_input(_L("fees.a_share_management_fee_bps"), min_value=0.0, value=float(default.a_share_management_fee_bps), step=0.001, format="%.3f")
        a_share_transfer_fee_bps = c1.number_input(_L("fees.a_share_transfer_fee_bps"), min_value=0.0, value=float(default.a_share_transfer_fee_bps), step=0.001, format="%.3f")
        a_share_stamp_duty_sell_bps = c2.number_input(_L("fees.a_share_stamp_duty_sell_bps"), min_value=0.0, value=float(default.a_share_stamp_duty_sell_bps), step=0.001, format="%.3f")
        a_share_broker_commission_bps = c1.number_input(_L("fees.a_share_broker_commission_bps"), min_value=0.0, value=float(default.a_share_broker_commission_bps), step=0.001, format="%.3f")
        a_share_min_commission_cny = c2.number_input(_L("fees.a_share_min_commission_cny"), min_value=0.0, value=float(default.a_share_min_commission_cny), step=0.5)
    elif default.market == "US_EQUITY":
        us_sec_fee_per_million = c1.number_input(_L("fees.us_sec_fee_per_million"), min_value=0.0, value=float(default.us_sec_fee_per_million), step=0.1)
        us_finra_taf_per_share = c2.number_input(_L("fees.us_finra_taf_per_share"), min_value=0.0, value=float(default.us_finra_taf_per_share), step=0.000001, format="%.6f")
        us_finra_taf_cap_per_trade = c1.number_input(_L("fees.us_finra_taf_cap_per_trade"), min_value=0.0, value=float(default.us_finra_taf_cap_per_trade), step=0.01)
        us_broker_commission_per_share = c2.number_input(_L("fees.us_broker_commission_per_share"), min_value=0.0, value=float(default.us_broker_commission_per_share), step=0.0001, format="%.4f")
        us_broker_min_commission = c1.number_input(_L("fees.us_broker_min_commission"), min_value=0.0, value=float(default.us_broker_min_commission), step=0.01)
        us_platform_fee_per_order = c2.number_input(_L("fees.us_platform_fee_per_order"), min_value=0.0, value=float(default.us_platform_fee_per_order), step=0.01)
    preview_price_default = 100.0 if default.market == "US_EQUITY" else 10.0
    preview_shares_default = 100 if default.market == "US_EQUITY" else 10_000
    preview_price = c1.number_input(_L("fees.preview_price"), min_value=0.01, value=float(preview_price_default), step=0.01)
    preview_shares = c2.number_input(_L("fees.preview_shares"), min_value=1, value=int(preview_shares_default), step=1)
    config = FeeConfig(
        market=default.market,
        buy_commission_rate=buy_commission_rate,
        sell_commission_rate=sell_commission_rate,
        min_commission=min_commission,
        stamp_tax_rate=stamp_tax_rate,
        transfer_fee_rate=transfer_fee_rate,
        other_fee_rate=other_fee_rate,
        buy_slippage_rate=buy_slippage_rate,
        sell_slippage_rate=sell_slippage_rate,
        a_share_handling_fee_bps=a_share_handling_fee_bps,
        a_share_management_fee_bps=a_share_management_fee_bps,
        a_share_transfer_fee_bps=a_share_transfer_fee_bps,
        a_share_stamp_duty_sell_bps=a_share_stamp_duty_sell_bps,
        a_share_broker_commission_bps=a_share_broker_commission_bps,
        a_share_min_commission_cny=a_share_min_commission_cny,
        us_sec_fee_per_million=us_sec_fee_per_million,
        us_finra_taf_per_share=us_finra_taf_per_share,
        us_finra_taf_cap_per_trade=us_finra_taf_cap_per_trade,
        us_broker_commission_per_share=us_broker_commission_per_share,
        us_broker_min_commission=us_broker_min_commission,
        us_platform_fee_per_order=us_platform_fee_per_order,
    )
    _render_custom_fee_break_even_preview(config, float(preview_price), int(preview_shares))
    return config


def _render_custom_fee_break_even_preview(config: FeeConfig, preview_price: float, preview_shares: int) -> None:
    try:
        round_trip_cost = FeeModel(config).estimate_round_trip_cost(config.market, preview_price, preview_shares, "B_TO_S")
        break_even_bps = FeeModel(config).estimate_break_even_bps(config.market, preview_price, preview_shares, "B_TO_S")
    except ValueError:
        return
    st.caption(
        _L(
            "fees.break_even_preview",
            market=config.market,
            shares=preview_shares,
            price=preview_price,
            cost=round_trip_cost,
            bps=break_even_bps,
        )
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
    st.subheader(_L("panel.model_audit"))
    if report.status == "OK":
        st.success(report.summary)
    else:
        st.warning(report.summary)
        st.caption(report.review_guidance)
    cols = st.columns(3)
    cols[0].metric(_L("model_audit.status"), report.status)
    cols[1].metric(_L("model_audit.locked_oos"), f"{report.locked_oos_count}")
    cols[2].metric(_L("model_audit.changes"), f"{len(report.threshold_changes) + len(report.metric_changes)}")
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
    st.subheader(_L("panel.baseline_update"))
    if preview.status == "NO_UPDATE_NEEDED":
        st.info(_L("model_audit.no_update_needed"))
    else:
        st.warning(preview.audit_summary)
    st.dataframe(_build_model_audit_baseline_update_table(preview), hide_index=True, width="stretch")
    st.caption(preview.report_note)
    with st.expander(_L("model_audit.update_gate"), expanded=preview.status == "REVIEW_REQUIRED"):
        st.write(_L("model_audit.update_gate_note"))
        st.code(MODEL_AUDIT_BASELINE_REVIEW_TOKEN)
        review_token = st.text_input(_L("model_audit.review_token"), value="", type="password")
        reviewer_note = st.text_input(_L("model_audit.reviewer_note"), value="")
        if st.button(_L("model_audit.apply_update"), disabled=preview.status != "REVIEW_REQUIRED"):
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
                "caveat": _L("threshold_experiment.caveat"),
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
    st.subheader(_L("panel.threshold_experiments"))
    st.caption(
        _L("research.threshold_caption")
    )
    st.dataframe(_build_threshold_experiment_comparison_table(report), hide_index=True, width="stretch")
    with st.expander(_L("research.threshold_expander"), expanded=False):
        detail = _build_threshold_experiment_metric_delta_table(report)
        if detail.empty:
            st.info(_L("research.threshold_no_delta"))
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
    st.subheader(_L("panel.research_audit"))
    st.caption(
        _L("research.page_intro")
    )
    if held_qty <= 0:
        st.warning(_L("research.need_qty"))

    can_run_position_sized_research = held_qty > 0
    if st.button(_L("research.run_scenario"), disabled=not can_run_position_sized_research):
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
        st.caption(_L("research.scenario_idle"))

    if st.button(_L("research.run_threshold"), disabled=not can_run_position_sized_research):
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
        st.caption(_L("research.threshold_idle"))

    if st.button(_L("research.run_model_audit")):
        try:
            _render_model_change_audit_report(build_model_change_audit_report())
        except Exception as exc:
            st.warning(_L("error.model_audit_unavailable", error=f"{type(exc).__name__}: {exc}"))
    else:
        st.caption(_L("research.model_audit_idle"))

    if st.button(_L("research.run_baseline_review")):
        try:
            _render_model_audit_baseline_update_panel(build_model_audit_baseline_update_preview())
        except Exception as exc:
            st.warning(_L("error.baseline_review_unavailable", error=f"{type(exc).__name__}: {exc}"))
    else:
        st.caption(_L("research.baseline_review_idle"))


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
    st.subheader(_L("research.scenario_title"))
    st.caption(
        _L("research.scenario_caption")
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
        with st.expander(_L("research.assumptions"), expanded=False):
            st.write(_L("research.synthetic_qty", qty=trade_qty))
            st.write(_L("research.assumption_no_trade"))
            st.write(_L("research.assumption_simple_baseline"))
            st.write(_L("research.assumption_signal_only"))
            st.dataframe(_build_risk_limit_preset_table(risk_limit_preset_id), hide_index=True, width="stretch")
    except Exception as exc:
        st.error(_L("error.scenario_unavailable", error=f"{type(exc).__name__}: {exc}"))


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
        st.warning(_L("error.threshold_unavailable", error=f"{type(exc).__name__}: {exc}"))


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
    st.subheader(_L("research.scenario_title"))
    st.caption(
        _L("research.scenario_caption")
    )
    if held_qty <= 0:
        st.warning(_L("research.need_qty"))
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
            with st.expander(_L("research.assumptions"), expanded=False):
                st.write(_L("research.synthetic_qty", qty=trade_qty))
                st.write(_L("research.assumption_no_trade"))
                st.write(_L("research.assumption_simple_baseline"))
                st.write(_L("research.assumption_signal_only"))
                st.dataframe(_build_risk_limit_preset_table(risk_limit_preset_id), hide_index=True, width="stretch")
        except Exception as exc:
            st.error(_L("error.scenario_unavailable", error=f"{type(exc).__name__}: {exc}"))
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
            st.warning(_L("error.threshold_unavailable", error=f"{type(exc).__name__}: {exc}"))
    try:
        audit_report = build_model_change_audit_report()
        _render_model_change_audit_report(audit_report)
    except Exception as exc:
        st.warning(_L("error.model_audit_unavailable", error=f"{type(exc).__name__}: {exc}"))
    try:
        _render_model_audit_baseline_update_panel(build_model_audit_baseline_update_preview())
    except Exception as exc:
        st.warning(_L("error.baseline_review_unavailable", error=f"{type(exc).__name__}: {exc}"))


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
    lot_size = _lot_size_for_market(market_source)
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
    if _is_korea_market(market_source):
        base_rules = _make_rules_config(
            {
                "lot_size": 1,
                "minimum_order_qty": 1,
                "max_t_ratio": max_t_ratio,
                "max_single_trade_qty": max_single_trade_qty,
                "start_time": "09:15",
                "no_new_trade_after": "15:05",
                "latest_open_time": "15:05",
                "force_restore_time": "15:20",
                "close_time": "15:30",
                "price_limit_pct": 0.30,
            }
        )
    elif _is_us_market(market_source):
        base_rules = _make_rules_config(
            {
                "lot_size": 1,
                "minimum_order_qty": 1,
                "max_t_ratio": max_t_ratio,
                "max_single_trade_qty": max_single_trade_qty,
                "start_time": "09:30",
                "no_new_trade_after": "15:35",
                "latest_open_time": "15:35",
                "force_restore_time": "15:50",
                "close_time": "16:00",
                "price_limit_pct": 1.00,
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
    if _is_yahoo_market(market_source):
        return _L("market.data_caption", market="Yahoo Finance", symbol=symbol, latest=latest.ts, price=latest.close)
    return _L("market.data_caption", market="Eastmoney", symbol=symbol, latest=latest.ts, price=latest.close)


def _is_korea_market(market_source: str) -> bool:
    return str(market_source or "").startswith("Korea")


def _is_us_market(market_source: str) -> bool:
    return str(market_source or "").startswith("US")


def _is_yahoo_market(market_source: str) -> bool:
    return "Yahoo Finance" in str(market_source or "")


def _lot_size_for_market(market_source: str) -> int:
    return 1 if _is_yahoo_market(market_source) else 100


def _fee_market_key(market_source: str) -> str:
    if _is_us_market(market_source):
        return "US_EQUITY"
    if str(market_source or "").startswith("A-share"):
        return "A_SHARE"
    return "GENERIC"


def _render_intent(intent: TradeIntent) -> None:
    label = _action_label(intent.action_type)
    if intent.action_type in {ActionType.TRIGGER_SELL_TO_BUY, ActionType.TRIGGER_BUY_TO_SELL}:
        st.success(_L("decision.intent_with_conf", action=label, confidence=intent.confidence))
    elif intent.action_type in {ActionType.MANAGE_OPEN_PAIR, ActionType.FORCE_CLOSE_OR_RESTORE}:
        st.warning(_L("decision.intent_with_conf", action=label, confidence=intent.confidence))
    else:
        st.info(_L("decision.intent_with_conf", action=label, confidence=intent.confidence))

    c1, c2, c3, c4 = st.columns(4)
    c1.metric(_L("intent.reference_price"), f"{intent.reference_price:.2f}")
    c2.metric(_L("intent.suggested_qty"), f"{intent.suggested_qty}")
    c3.metric(_L("intent.net_edge"), f"{intent.estimated_net_edge:.2f}")
    c4.metric(_L("intent.cost_per_share"), f"{intent.expected_cost_reduction_per_share:.4f}")
    st.write(_L("intent.next_action_prefix", value=intent.next_action or _L("na")))
    _render_list(_L("intent.reasons"), intent.reasons)
    _render_list(_L("intent.blockers"), intent.blockers)
    _render_list(_L("intent.warnings"), intent.warnings)


def _render_intent_compact(intent: TradeIntent) -> None:
    label = _action_label(intent.action_type)
    if intent.action_type in {ActionType.TRIGGER_SELL_TO_BUY, ActionType.TRIGGER_BUY_TO_SELL}:
        st.success(label)
    elif intent.action_type in {ActionType.MANAGE_OPEN_PAIR, ActionType.FORCE_CLOSE_OR_RESTORE}:
        st.warning(label)
    else:
        st.info(label)
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric(_L("intent.confidence"), f"{intent.confidence}")
    col2.metric(_L("intent.suggested_qty"), f"{intent.suggested_qty}")
    col3.metric(_L("intent.cost_per_share"), f"{intent.expected_cost_reduction_per_share:.4f}")
    deviation = intent.deviation_decision
    col4.metric(_L("intent.cost_bps"), f"{(deviation.estimated_round_trip_cost_bps if deviation else 0.0):.2f}")
    col5.metric(_L("intent.net_edge_bps"), f"{(deviation.net_edge_bps if deviation else 0.0):.2f}")
    inventory = _inventory_metric_payload(intent)
    inv1, inv2, inv3, inv4 = st.columns(4)
    inv1.metric(_L("intent.inventory_ok"), _L("yes") if inventory["inventory_ok"] else _L("no"))
    inv2.metric(_L("intent.sellable_after"), f"{inventory['sellable_after_trade']:,}")
    inv3.metric(_L("intent.inventory_delta"), f"{inventory['inventory_delta_after_trade']:+,}")
    inv4.metric(_L("intent.capital_required"), f"{inventory['capital_required']:,.2f}")
    st.markdown(_L("intent.next_action_prefix", value=intent.next_action or _L("na")))
    if intent.reasons:
        st.caption(_L("intent.key_reasons") + ": " + "; ".join(intent.reasons[:2]))
    if intent.blockers:
        st.warning(_L("intent.primary_blocker") + ": " + intent.blockers[0])


def _inventory_metric_payload(intent: TradeIntent) -> dict[str, int | float | bool]:
    inventory = intent.inventory_decision
    if inventory is None:
        return {
            "inventory_ok": False,
            "sellable_after_trade": 0,
            "inventory_delta_after_trade": 0,
            "capital_required": 0.0,
        }
    return {
        "inventory_ok": inventory.executable,
        "sellable_after_trade": inventory.sellable_after_trade,
        "inventory_delta_after_trade": inventory.inventory_delta_after_trade,
        "capital_required": inventory.capital_required,
    }


def _render_decision_summary(summary: DecisionSummary) -> None:
    st.subheader(_L("panel.decision_summary"))
    top = st.columns(3)
    _render_summary_section(top[0], _L("summary.recommendation"), summary.recommendation)
    _render_summary_section(top[1], _L("summary.invalidation"), summary.invalidation)
    _render_summary_section(top[2], _L("summary.position_impact"), summary.position_impact)
    bottom = st.columns(2)
    _render_summary_section(bottom[0], _L("summary.evidence"), summary.evidence)
    _render_summary_section(bottom[1], _L("summary.caveats"), summary.caveats)


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
        "broker_confirmed": _L("status.broker_yes") if disclosure.broker_confirmed else _L("status.broker_no"),
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
        _L("status.strip_template", data=payload["data"], broker_confirmed=payload["broker_confirmed"], latest_bar=payload["latest_bar"], bars=payload["bars"], status=_L(f"status.{payload['status'].lower()}"))
    )
    if payload["status"] == "OK":
        st.success(message)
    elif payload["status"] == "BAD":
        st.error(message)
    else:
        st.warning(message)


def _render_data_risk_details(disclosure: DataSourceDisclosure, report: DataQualityReport, intent: TradeIntent) -> None:
    expanded = _should_expand_data_risk_details(disclosure, report, intent)
    with st.expander(_L("panel.source_caveats"), expanded=expanded):
        _render_data_source_disclosure(disclosure)
    with st.expander(_L("panel.data_quality"), expanded=expanded):
        _render_data_quality(report)


def _render_data_source_disclosure(disclosure: DataSourceDisclosure) -> None:
    st.warning(disclosure.summary())
    cols = st.columns(3)
    cols[0].metric(_L("panel.source_grade"), disclosure.source_grade)
    cols[1].metric(_L("intent.broker_confirmed"), _L("status.broker_yes") if disclosure.broker_confirmed else _L("status.broker_no"))
    cols[2].metric(_L("panel.delay_status"), disclosure.delay_status)
    st.dataframe(_build_source_disclosure_table(disclosure), hide_index=True, width="stretch")
    st.caption(_L("status.live_note"))

def _render_data_quality(report: DataQualityReport) -> None:
    message = f"{report.status}: {report.confidence_note}"
    message = f"{_L(f'status.{report.status.lower()}')}: {report.confidence_note}"
    if report.status == "OK":
        st.success(message)
    elif report.status == "BAD":
        st.error(message)
    else:
        st.warning(message)

    cols = st.columns(3)
    cols[0].metric(_L("market.bars"), f"{report.bar_count}")
    cols[1].metric(_L("market.latest_bar"), report.latest_ts)
    cols[2].metric(_L("status.checks"), f"{len(report.checks)}")

    with st.expander(_L("panel.data_quality"), expanded=report.status != "OK"):
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
    st.subheader(_L("panel.intraday_market"))
    if _is_yahoo_market(market_source):
        st.caption(_L("market.source_hint"))
    df = _build_market_frame(bars)
    plot_df = chart_df if chart_df is not None else df
    _render_market_ratio_metrics(df, intent)
    _render_signal_summary(signal_markers)
    if chart_df is not None and len(chart_df) != len(df):
        st.caption(
            _L(
                "market.marker_caption",
                total=len(chart_df),
                time=pd.Timestamp(df.iloc[-1]["time"]).strftime("%H:%M"),
            )
        )
    _render_price_chart(plot_df, signal_markers, intent, show_markers=show_chart_markers)
    _render_ratio_chart(plot_df)
    _render_signal_detail(signal_markers)
    with st.expander(_L("panel.trade_intent_json")):
        st.json(intent.as_dict())


def _render_layers(intent: TradeIntent) -> None:
    st.subheader(_L("layer.header"))
    st.caption(_L("layer.subtitle"))
    payload = intent.as_dict()
    col1, col2, col3 = st.columns(3)
    with col1:
        _render_regime_card(payload.get("regime_decision"))
    with col2:
        _render_deviation_card(payload.get("deviation_decision"))
    with col3:
        _render_inventory_card(payload.get("inventory_decision"))
    with st.expander(_L("panel.raw_json")):
        tabs = st.tabs([_L("panel.regime"), _L("panel.deviation"), _L("panel.inventory")])
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
        st.caption(_L("status.live_mode"))
        return
    st.info(
        _L("status.replay_mode", time=pd.Timestamp(replay_time).strftime("%H:%M"))
    )
    if st.button(_L("status.replay_back"), key="back_to_live"):
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
    cols[0].metric(_L("market.close_vs_open"), _fmt_pct(float(latest["close_vs_open_pct"])))
    cols[1].metric(_L("market.vwap_deviation"), _fmt_pct(float(latest["vwap_deviation_pct"])))
    cols[2].metric(_L("market.amplitude"), _fmt_pct(amplitude_pct))
    cols[3].metric(_L("market.suggested_ratio"), _fmt_pct_unsigned(intent.suggested_ratio * 100), help=_L("intent.suggested_ratio_help"))
    st.caption(
        _L(
            "market.metrics_prefix",
            date=session_date,
            count=len(df),
            latest=float(latest["close"]),
            open=open_price,
            vwap=float(latest["vwap"]),
        )
    )


def _render_signal_summary(signal_markers: pd.DataFrame) -> None:
    if signal_markers.empty:
        st.caption(_L("market.no_opportunities"))
        return
    if "state" in signal_markers.columns:
        counts = signal_markers["state"].value_counts().to_dict()
        st.caption(
            _L(
                "market.signal_counts_main",
                watch=counts.get("WATCH", 0),
                enter=counts.get("ENTER", 0),
                exit=counts.get("EXIT", 0),
                abort=counts.get("ABORT", 0),
            )
        )
        return
    counts = signal_markers["signal"].value_counts().to_dict()
    st.caption(
        _L(
            "market.signal_counts_simple",
            sb=counts.get("SB", 0),
            bs=counts.get("BS", 0),
            watch_sb=counts.get("Watch S->B", 0),
            watch_bs=counts.get("Watch B->S", 0),
        )
    )


def _render_price_chart(df: pd.DataFrame, signal_markers: pd.DataFrame, intent: TradeIntent, show_markers: bool = False) -> None:
    chart_df = df[["time", "close", "vwap"]].melt("time", var_name="line", value_name="price")
    chart_df["line"] = chart_df["line"].map({"close": _L("chart.price"), "vwap": _L("chart.vwap")})
    base = (
        alt.Chart(chart_df)
        .mark_line(strokeWidth=2)
        .encode(
            x=alt.X("time:T", title=_L("chart.time")),
            y=alt.Y("price:Q", title=_L("chart.price"), scale=alt.Scale(zero=False)),
            color=alt.Color(
                "line:N",
                title="",
                scale=alt.Scale(
                    domain=[_L("chart.price"), _L("chart.vwap")],
                    range=["#2563eb", "#d97706"],
                ),
            ),
            tooltip=[
                alt.Tooltip("time:T", title=_L("chart.time"), format="%H:%M"),
                alt.Tooltip("line:N", title=_L("chart.line")),
                alt.Tooltip("price:Q", title=_L("chart.price"), format=",.2f"),
            ],
        )
        .properties(height=260)
    )
    current_marker = pd.DataFrame([_current_intent_marker_row(intent, df)])
    current_rule = (
        alt.Chart(current_marker)
        .mark_rule(color="#facc15", strokeDash=[6, 4], strokeWidth=2)
        .encode(
            x=alt.X("time:T", title=_L("chart.time")),
            tooltip=[
                alt.Tooltip("time:T", title=_L("chart.latest_closed_minute"), format="%H:%M"),
                alt.Tooltip("action:N", title=_L("chart.current_action")),
                alt.Tooltip("price:Q", title=_L("intent.reference_price"), format=",.2f"),
                alt.Tooltip("confidence:Q", title=_L("intent.confidence")),
                alt.Tooltip("suggested_qty:Q", title=_L("execution.qty"), format=","),
                alt.Tooltip("suggested_ratio_pct:Q", title=_L("summary.suggested_ratio"), format=".2f"),
                alt.Tooltip("vwap_deviation_pct:Q", title=_L("market.vwap_deviation"), format=".3f"),
                alt.Tooltip("net_edge:Q", title=_L("intent.net_edge"), format=",.2f"),
                alt.Tooltip("reason:N", title=_L("intent.reasons")),
                alt.Tooltip("note:N", title=_L("summary.caveat_warning")),
            ],
        )
    )
    current_point = (
        alt.Chart(current_marker)
        .mark_point(filled=True, size=260, color="#facc15", stroke="#111827", strokeWidth=1.5)
        .encode(
            x=alt.X("time:T", title=_L("chart.time")),
            y=alt.Y("price:Q", title=_L("chart.price"), scale=alt.Scale(zero=False)),
            shape=alt.Shape(
                "side:N",
                title=_L("panel.side"),
                scale=alt.Scale(domain=["S->B", "B->S", "None"], range=["triangle-down", "triangle-up", "circle"]),
            ),
            tooltip=[
                alt.Tooltip("time:T", title=_L("chart.latest_closed_minute"), format="%H:%M"),
                alt.Tooltip("action:N", title=_L("chart.current_action")),
                alt.Tooltip("price:Q", title=_L("intent.reference_price"), format=",.2f"),
                alt.Tooltip("confidence:Q", title=_L("intent.confidence")),
                alt.Tooltip("suggested_qty:Q", title=_L("execution.qty"), format=","),
                alt.Tooltip("reason:N", title=_L("intent.reasons")),
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
            x=alt.X("time:T", title=_L("chart.time")),
            tooltip=[
                alt.Tooltip("time:T", title=_L("chart.click_to_replay"), format="%H:%M"),
                alt.Tooltip("close:Q", title=_L("chart.close"), format=",.2f"),
            ],
        )
        .add_params(minute_selection)
    )
    chart = base + current_rule + current_point + current_label + click_rules
    if show_markers and not signal_markers.empty:
        has_state = "state" in signal_markers.columns
        visible_markers = _main_chart_signal_markers(signal_markers) if has_state else signal_markers[signal_markers["level"] == "Trigger"]
        if visible_markers.empty:
            visible_markers = _main_chart_signal_markers(signal_markers)
        color_encoding = (
            alt.Color(
                "state:N",
                title=_L("chart.state"),
                scale=alt.Scale(
                    domain=["ENTER", "EXIT", "ABORT"],
                    range=["#2563eb", "#22c55e", "#dc2626"],
                ),
            )
            if has_state
            else alt.Color(
                "signal:N",
                title=_L("chart.signal"),
                scale=alt.Scale(domain=["SB", "BS", "Watch S->B", "Watch B->S"], range=["#dc2626", "#16a34a", "#ea580c", "#65a30d"]),
            )
        )
        label_color = (
            alt.Color(
                "state:N",
                legend=None,
                scale=alt.Scale(
                    domain=["ENTER", "EXIT", "ABORT"],
                    range=["#2563eb", "#22c55e", "#dc2626"],
                ),
            )
            if has_state
            else alt.Color("signal:N", legend=None, scale=alt.Scale(domain=["SB", "BS"], range=["#dc2626", "#16a34a"]))
        )
        tooltip = [
            alt.Tooltip("time:T", title=_L("chart.time"), format="%H:%M"),
            alt.Tooltip("action:N", title=_L("chart.action")),
            alt.Tooltip("price:Q", title=_L("chart.price"), format=",.2f"),
            alt.Tooltip("confidence:Q", title=_L("intent.confidence")),
            alt.Tooltip("suggested_qty:Q", title=_L("execution.qty"), format=","),
            alt.Tooltip("vwap_deviation_pct:Q", title=_L("market.vwap_deviation"), format=".3f"),
            alt.Tooltip("anchor_type:N", title=_L("market.anchor")),
            alt.Tooltip("exhaustion_score:Q", title=_L("chart.exhaustion"), format=".1f"),
            alt.Tooltip("liquidity_score:Q", title=_L("chart.liquidity"), format=".1f"),
            alt.Tooltip("debug_state:N", title=_L("chart.debug_state")),
            alt.Tooltip("regime_simple:N", title=_L("chart.regime_simple")),
            alt.Tooltip("cost_bps:Q", title=_L("chart.cost_bps"), format=".2f"),
            alt.Tooltip("net_edge_bps:Q", title=_L("chart.net_edge_bps"), format=".2f"),
            alt.Tooltip("net_edge:Q", title=_L("intent.net_edge"), format=",.2f"),
            alt.Tooltip("target_price:Q", title=_L("summary.expected_reversion"), format=",.2f"),
            alt.Tooltip("invalidation_price:Q", title=_L("summary.invalidation_price"), format=",.2f"),
            alt.Tooltip("reason_codes:N", title=_L("chart.reason_codes")),
            alt.Tooltip("blocked_reasons:N", title=_L("intent.blockers")),
            alt.Tooltip("why_not_earlier:N", title=_L("chart.why_not_earlier")),
            alt.Tooltip("reason:N", title=_L("intent.reasons")),
        ]
        if has_state:
            tooltip.insert(1, alt.Tooltip("state:N", title=_L("chart.state")))
            tooltip.append(alt.Tooltip("note:N", title=_L("summary.caveat_warning")))
        points = (
            alt.Chart(visible_markers)
            .mark_point(filled=True, opacity=0.9)
            .encode(
                x=alt.X("time:T", title=_L("chart.time")),
                y=alt.Y("price:Q", title=_L("chart.price"), scale=alt.Scale(zero=False)),
                color=color_encoding,
                shape=alt.Shape("side:N", title=_L("panel.side"), scale=alt.Scale(domain=["S->B", "B->S"], range=["triangle-down", "triangle-up"])),
                size=alt.Size("state:N", title=_L("chart.marker_level"), scale=alt.Scale(domain=["ENTER", "EXIT", "ABORT"], range=[190, 160, 170])),
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
                text="action:N" if has_state else "signal:N",
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


def _main_chart_signal_markers(signal_markers: pd.DataFrame) -> pd.DataFrame:
    if signal_markers.empty or "state" not in signal_markers.columns:
        return signal_markers
    return signal_markers[signal_markers["state"].isin(["ENTER", "EXIT", "ABORT"])]


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
            "deviation_bps",
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
    with st.expander(_L("panel.signal_details")):
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
    label_map = {"close_vs_open_pct": _L("market.close_vs_open"), "vwap_deviation_pct": _L("market.vwap_deviation")}
    ratio_df["ratio"] = ratio_df["ratio"].map(label_map)
    line = (
        alt.Chart(ratio_df)
        .mark_line(strokeWidth=2)
        .encode(
            x=alt.X("time:T", title=_L("chart.time")),
            y=alt.Y("pct:Q", title=_L("chart.percent"), axis=alt.Axis(format=".2f")),
            color=alt.Color(
                "ratio:N",
                title="",
                scale=alt.Scale(
                    domain=[_L("market.close_vs_open"), _L("market.vwap_deviation")],
                    range=["#16a34a", "#ca8a04"],
                ),
            ),
            tooltip=[
                alt.Tooltip("time:T", title=_L("chart.time"), format="%H:%M"),
                alt.Tooltip("ratio:N", title=_L("chart.ratio")),
                alt.Tooltip("pct:Q", title="%", format=".3f"),
            ],
        )
    )
    zero = alt.Chart(pd.DataFrame({"pct": [0]})).mark_rule(color="#64748b").encode(y="pct:Q")
    st.altair_chart((line + zero).properties(height=220), width="stretch")


def _render_regime_card(regime: dict | None) -> None:
    with st.container(border=True):
        st.markdown(f"**1. {_L('panel.regime')}**")
        if not regime:
            st.info(_L("layer.not_calculated"))
            return
        regime_type = regime.get("regime_type", "")
        blockers = regime.get("blockers") or []
        status = _L("layer.blocked") if blockers else _L("layer.passed")
        st.metric(status, _regime_label(regime_type), delta=f"{_L('summary.confidence_prefix', value=regime.get('confidence', 0))}")
        st.write(f"{_L('side.sb')}: {_yes_no(regime.get('allow_sell_to_buy'))} | {_L('side.bs')}: {_yes_no(regime.get('allow_buy_to_sell'))}")
        _render_compact_rows(_L("intent.reasons"), regime.get("reasons") or [_L("layer.no_reason")])
        _render_compact_rows(_L("intent.blockers"), blockers)


def _render_deviation_card(deviation: dict | None) -> None:
    with st.container(border=True):
        st.markdown(f"**2. {_L('panel.deviation')}**")
        if not deviation:
            st.info(_L("layer.not_calculated_regime"))
            return
        side = deviation.get("side_candidate", "NONE")
        score = float(deviation.get("deviation_score") or 0.0)
        st.metric(_L("layer.candidate"), _side_label(side), delta=f"{_L('layer.score')} {score:.2f}x")
        c1, c2 = st.columns(2)
        c1.metric(_L("summary.net_edge"), f"{float(deviation.get('net_edge_after_fee') or 0):,.2f}")
        c2.metric(_L("layer.max_wait"), f"{int(deviation.get('max_wait_minutes') or 0)} {_L('chart.min')}")
        if deviation.get("expected_reversion_zone") is not None:
            st.write(f"{_L('summary.expected_reversion')}: {float(deviation['expected_reversion_zone']):,.2f}")
        if deviation.get("invalidation_price") is not None:
            st.write(f"{_L('summary.invalidation_price')}: {float(deviation['invalidation_price']):,.2f}")
        _render_compact_rows(_L("intent.reasons"), deviation.get("reasons") or [])
        _render_compact_rows(_L("intent.warnings"), deviation.get("warnings") or [])


def _render_inventory_card(inventory: dict | None) -> None:
    with st.container(border=True):
        st.markdown(f"**3. {_L('panel.inventory')}**")
        if not inventory:
            st.info(_L("layer.not_calculated_inventory"))
            return
        executable = bool(inventory.get("executable"))
        status = _L("inventory.executable") if executable else _L("inventory.not_executable")
        qty = int(inventory.get("suggested_qty") or 0)
        st.metric(status, f"{qty:,} {_L('layer.shares')}", delta=_fmt_pct(float(inventory.get('suggested_ratio') or 0) * 100))
        c1, c2 = st.columns(2)
        c1.metric(_L("execution.cash_required"), f"{float(inventory.get('capital_required') or 0):,.2f}")
        c2.metric(_L("layer.sellable_after"), f"{int(inventory.get('sellable_after_trade') or 0):,} {_L('layer.shares')}")
        delta = int(inventory.get("inventory_delta_after_trade") or 0)
        st.write(f"{_L('summary.inventory_delta')}: {delta:+,} {_L('layer.shares')}")
        _render_compact_rows(_L("intent.reasons"), inventory.get("reasons") or [])
        _render_compact_rows(_L("intent.blockers"), inventory.get("blockers") or [])


def _render_compact_rows(title: str, rows: list[str]) -> None:
    if not rows:
        return
    st.write(f"{title}:")
    for row in rows[:4]:
        st.markdown(f"- {row}")
    if len(rows) > 4:
        st.caption(_L("layer.raw_rows_more", count=len(rows) - 4))


def _render_list(title: str, rows: list[str]) -> None:
    if not rows:
        return
    st.write(f"{title}:")
    for row in rows:
        st.markdown(f"- {row}")


def _yes_no(value: bool | None) -> str:
    return _L("yes") if value else _L("no")


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




























