# Evaluation

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
