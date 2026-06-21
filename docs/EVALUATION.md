# Evaluation

## Debug-Field Alias Closeout

Validation scope:

- Lifecycle events expose `deviation_bps` as an alias for `vwap_deviation_bps`.
- Signal details can include `deviation_bps`.
- Focused validation: `python -m py_compile research\opportunity_lifecycle.py app\dashboard.py tests\test_opportunity_lifecycle.py tests\test_dashboard_signals.py`; `python -m pytest tests\test_opportunity_lifecycle.py tests\test_dashboard_signals.py -q -p no:cacheprovider --basetemp=.runtime\pytest-tmp-debug-fields-alias` (17 passed).
- This is debug/export naming only; it does not alter trigger thresholds, sizing, fees, fills, or cost-basis accounting.

## Inventory and Sellability Top-Level Decision Exposure

Validation scope:

- `TradeIntent.as_dict()` exposes top-level `inventory_ok`, `sellable_after_trade`, `inventory_delta_after_trade`, and `capital_required`.
- Dashboard compact decision payload shows inventory OK, sellable-after, inventory delta, and capital required.
- Focused validation: `python -m py_compile research\trigger_engine.py app\dashboard.py app\ui_text.py tests\test_trigger_engine.py tests\test_dashboard_signals.py`; `python -m pytest tests\test_trigger_engine.py::test_sell_to_buy_triggers_when_regime_deviation_and_inventory_pass tests\test_dashboard_signals.py -q -p no:cacheprovider --basetemp=.runtime\pytest-tmp-inventory-top-level` (11 passed).
- This validates observability only; it does not change inventory gates, broker reconciliation, fills, or countable cost-basis reduction.

## Decision-Path Cost and Edge Bps Exposure

Validation scope:

- `TradeIntent.as_dict()` exposes top-level `estimated_round_trip_cost_bps`, `net_edge_bps`, and `min_edge_buffer_bps`.
- Decision summary evidence includes round-trip cost bps, net edge bps, and required edge buffer.
- Dashboard top trading decision card shows round-trip cost bps and net edge bps.
- Focused validation: `python -m py_compile research\trigger_engine.py research\decision_summary.py app\dashboard.py app\ui_text.py tests\test_trigger_engine.py tests\test_decision_summary.py tests\test_dashboard_signals.py`; `python -m pytest tests\test_trigger_engine.py::test_round_trip_edge_buffer_blocks_enter tests\test_decision_summary.py tests\test_dashboard_signals.py -q -p no:cacheprovider --basetemp=.runtime\pytest-tmp-edge-bps-display3` (12 passed).
- This validates observability only; it does not alter trigger thresholds, route orders, infer fills, or count cost-basis reduction.

## Custom Fee Break-Even Preview

Validation scope:

- Dashboard custom fee mode displays round-trip cost and break-even bps from the selected market `FeeModel`.
- The preview uses user-entered preview price and share count and does not mutate fee profiles or trigger thresholds.
- Focused validation: `python -m py_compile app\dashboard.py app\ui_text.py tests\test_dashboard_model_audit.py`; `python -m pytest tests\test_dashboard_model_audit.py::test_dashboard_custom_fee_config_preserves_market tests\test_fee_model.py tests\test_fee_profiles.py -q -p no:cacheprovider --basetemp=.runtime\pytest-tmp-fee-preview` (11 passed).
- This validates display and cost-model plumbing only; it does not verify broker schedules, route orders, infer fills, or count cost-basis reduction.

## Market-Specific Custom Fee Plumbing

Validation scope:

- CLI custom fee args expose A-share official bps/min-commission fields and US SEC/FINRA/broker/platform fields.
- Dashboard custom fee config preserves `FeeConfig.market` and returns market-specific custom fields.
- Focused validation: `python -m py_compile app\cli.py app\dashboard.py app\ui_text.py tests\test_cli.py tests\test_dashboard_model_audit.py tests\test_fee_model.py tests\test_fee_profiles.py`; `python -m pytest tests\test_cli.py::test_cli_fee_config_is_explicitly_configurable tests\test_cli.py::test_cli_us_custom_fee_components_are_configurable tests\test_cli.py::test_cli_default_fee_profile_is_costed_not_zero_fee tests\test_cli.py::test_cli_us_yahoo_uses_us_fee_profile_and_rules tests\test_dashboard_model_audit.py::test_dashboard_custom_fee_config_preserves_market tests\test_fee_model.py tests\test_fee_profiles.py -q -p no:cacheprovider --basetemp=.runtime\pytest-tmp-fee-config-plumbing` (15 passed).
- This validates configuration plumbing only; it does not verify any live broker fee schedule, route orders, infer fills, or count cost-basis reduction.

## Model-Audit Review Guidance and Custom-Fee Market Fix

Validation scope:

- `ModelChangeAuditReport.as_dict()` now includes `review_guidance`.
- OK audit reports state that no baseline update is needed.
- REVIEW audit reports state that baseline drift is a human review gate and not evidence of improvement.
- Dashboard custom fee config preserves the selected `FeeConfig.market`, including `US_EQUITY`.
- Focused validation: `python -m py_compile research\model_audit.py app\dashboard.py tests\test_model_audit.py tests\test_dashboard_model_audit.py`; `python -m pytest tests\test_model_audit.py tests\test_dashboard_model_audit.py -q -p no:cacheprovider --basetemp=.runtime\pytest-tmp-audit-guidance2` (8 passed).
- This does not mutate the locked baseline, route orders, infer fills, realize PnL, or count cost-basis reduction.

## Subtractive Intraday Execution Simplification

Validation scope:

- Main lifecycle output is collapsed to `NO_TRADE`, `WATCH`, `ENTER`, `EXIT`, and `ABORT`, with richer diagnostic states retained for detail tables/tooltips.
- Main chart signal markers filter to enter/exit/abort events so watch/debug states do not dominate the price chart.
- Default auto-add is disabled, default max T ratio is 5%, and no-new-pair cutoffs are explicit.
- A-share fee modeling includes official handling/management/transfer, sell stamp duty, broker commission, minimum commission, and slippage assumptions.
- US fee modeling includes SEC fee, FINRA TAF, optional broker/platform fees, and slippage assumptions.
- Trigger entry gates use market-aware round-trip costs and a 5 bps net-edge buffer.
- Focused validation passed for fee model/profiles, trigger engine, opportunity lifecycle, dashboard signal/risk rendering, order tickets, execution sensitivity, evaluation reports, model audit, and threshold experiments.
- `python -m compileall .` exited 0, with existing inaccessible pytest/cache/temp directory listing warnings.
- Full `python -m pytest -q` could not produce a clean final report in this Windows environment because pytest hit `PermissionError` while iterating its basetemp during session finish.
- This changes signal semantics and cost gating only; it does not infer fills, route orders, realize PnL, or count cost-basis reduction.

## US/Yahoo Market Module

Validation scope:

- Dashboard has a third `US / Yahoo Finance` market source with US ticker examples and 1-share lot defaults.
- CLI trigger paths accept `--data-source us_yahoo`, map US persisted position snapshots back to `us_yahoo`, and select `US / Yahoo Finance` as the market source for fee/rule derivation.
- US/Yahoo uses `us_prototype_conservative` rather than A-share or Korea defaults.
- Source disclosure and data-quality checks keep Yahoo as a research/prototype feed with approximate turnover amount.
- Focused validation: `python -m py_compile app\dashboard.py app\cli.py app\ui_text.py core\fee_profiles.py research\source_disclosure.py data\yahoo.py tests\test_yahoo.py tests\test_dashboard_risk_limits.py tests\test_fee_profiles.py tests\test_source_disclosure.py tests\test_data_quality.py tests\test_cli.py`; `python -m pytest tests\test_yahoo.py tests\test_dashboard_risk_limits.py tests\test_fee_profiles.py tests\test_source_disclosure.py tests\test_data_quality.py tests\test_cli.py::test_cli_us_yahoo_uses_us_fee_profile_and_rules tests\test_cli.py::test_cli_position_snapshot_maps_us_market_to_us_yahoo_source -q --basetemp=.runtime\pytest-tmp-us-yahoo -o cache_dir=.runtime\pytest-cache-us-yahoo` (29 passed; local pytest cache warnings only); `python -m app.cli trigger --scenario mean_revert --data-source us_yahoo --held-qty 100 --settled-sellable-qty 100 --purchasable-qty 10 --max-t-ratio 0.10 --risk-preset balanced --no-position-state` completed and selected `fee_profile=us_prototype_conservative`.
- This does not validate live Yahoo availability for any specific US ticker and does not infer fills, route orders, model FX, claim profitability, or count cost-basis reduction.

## Per-Session Ledger Summary

Validation scope:

- `app.session_ledger` derives realized/countable reduction, blocked pair net cash, and no-action-day rows from `SessionCloseoutReport`.
- CLI trigger output includes `session_ledger`; dashboard exposes a session ledger panel/table.
- Positive blocked pair cash remains non-countable until closeout gates pass.
- This does not infer fills, route orders, realize PnL, or count cost-basis reduction outside closeout.
- Focused validation: `python -m py_compile app\session_ledger.py app\session_closeout.py app\cli.py app\dashboard.py tests\test_session_ledger.py tests\test_dashboard_session_closeout.py tests\test_session_closeout.py tests\test_end_of_day_review.py`; `python -m pytest tests\test_session_ledger.py tests\test_dashboard_session_closeout.py tests\test_session_closeout.py tests\test_end_of_day_review.py -q --basetemp=.runtime\pytest-tmp-ledger-core -o cache_dir=.runtime\pytest-cache-ledger-core` (16 passed); `python -m app.cli trigger --scenario mean_revert --held-qty 10000 --settled-sellable-qty 10000 --purchasable-qty 10000 --max-t-ratio 0.10 --risk-preset defensive --ignore-fees --no-position-state` completed and emitted `session_ledger`. Local pytest cache warnings only.

## Broker/Manual Fill Freshness Checks

Validation scope:

- Session closeout now includes a `fill_freshness` check for manual-fill and broker-export row dates versus the session date.
- Stale rows produce WARN and are not counted as current-session closeout evidence.
- End-of-day review surfaces closeout WARN status in its summary and rows.
- This does not infer fills, route orders, realize PnL, or count cost-basis reduction from stale evidence.
- Focused validation: `python -m py_compile app\session_closeout.py app\end_of_day_review.py app\cli.py app\dashboard.py tests\test_session_closeout.py tests\test_end_of_day_review.py tests\test_dashboard_session_closeout.py tests\test_dashboard_end_of_day_review.py`; `python -m pytest tests\test_session_closeout.py tests\test_end_of_day_review.py tests\test_dashboard_session_closeout.py tests\test_dashboard_end_of_day_review.py -q --basetemp=.runtime\pytest-tmp-freshness-core -o cache_dir=.runtime\pytest-cache-freshness-core` (13 passed); `python -m pytest tests\test_cli.py::test_cli_fee_config_is_explicitly_configurable tests\test_cli.py::test_cli_default_fee_profile_is_costed_not_zero_fee tests\test_cli.py::test_cli_zero_fee_requires_explicit_flag_or_profile -q --basetemp=.runtime\pytest-tmp-freshness-cli-basic -o cache_dir=.runtime\pytest-cache-freshness-cli-basic` (3 passed); `python -m app.cli trigger --scenario mean_revert --held-qty 10000 --settled-sellable-qty 10000 --purchasable-qty 10000 --max-t-ratio 0.10 --risk-preset defensive --ignore-fees --no-position-state` completed and emitted `fill_freshness`. Local pytest cache warnings only; full `tests\test_cli.py` combined run remains blocked by Windows `tmp_path` permission errors.

## Bounded Multi-Leg Lifecycle State

Validation scope:

- Lifecycle ADD markers now require same-side trigger, max-leg room, total T cap room, minimum spacing, and minimum price improvement.
- `OpportunityEvent` exposes `leg_count`, cumulative `total_suggested_qty`, `max_total_suggested_qty`, add price improvement, and minutes since the prior leg.
- A same-side trigger that crosses invalidation but cannot add because of a bound is blocked with the failed constraint in the reason.
- This does not infer fills, route orders, realize PnL, or count cost-basis reduction.
- Focused validation: `python -m py_compile research\trigger_engine.py research\opportunity_lifecycle.py tests\test_opportunity_lifecycle.py tests\test_trigger_engine.py tests\test_dashboard_signals.py`; `python -m pytest tests\test_opportunity_lifecycle.py tests\test_trigger_engine.py tests\test_dashboard_signals.py -q --basetemp=pytest_tmp_bounded_multileg -o cache_dir=pytest_cache_bounded_multileg` (30 passed; local pytest cache warnings only).

## Soft Down-Regime B/S Gating

Validation scope:

- `TriggerEngine` now emits down-regime profiles that distinguish weak-down, strong-down, and crash-down conditions.
- B->S trigger eligibility uses side-specific deviation thresholds, regime trigger multipliers, and downside exhaustion requirements.
- Weak/strong down B->S inventory sizing can be reduced by a regime multiplier before lot-size rounding.
- This does not infer fills, route orders, realize PnL, or count cost-basis reduction.
- Focused validation: `python -m py_compile research\trigger_engine.py research\opportunity_lifecycle.py app\dashboard.py tests\test_trigger_engine.py tests\test_opportunity_lifecycle.py tests\test_dashboard_signals.py`; `python -m pytest tests\test_trigger_engine.py tests\test_opportunity_lifecycle.py tests\test_dashboard_signals.py -q --basetemp=pytest_tmp_soft_regime -o cache_dir=pytest_cache_soft_regime` (28 passed; local pytest cache warnings only).

## B/S Lifecycle Diagnostics Stage 1

Validation scope:

- Trigger diagnostics now include `exhaustion_score`, `anchor_type`, `target_reason`, `liquidity_score`, `reason_codes`, and `blocked_reasons`.
- Lifecycle scan emits staged signal states instead of generic `OPEN`, and dashboard marker/detail outputs expose target, invalidation, inventory before/after, reason codes, blocked reasons, and why-not-earlier fields.
- Focused validation covered trigger engine behavior, opportunity lifecycle state transitions, and dashboard signal marker rendering.
- This does not infer fills, route orders, realize PnL, or count cost-basis reduction.

## Button-Gated Research Audit Page

Validation scope:

- `Execution / EOD review` no longer calls scenario evaluation, threshold experiments, model audit, or baseline update review as part of page render.
- `Research / Audit` exposes explicit buttons for scenario evaluation / locked-OOS, locked-OOS threshold experiments, model-change audit, and audit baseline update review.
- Focused validation covered dashboard compile, signal/replay helpers, deployment import, and evaluation rendering tests.
- This changes execution timing only; evaluation logic, locked-OOS hashes, trigger logic, fills, and cost-basis claims are unchanged.

## Compact Data and Account Status Strip

Validation scope:

- The strip summarizes data source grade, broker-confirmed status, latest bar, bar count, and rollup status.
- It returns WARN for research feeds without broker confirmation, BAD for unavailable data, and auto-expands detailed risk sections for BAD data or actionable unconfirmed signals.
- Focused validation covered strip payload status, expansion rules, data quality checks, and dashboard replay helpers.
- This changes presentation hierarchy only; trigger logic, fills, accounting, locked-OOS metrics, and cost-basis claims are unchanged.

## Intraday Decision Priority and Idle Persistence

Validation scope:

- Persisted position state is disabled by default and is not read/written unless the checkbox is enabled.
- The dashboard now renders trading decision and core metrics before secondary analysis/review work.
- Focused validation covered dashboard compile, signal/replay helpers, deployment import, and evaluation rendering tests.
- This changes UI order and state I/O behavior only; trigger logic, fills, accounting, locked-OOS metrics, and cost-basis claims are unchanged.

## Lazy Dashboard Page Split

Validation scope:

- The intraday page now skips execution/research-review panel construction.
- The review page explicitly lazy-loads manual fills, broker reconciliation, journal, closeout, scenario evaluation, locked-OOS experiment, audit, and baseline review panels.
- Focused validation covered dashboard compile, signal/replay helpers, deployment import, and evaluation rendering tests.
- This changes Streamlit runtime organization only; trigger logic, fills, accounting, locked-OOS metrics, and cost-basis claims are unchanged.

## Replay Click Selection Reliability

Validation scope:

- Chart selection now uses local `time_key` payloads and full-height transparent minute rules.
- Focused tests cover parsing local `time_key` selection payloads plus existing replay truncation and nearest-minute behavior.
- This changes only interaction reliability; model logic, evaluation rows, fills, and cost-basis accounting are unchanged.

## Replay Full-Session Chart Context

Validation scope:

- Replay-at-time model input remains truncated to the selected closed minute.
- Price and ratio charts can show the full session as visual context while as-of outputs remain tied to the selected minute.
- Focused validation covered dashboard replay helpers and Yahoo session fallback tests.
- This does not change trigger logic, execution accounting, locked-OOS results, or profitability evidence.

## Yahoo Sparse-Session Fallback

Validation scope:

- If Yahoo `range=1d` has too few closed-minute bars, a 5-day response can be split by exchange date and the latest session with enough bars is selected.
- Focused tests cover sparse latest-day fallback to the prior usable session.
- This changes data selection for display/model input only; it does not alter trigger thresholds, execution accounting, locked-OOS results, or profitability evidence.

## Replay-at-time Model State

Validation scope:

- Chart clicks are captured through a transparent minute-point layer with a named `minute_select` selection.
- The selected time is normalized to the nearest closed minute, and replay uses only `bars` up to that minute before rerunning the trigger engine.
- Focused validation covered bar truncation, nearest-minute selection, chart-event parsing, and existing signal marker behavior.
- This is model-state replay only; no account state, manual fill, broker import, journal, realized PnL, or cost-basis reduction is rewound or inferred.

## Streamlit Width API Maintenance

Validation scope:

- Deprecated `use_container_width=True` dashboard calls were replaced with `width="stretch"`.
- Validation confirmed no `use_container_width` residue in `app/dashboard.py`, successful dashboard compile, and focused dashboard tests passing.
- This maintenance change does not alter trigger logic, fills, accounting, locked-OOS metrics, or cost-basis claims.

## Current Intraday Decision Marker

Validation scope:

- The chart marker is a UI decision-support annotation generated from the current `TradeIntent` on the latest closed minute.
- It is not part of locked-OOS performance evaluation, does not infer fills, and does not create realized PnL or cost-basis reduction.
- Historical lifecycle SB/BS markers remain separate optional scan annotations.
- Focused validation: `python -m py_compile app\dashboard.py tests\test_dashboard_signals.py`; `python -m pytest tests\test_dashboard_signals.py -q --basetemp=pytest_tmp_current_marker -o cache_dir=pytest_cache_current_marker` (4 passed; local pytest cache warnings only).

V1 evaluation compares:

1. no trade baseline;
2. simple S->B baseline;
3. future candidate strategies.

Required metrics are emitted by `core.accounting.EvaluationMetrics`.

Initial synthetic scenarios:

- `mean_revert`: should close a Pair and restore target inventory.
- `one_way_up`: should expose missed-upside tail and ending inventory deficit.
- `low_liquidity`: should usually produce no trade under the amount-ratio filter.

The default fee configuration is intentionally conservative for small 100-share trades. A strategy can produce gross price improvement and still be rejected if the expected round-trip edge does not cover fees and slippage.

## 603236 2026-06-18 Smoke Replay

Assumptions:

- Symbol: 603236, Quectel / 绉昏繙閫氫俊.
- Bankroll proxy: RMB 8,000,000.
- Latest replay close: RMB 52.81.
- Target quantity proxy: 151,400 shares, rounded down to 100-share lots.
- Sellable quantity proxy: 151,400 shares.
- Trade quantity proxy: 15,100 shares.

Results:

- Default conservative configuration: no trade.
- Diagnostic `buyback_deviation=-0.002`: 2 closed S->B pairs, `closed_t_net_pnl=14183.00418`, `ending_quantity_delta=0`, `max_inventory_deviation_duration=51`.

Interpretation: This is a same-day smoke replay, not evidence of strategy validity. It is useful for validating data ingestion, VWAP calculation, fee gating, inventory restoration, and temporary under-allocation metrics.

## 603236 Prompt Scan

Default prompt config, bankroll proxy RMB 8,000,000:

- Latest 15:00 prompt: `HOLD`; reason: after new-T cutoff.
- First scanned first-leg prompt: `SB_OPEN` at 10:14, price 53.99, VWAP deviation 1.1876%.
- Later scanned first-leg prompts: multiple `BS_OPEN` signals as price traded below VWAP with elevated鎴愪氦棰?
- Stateful example: open `SB` at 53.98 produced `SB_CLOSE` at 52.81, gross spread 1.17/share.

## Trigger Engine Smoke

Command:

```powershell
python -m app.cli trigger --symbol 603236 --held-qty 151400 --purchasable-qty 15100 --ignore-fees
```

Observed on 2026-06-18 after close:

- `action_type=NO_TRADE`
- `regime_type=LATE_SESSION`
- blocker: close/restore window has priority.

Interpretation: The engine did not open a new T late in the day, which matches the regime layer rule.

## Korea / Samsung Trigger Smoke

Command:

```powershell
python -m app.cli trigger --data-source yahoo --symbol 005930.KS --held-qty 1000 --purchasable-qty 100 --ignore-fees
```

Expected interpretation:

- Data source should normalize Samsung Electronics common stock to `005930.KS`.
- Korean rules should use 1-share trading unit, 09:15 new-T start, 15:05 latest open time, 15:20 force-restore time, and 15:30 close.
- VWAP diagnostics are based on approximate amount because Yahoo minute bars expose OHLCV but not turnover amount.

Observed in local live-network smoke:

- Command executed successfully.
- `action_type=NO_TRADE`
- `regime_type=MEAN_REVERTING`
- reason: VWAP deviation had not reached the observation threshold.

Interpretation: The Samsung/Yahoo data path and Korean rule profile are callable. This is a connectivity and parsing smoke test only, not evidence that the prompt thresholds are suitable for Samsung.

## Trigger Quality Gate

Validation command:

```powershell
python -m pytest
```

Observed locally:

- `50 passed`.
- Watch-threshold but below-trigger deviation remains `WATCH_SELL_TO_BUY` even when expected net edge is positive.
- Strong deviation with weak turnover confirmation remains `WATCH_SELL_TO_BUY`.
- Existing trigger cases still pass when regime, deviation strength, liquidity, post-cost edge, and inventory constraints all pass.

Interpretation: This is a stricter signal-quality filter for decision support. It is not evidence of profitability and does not replace out-of-sample evaluation.

## Professional Decision Summary

Validation command:

```powershell
python -m pytest
```

Observed locally:

- `52 passed`.
- Trigger and watch-only synthetic intents both produce five separate summary sections.
- The caveats section explicitly states that cost-basis reduction is not realized until both legs close, target inventory is restored, and fees/slippage are deducted.

Interpretation: This improves operator readability only. It is not a performance evaluation and does not support profitability claims.

## Multi-Scenario Evaluation Report

Validation commands:

```powershell
python -m pytest
python -m app.cli evaluate --ignore-fees
```

Observed locally:

- `54 passed`.
- CLI evaluation emitted rows for `mean_revert`, `one_way_up`, and `low_liquidity`.
- Each row includes `no_trade_baseline`, `simple_interpretable_baseline`, `simple_vs_no_trade`, and `trigger_engine_signal`.
- The trigger-engine section states that closed-minute signal scans assume no same-minute fill and do not infer realized PnL.

Interpretation: This is a research comparison report. It improves evaluation hygiene but does not constitute out-of-sample profitability evidence.

## Data-Quality Diagnostics

Validation commands:

```powershell
python -m py_compile research/data_quality.py app/dashboard.py tests/test_data_quality.py
python -m pytest
```

Observed locally:

- `58 passed`.
- Stale live data produces a warning and a confidence downgrade note.
- Sparse/zero-volume data produces coverage and sparse-volume warnings.
- Korea/Yahoo data produces an amount-quality warning because turnover amount is approximated from `close * volume`.
- Recent dense A-share-style data with exchange-like turnover passes as `OK`.

Interpretation: These diagnostics guard the UI against overconfidence in weak data. They are not performance metrics and do not support profitability claims.

## Opportunity Lifecycle Markers

Validation commands:

```powershell
python -m py_compile research/opportunity_lifecycle.py app/dashboard.py tests/test_opportunity_lifecycle.py tests/test_dashboard_signals.py
python -m pytest
```

Observed locally:

- `62 passed`.
- Lifecycle tests cover close-ready, expiry, invalidation blocking, and same-side trigger collapse.
- Dashboard signal marker tests confirm the first trigger remains visible as an `OPEN` lifecycle event.

Interpretation: Lifecycle markers are designed to show whether a signal opportunity is open, close-ready, expired, or blocked. They do not imply an order was filled, do not infer realized PnL, and do not support a cost-basis reduction claim.

## Persistent Position State

Validation commands:

```powershell
python -m py_compile app/position_state.py app/dashboard.py app/cli.py tests/test_cli.py
python -m pytest
```

Observed locally:

- `65 passed`.
- Tests cover JSON position-state round-trip, prompt/monitor context merge from saved state, and explicit CLI argument override precedence.

Interpretation: The persisted state is an operational context bridge between dashboard refreshes and CLI monitoring. It is not broker-confirmed position data and must not be treated as proof of holdings, fills, PnL, or cost-basis reduction.

## Dashboard Evaluation Table

Validation commands:

```powershell
python -m py_compile app/dashboard.py tests/test_dashboard_evaluation.py
python -m pytest
```

Observed locally:

- `67 passed`.
- Dashboard evaluation tests cover flattened table columns for no-trade, simple baseline, trigger diagnostics, and market-aware trade quantity rounding.

Interpretation: The dashboard table renders synthetic scenario comparisons for research hygiene. It compares no-trade, a simple interpretable replay baseline, and trigger-engine signal diagnostics; it is not current-symbol performance evidence and does not support profitability claims.

## Fee Profile Presets

Validation commands:

```powershell
python -m py_compile core/fee_profiles.py app/position_state.py app/cli.py app/dashboard.py tests/test_fee_profiles.py tests/test_cli.py tests/test_dashboard_evaluation.py
python -m pytest
```

Observed locally:

- `76 passed`.
- Tests cover costed default profiles, explicit zero-fee research mode, custom manual config, persisted fee-profile state, and dashboard fee-model selection.

Interpretation: Fee presets reduce accidental zero-cost guidance. They are still assumptions, not broker-confirmed execution data, and do not support profitability or production-validity claims.

## Dataset Registry and Split Enforcement

Validation commands:

```powershell
python -m py_compile research/dataset_registry.py research/evaluation_report.py app/dashboard.py app/cli.py tests/test_dataset_registry.py tests/test_evaluation_report.py tests/test_dashboard_evaluation.py
python -m pytest
```

Observed locally:

- `79 passed`.
- Default synthetic scenarios are registered as `in_sample` only.
- Evaluation reports include `dataset_id`, `dataset_split`, `is_out_of_sample`, and split summary.
- Dashboard evaluation table includes split metadata.
- Unknown/unregistered scenarios are rejected.

Interpretation: Split enforcement improves research hygiene. It does not create an OOS dataset; therefore profitability and production-validity claims remain unsupported.

## 2026-06-20 - Manual fill recorder validation
- Scope: Verified manual fill serialization, duplicate rejection, SB/BS checklist transitions, and CLI manual-fill argument handling.
- Commands: `python -m py_compile app/manual_fills.py app/cli.py app/dashboard.py tests/test_manual_fills.py tests/test_cli_manual_fills.py`; `python -m pytest`.
- Result: 85 passed.
- Evaluation note: Execution accounting still requires broker-confirmed reconciliation in a later step; manual fills are a safer interim source of truth than inferred fills.

## 2026-06-20 - Data source disclosure validation
- Scope: Verified Eastmoney and Yahoo disclosure content and dashboard table structure.
- Commands: `python -m py_compile research/source_disclosure.py app/dashboard.py tests/test_source_disclosure.py`; `python -m pytest`.
- Result: 88 passed.
- Evaluation note: This improves operational risk labeling only. It does not make public quote feeds licensed, broker-confirmed, or sufficient for production trading decisions.

## 2026-06-20 - Manual broker reconciliation validation
- Scope: Verified broker snapshot serialization, matching/understated/overstated reconciliation states, symbol mismatch blocking, CLI snapshot construction, and dashboard table structure.
- Commands: `python -m py_compile app/position_reconciliation.py app/cli.py app/dashboard.py tests/test_position_reconciliation.py tests/test_cli_reconciliation.py tests/test_dashboard_reconciliation.py`; `python -m pytest`.
- Result: 96 passed.
- Evaluation note: Manual reconciliation reduces stale-state risk but is not a broker API. Broker-confirmed imports remain a future improvement.

## 2026-06-20 - Pre-trade ticket validation
- Scope: Verified sell ticket pass case, sellable-quantity blocking, buy cash blocking, price-limit proximity warnings, zero-fee blocking, no-action tickets, and dashboard table structure.
- Commands: `python -m py_compile app/order_ticket.py app/cli.py app/dashboard.py tests/test_order_ticket.py tests/test_dashboard_order_ticket.py`; `python -m pytest`.
- Result: 103 passed.
- Evaluation note: The checklist is an order-entry risk gate only. It does not route orders, confirm fills, or prove strategy profitability.

## 2026-06-20 - Locked OOS dataset validation
- Scope: Registered `oos_000001_20260618_eastmoney` as a real CSV OOS row with SHA-256 lock `f49358b32e3a8904ef5b2251d8a749ff79e9175bbc4d3767c5c643183751dc7d`.
- Commands: `python -m py_compile research/dataset_registry.py research/evaluation_report.py app/cli.py app/dashboard.py tests/test_dataset_registry.py tests/test_evaluation_report.py tests/test_dashboard_evaluation.py`; `python -m pytest`; `python -m app.cli evaluate --locked-oos --target-qty 151400 --settled-sellable-qty 151400 --purchasable-qty 15100 --trade-qty 15100`.
- Result: 106 passed; locked OOS CLI output contained 1 out-of-sample row, 241 bars, `dataset_locked=true`, latest trigger action `NO_TRADE`, trigger count 21, watch count 173, and no realized fills inferred.
- Evaluation note: This is one OOS sample only. It improves regression discipline but does not support profitability or production trading validity claims.

## 2026-06-20 - Execution sensitivity validation
- Scope: Verified positive-edge survival, worse-fill edge exhaustion, no-action behavior, and dashboard table flattening for base/worse/bad/tail slippage bands.
- Commands: `python -m py_compile app/execution_sensitivity.py app/cli.py app/dashboard.py tests/test_execution_sensitivity.py tests/test_dashboard_execution_sensitivity.py`; `python -m pytest`.
- Result: 110 passed.
- Evaluation note: Sensitivity bands are pre-trade execution-risk diagnostics. They do not route orders, confirm fills, or prove profitability.

## 2026-06-20 - Expanded locked OOS validation
- Scope: Added and verified 5 locked OOS rows across 3 symbols and 4 dates: `000001` 2026-06-12 Yahoo, `300750` 2026-06-16 Yahoo, `000858` 2026-06-17 Yahoo, `300750` 2026-06-18 Eastmoney, and `000001` 2026-06-18 Eastmoney.
- Commands: `python -m py_compile research/dataset_registry.py research/evaluation_report.py app/dashboard.py tests/test_dataset_registry.py tests/test_evaluation_report.py tests/test_dashboard_evaluation.py`; `python -m pytest`; `python -m app.cli evaluate --locked-oos --target-qty 151400 --settled-sellable-qty 151400 --purchasable-qty 15100 --trade-qty 15100`.
- Result: 111 passed; locked OOS CLI output contained 5 out-of-sample rows, all `dataset_locked=true`, all hash-checked before evaluation.
- Evaluation note: This improves regression discipline and breadth. It still does not support profitability or production trading validity claims because all rows are public-feed samples and the sample size remains small.

## 2026-06-20 - Model-change audit validation
- Scope: Verified stored baseline loading, unchanged audit `OK` status, threshold-change detection, dashboard table flattening, and CLI audit output.
- Commands: `python -m py_compile research/model_audit.py app/cli.py app/dashboard.py tests/test_model_audit.py tests/test_dashboard_model_audit.py`; `python -m pytest`; `python -m app.cli audit`.
- Result: 116 passed; CLI audit output reported `status=OK`, 5 locked OOS rows, no threshold changes, and no metric changes.
- Evaluation note: Audit status only shows drift versus baseline. It does not support profitability, realized PnL, or production trading validity claims.

## Locked OOS Capture CLI

Validation commands:

```powershell
python -m py_compile research/oos_capture.py app/cli.py tests/test_oos_capture.py tests/test_cli_oos_capture.py
python -m pytest
python -m app.cli capture-oos --source csv --symbol 000001 --date 20260612 --csv datasets/oos/000001_20260612_yahoo_intraday.csv --output-dir .runtime/<capture_oos_smoke> --min-bars 300
```

Observed locally:

- `121 passed`.
- CLI smoke produced a 330-bar normalized CSV.
- Captured SHA-256: `0470e0fce70e2a5dc13c71a3ce659a05ed7665f7452c994d37820a68791c0f3a`.
- The command emitted a `DatasetRecord` snippet and the caveat that manual registry review is still required.

Interpretation: This validates the dataset intake mechanism only. It does not expand the registered OOS set by itself and does not support profitability or production-validity claims.
## Threshold Experiment Runner

Validation commands:

```powershell
python -m py_compile research/threshold_experiments.py app/cli.py tests/test_threshold_experiments.py tests/test_cli_threshold_experiments.py
python -m pytest
python -m app.cli threshold-experiments --experiments more_selective
```

Observed locally:

- `125 passed`.
- `more_selective` produced audit status `REVIEW`.
- Aggregate locked-OOS deltas: `trigger_count=-61`, `watch_count=-105`, `no_trade_count=166`.
- The report note states that the stored baseline is read but never modified.

Interpretation: The runner supports controlled threshold exploration. These are signal-count deltas against a small public-feed locked-OOS set, not realized PnL, profitability evidence, or approval to update the baseline.
## Audit Baseline Update Workflow

Validation commands:

```powershell
python -m py_compile research/model_audit.py app/cli.py app/dashboard.py tests/test_model_audit_baseline_update.py tests/test_cli_baseline_update.py tests/test_dashboard_baseline_update.py
python -m pytest
python -m app.cli audit-baseline-update
```

Observed locally:

- `131 passed`.
- Default CLI preview returned `NO_UPDATE_NEEDED`.
- The preview reported 5 locked OOS rows, 0 threshold changes, and 0 metric changes.
- Test coverage verifies that a drifted temp baseline is not written without the review token and is written only with `APPROVE_LOCKED_OOS_BASELINE_UPDATE`.

Interpretation: This validates baseline governance, not model profitability. Baseline writes are explicit review actions and must not be read as trading approval.
## Dashboard Locked-OOS Threshold Experiment Tables

Validation commands:

```powershell
python -m py_compile app/dashboard.py tests/test_dashboard_threshold_experiments.py
python -m pytest
```

Observed locally:

- `133 passed`.
- Dashboard table builders expose aggregate `delta_trigger_count`, `delta_watch_count`, and `delta_no_trade_count` for each built-in threshold experiment.
- Per-scenario metric deltas are split into `scenario` and `metric` columns so review does not require reading raw JSON.

Interpretation: This improves review usability for threshold experiments. These are signal-count deltas against locked public-feed OOS rows, not execution evidence or profitability validation.
## Professional Intraday Risk-Limit Presets

Validation commands:

```powershell
python -m py_compile research/risk_limits.py research/trigger_engine.py app/position_state.py app/cli.py app/dashboard.py tests/test_risk_limits.py tests/test_trigger_engine_risk_limits.py tests/test_dashboard_risk_limits.py tests/test_cli.py
python -m pytest
python -m app.cli trigger --scenario mean_revert --held-qty 10000 --settled-sellable-qty 10000 --purchasable-qty 10000 --max-t-ratio 0.10 --risk-preset defensive --ignore-fees
```

Observed locally:

- `139 passed`.
- `defensive` caps a 10,000-share target at 500 shares for a single pair under the 10% round-trip turnover and 5% same-day capital-at-risk limits.
- CLI smoke reported `max_wait_minutes=25` for the defensive preset.

Interpretation: Risk presets improve sizing discipline and make risk assumptions explicit. They are not evidence of profitability, fills, or production trading validity.
## Post-Trade Review Validation

Validation commands:

```powershell
python -m py_compile app/post_trade_review.py app/cli.py app/dashboard.py tests/test_post_trade_review.py tests/test_dashboard_post_trade_review.py
python -m pytest
python -m app.cli trigger --scenario mean_revert --held-qty 10000 --settled-sellable-qty 10000 --purchasable-qty 10000 --max-t-ratio 0.10 --risk-preset defensive --ignore-fees
```

Observed locally:

- `145 passed`.
- CLI `trigger` includes `post_trade_review` alongside `pre_trade_order_ticket` and `execution_sensitivity`.
- The no-action smoke returns `post_trade_review.status=NO_ACTION`, confirming no fill is inferred.
- Unit tests cover matching fills, partial/adverse fills, overfills, missing fills, blocked sensitivity, and dashboard table flattening.

Interpretation: This improves execution review hygiene only. It is not out-of-sample performance evidence, does not imply routed orders, and does not support profitability or production-validity claims.

## Live-Session Risk Usage Validation

Validation commands:

```powershell
python -m py_compile app/session_risk.py app/cli.py app/dashboard.py tests/test_session_risk.py tests/test_dashboard_session_risk.py
python -m pytest
python -m app.cli trigger --scenario mean_revert --held-qty 10000 --settled-sellable-qty 10000 --purchasable-qty 10000 --max-t-ratio 0.10 --risk-preset defensive --ignore-fees
```

Observed locally:

- `150 passed`.
- CLI `trigger` includes `live_session_risk_usage` alongside ticket, sensitivity, and post-trade review output.
- The no-fill smoke reports `status=OK`, zero manual turnover, zero open-pair exposure, and defensive limits of 1,000 shares turnover, RMB 5,000 same-day capital at risk, and 25 minutes max open-pair age.
- Unit tests cover closed-pair turnover, turnover limit breach, open exposure plus age breach, session/symbol filtering, and dashboard table flattening.

Interpretation: This improves operational risk hygiene only. It does not infer fills, does not prove execution quality, and does not support profitability or production-validity claims.

## Broker Fill Import Reconciliation Validation

Validation commands:

```powershell
python -m py_compile app/broker_import.py app/cli.py app/dashboard.py tests/test_broker_import.py tests/test_cli_broker_import.py tests/test_dashboard_broker_import.py
python -m pytest
python -m app.cli broker-import --path .runtime\broker_import_smoke\broker.csv --manual-fills-path .runtime\broker_import_smoke\manual_fills.json --symbol 603236
```

Observed locally:

- `157 passed`.
- CLI `broker-import` parses CSV broker fill exports and compares them with manual fills.
- The smoke report returned `status=OK`, `matched_count=1`, `broker_only_count=0`, `manual_only_count=0`, and `ambiguous_count=0`.
- Unit tests cover CSV parsing, JSON parsing, exact matched reconciliation, broker-only/manual-only rows, ambiguous duplicate keys, CLI output, and dashboard table flattening.

Interpretation: This adds broker-confirmation reconciliation scaffolding only. It does not import fills automatically, does not infer pair context, and does not support profitability or production-validity claims.

## Session Execution Journal Validation

Validation commands:

```powershell
python -m py_compile app/execution_journal.py app/cli.py app/dashboard.py tests/test_execution_journal.py tests/test_dashboard_execution_journal.py
python -m pytest --basetemp .runtime\pytest-tmp
python -m app.cli trigger --scenario mean_revert --held-qty 10000 --settled-sellable-qty 10000 --purchasable-qty 10000 --max-t-ratio 0.10 --risk-preset defensive --ignore-fees
```

Observed locally:

- `161 passed`; pytest emitted cache warnings because `.pytest_cache` is not writable in this environment.
- CLI `trigger` includes `execution_journal` and `broker_fill_reconciliation`.
- The no-action smoke returned `execution_journal.status=OK` with signal, pre-trade ticket, manual fill, broker reconciliation, post-trade review, and risk usage stages.
- Unit tests cover a clean confirmed fill chain, missing-fill warning chain, risk-blocked chain, and dashboard journal table flattening.

Interpretation: This improves auditability of the execution workflow only. It does not infer broker execution, update accounting, or support profitability or production-validity claims.

## Broker Fill Promotion Smoke

Command pattern:

```powershell
python -m app.cli broker-promote --path .runtime\broker_promote_smoke\broker.csv --manual-fills-path .runtime\broker_promote_smoke\manual_fills.json --broker-fill-id bf-promote --pair-id 603236-SB-53p9800-100
python -m app.cli broker-promote --path .runtime\broker_promote_smoke\broker.csv --manual-fills-path .runtime\broker_promote_smoke\manual_fills.json --broker-fill-id bf-promote --pair-id 603236-SB-53p9800-100 --review-token APPROVE_BROKER_FILL_PROMOTION
```

Observed locally on 2026-06-20:

- Without the review token, promotion returned `status=REVIEW_REQUIRED` and did not write a manual fill.
- With `APPROVE_BROKER_FILL_PROMOTION`, promotion returned `status=READY` and wrote one manual fill carrying broker fees, slippage, pair_id, and broker provenance.

Interpretation: This validates the operator-review guardrail for broker-confirmed rows. It is not strategy-performance evidence and does not imply realized cost-basis reduction unless the full pair lifecycle and inventory restoration checks also pass.

## Persisted Execution Journal Smoke

Command:

```powershell
python -m app.cli trigger --scenario mean_revert --held-qty 10000 --settled-sellable-qty 10000 --purchasable-qty 10000 --max-t-ratio 0.10 --risk-preset defensive --ignore-fees
```

Observed locally on 2026-06-20:

- CLI output included `execution_journal_path=.runtime\execution_journals\journal-scenario_mean_revert-2026-01-02T093700.json`.
- CLI output included `recent_execution_journals` with the saved journal ID, status, timestamp, and path.
- Full validation passed with 171 tests.

Interpretation: Session journals now persist across runs and can be compared during end-of-day review. This is an audit-trail improvement, not performance evidence or an accounting trigger.
## End-of-Day Session Closeout Smoke

Command:

```powershell
python -m app.cli trigger --scenario mean_revert --held-qty 10000 --settled-sellable-qty 10000 --purchasable-qty 10000 --max-t-ratio 0.10 --risk-preset defensive --ignore-fees --no-position-state
```

Observed locally on 2026-06-20:

- CLI output included `session_closeout`.
- With no manual fills, `session_closeout.status=NO_ACTION`, `countable=false`, and `countable_cost_basis_reduction=0.0`.
- Unit tests cover all-gates-pass countable reduction, missing broker reconciliation, open inventory/risk breach, no-fill no-action state, dashboard table flattening, and CLI trigger output.
- Full validation passed with 177 tests.

Interpretation: Closeout now gates cost-basis accounting on execution evidence rather than signals. This is an accounting hygiene improvement, not a profitability claim.
## Compact End-of-Day Review Smoke

Command:

```powershell
python -m app.cli trigger --scenario mean_revert --held-qty 10000 --settled-sellable-qty 10000 --purchasable-qty 10000 --max-t-ratio 0.10 --risk-preset defensive --ignore-fees --no-position-state
```

Observed locally on 2026-06-20:

- CLI output included `end_of_day_review`.
- No-fill smoke returned `end_of_day_review.status=NO_ACTION`, `closeout_status=NO_ACTION`, `recent_journal_count=1`, latest journal status `OK`, and `countable_cost_basis_reduction=0.0`.
- Unit tests cover clean review, blocked persisted journal, no persisted journal, dashboard table flattening, and CLI trigger output.
- Full validation passed with 182 tests.

Interpretation: Compact EOD review improves audit usability by linking closeout and recent persisted journals. It is not execution proof, not performance evidence, and not an accounting override.
## Per-Pair Closeout Attribution Smoke

Command:

```powershell
python -m app.cli trigger --scenario mean_revert --held-qty 10000 --settled-sellable-qty 10000 --purchasable-qty 10000 --max-t-ratio 0.10 --risk-preset defensive --ignore-fees --no-position-state
```

Observed locally on 2026-06-20:

- CLI output included `session_closeout.pair_attributions`.
- No-fill smoke returned an empty pair attribution array, which matches `NO_ACTION` closeout semantics.
- Unit tests cover a mixed closed/open pair set, broker matched counts, net cash after fees/slippage, blocking reasons, and dashboard table flattening.
- Full validation passed with 184 tests.

Interpretation: Pair attribution improves EOD review detail but remains evidence organization only. It does not infer fills or override closeout gates.
## Reviewed Closeout Signoff Export

Validation commands:

```powershell
python -m py_compile app\closeout_signoff.py app\cli.py app\dashboard.py tests\test_closeout_signoff.py tests\test_dashboard_closeout_signoff.py tests\test_cli.py
python -m pytest tests\test_closeout_signoff.py tests\test_dashboard_closeout_signoff.py tests\test_cli.py tests\test_session_closeout.py tests\test_end_of_day_review.py -q --basetemp=.runtime\pytest-tmp-focused -o cache_dir=.runtime\pytest-cache-focused
python -m pytest -q --basetemp=.runtime\pytest-tmp-full -o cache_dir=.runtime\pytest-cache-full
python -m app.cli trigger --scenario mean_revert --held-qty 10000 --settled-sellable-qty 10000 --purchasable-qty 10000 --max-t-ratio 0.10 --risk-preset defensive --ignore-fees --no-position-state --closeout-signoff-review-token APPROVE_EOD_CLOSEOUT_SIGNOFF --closeout-signoff-note "smoke reviewed no-action closeout" --closeout-signoff-dir .runtime\closeout_signoff_smoke
```

Observed locally:

- Focused tests: `22 passed`.
- Full test suite: `190 passed`.
- CLI smoke wrote `.runtime\closeout_signoff_smoke\eod-signoff-scenario-mean_revert-2026-01-02.json` and returned `closeout_signoff_preview.status=READY`.

Interpretation: The signoff export provides reviewed EOD audit continuity only. It does not route orders, infer fills, mutate accounting, or support profitability claims.

## Streamlit Cloud Import Path Fix

Validation commands:

```powershell
python -m py_compile app\dashboard.py tests\test_dashboard_deployment_import.py
python -c "import os, sys; os.chdir('app'); sys.path=[os.getcwd()]+[p for p in sys.path if p != '']; import dashboard; print('dashboard import ok')"
python -m pytest tests\test_dashboard_deployment_import.py tests\test_dashboard_evaluation.py -q --basetemp=.runtime\pytest-tmp-deploy-import -o cache_dir=.runtime\pytest-cache-deploy-import
```

Observed locally:

- Dashboard py_compile passed.
- Cloud-style `app/` entrypoint import returned `dashboard import ok`.
- Focused deployment/dashboard tests: `7 passed`.
- Full suite was attempted but blocked by local Windows pytest temp-root permissions during `tmp_path` fixture setup.

Interpretation: This validates the deployment import failure fix. It is not a model-performance evaluation and does not support profitability claims.

## Streamlit Cloud Locked-OOS Hash Fix

Validation commands:

```powershell
python -m py_compile research\dataset_registry.py research\evaluation_report.py app\dashboard.py tests\test_dataset_registry.py tests\test_evaluation_report.py
python -m pytest tests\test_dataset_registry.py tests\test_evaluation_report.py tests\test_dashboard_evaluation.py -q --basetemp=pytest_tmp_dataset_hash_fix -o cache_dir=pytest_cache_dataset_hash_fix
python -m app.cli evaluate --locked-oos --target-qty 151400 --settled-sellable-qty 151400 --purchasable-qty 15100 --trade-qty 15100
```

Observed locally:

- Focused dataset/evaluation/dashboard tests: `14 passed`.
- Locked-OOS CLI evaluation completed all five registered rows and emitted LF-normalized content hashes.

Interpretation: This validates cross-platform locked dataset verification. It does not expand OOS coverage or support profitability claims.

## Dashboard Research Panel Resilience

Validation commands:

```powershell
python -m py_compile app\dashboard.py tests\test_dashboard_evaluation.py
python -m pytest tests\test_dashboard_evaluation.py -q --basetemp=pytest_tmp_eval_resilience -o cache_dir=pytest_cache_eval_resilience
python -m app.cli evaluate --locked-oos --target-qty 151400 --settled-sellable-qty 151400 --purchasable-qty 15100 --trade-qty 15100
```

Observed locally:

- Dashboard evaluation tests: `7 passed`.
- Locked-OOS CLI evaluation completed all five registered rows.

Interpretation: This validates dashboard resilience when a research panel fails. It does not change trading logic or expand OOS evidence.

## Streamlit Cloud Stale Module Cache Fix

Validation commands:

```powershell
python -m py_compile app\dashboard.py tests\test_dashboard_deployment_import.py
python -m pytest tests\test_dashboard_deployment_import.py tests\test_dashboard_evaluation.py -q --basetemp=pytest_tmp_deploy_cache_refresh -o cache_dir=pytest_cache_deploy_cache_refresh
python -m app.cli evaluate --locked-oos --target-qty 151400 --settled-sellable-qty 151400 --purchasable-qty 15100 --trade-qty 15100
```

Observed locally:

- Deployment/dashboard tests: `9 passed`.
- Locked-OOS CLI evaluation completed all five registered rows.

Interpretation: This validates deployment module freshness. It does not add OOS evidence or change model behavior.
