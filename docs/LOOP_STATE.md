# Loop State

## Iteration 0

- current_baseline: empty workspace, no Git repo, Python 3.12.8, pytest 8.3.4.
- hypothesis: build a minimal but runnable V1 core before UI to avoid false strategy claims.
- expected_result: tests pass; synthetic mean-reversion scenario closes one S->B Pair; one-way-up scenario reports unclosed Pair and missed upside tail.
- files_changed: initial project skeleton under `core/`, `data/`, `research/`, `app/`, `tests/`, `docs/`, plus `README.md`, `AGENTS.md`, `pyproject.toml`.
- commands_run: `git init`; `python -m pytest`; default CLI replay.
- test_result: 15 passed.
- metric_result: default `mean_revert` closed one Pair but produced `closed_t_net_pnl=-6.72532`, exposing missing cost gate.
- observed_failure: none yet.
- decision: MODIFY.
- next_highest_value_question: does next-open fill plus default fees produce conservative but usable S->B baseline metrics?
- known_blockers: official rule and fee source verification still pending.

## Iteration 1

- current_baseline: initial V1 skeleton with 15 passing tests; default CLI showed a closed Pair with negative net PnL.
- hypothesis: cost gating before opening a Pair prevents false positive "successful T" labels.
- expected_result: default fee model blocks weak-edge synthetic trade; zero-fee tests still close Pair for mechanics verification.
- files_changed: `research/replay.py`, `research/fills.py`, `tests/test_replay.py`, docs.
- commands_run: `python -m pytest`; default `mean_revert` CLI replay; default `one_way_up` CLI replay.
- test_result: 17 passed.
- metric_result: default fees suppress weak-edge trade; `trade_count=0`, `excess_pnl_vs_hold=0`.
- observed_failure: closed Pair under default fees produced `closed_t_net_pnl=-6.72532`.
- decision: KEEP.
- next_highest_value_question: does cost gating preserve no-future replay behavior while preventing cost-negative trades?
- known_blockers: official rule and fee source verification still pending.

## Iteration 2

- current_baseline: default fees correctly suppress weak-edge synthetic trades.
- hypothesis: exposing fee assumptions through CLI improves auditability and reproducibility.
- expected_result: CLI can run default conservative replay and explicit zero-fee mechanics replay.
- files_changed: `app/cli.py`, `tests/test_cli.py`, `README.md`, docs.
- commands_run: `python -m pytest`; zero-fee `mean_revert` CLI replay; zero-fee `one_way_up` CLI replay.
- test_result: 18 passed.
- metric_result: zero-fee `mean_revert` closed one Pair with `closed_t_net_pnl=4.0`; zero-fee `one_way_up` left one open Pair with `excess_pnl_vs_hold=-18.0`, `missed_upside_tail=18.0`, and `ending_quantity_delta=-100`.
- observed_failure: no CLI path to reproduce low-cost research scenarios.
- decision: KEEP.
- next_highest_value_question: can the CLI report clearly distinguish fee-blocked no-trade from low-fee mechanical closed Pair?
- known_blockers: official rule and fee source verification still pending.

## Iteration 4

- current_baseline: V1 supports synthetic and CSV replay only.
- hypothesis: adding a real minute-bar adapter enables immediate validation once a stock code is supplied.
- expected_result: parser tests pass; CLI accepts `--symbol` without changing synthetic behavior.
- files_changed: `data/eastmoney.py`, `app/cli.py`, `tests/test_eastmoney.py`, `README.md`, docs.
- commands_run: `python -m pytest`.
- test_result: 20 passed.
- metric_result: pending user stock code.
- observed_failure: user asked whether a stock code is needed for today live validation; current CLI had no symbol path.
- decision: KEEP.
- next_highest_value_question: which user-selected stock and inventory assumptions should be used for today's smoke replay?
- known_blockers: user stock code and real holding/fee assumptions not yet provided.

## Iteration 5

- current_baseline: `--symbol 603236` could fetch 241 bars, but VWAP diagnostics showed an impossible VWAP near 5325.
- hypothesis: Eastmoney reports minute volume in hands, so the adapter must convert to shares.
- expected_result: VWAP returns to price scale and strategy diagnostics become meaningful.
- files_changed: `data/eastmoney.py`, `tests/test_eastmoney.py`, docs.
- commands_run: `python -m pytest`; `python -m app.cli replay --symbol 603236 --target-qty 151400 --settled-sellable-qty 151400 --trade-qty 15100 --buyback-deviation -0.002`; default 603236 replay.
- test_result: 21 passed.
- metric_result: default 603236 replay produced no trade; 0.2% buyback diagnostic closed 2 pairs, `closed_t_net_pnl=14183.00418`, `ending_quantity_delta=0`, `max_inventory_deviation=15100`, `max_inventory_deviation_duration=51`.
- observed_failure: amount divided by unconverted volume inflated VWAP by 100x.
- decision: KEEP.
- next_highest_value_question: after VWAP fix, does 603236 today still produce no-trade, closed trade, or open sell-fly risk?
- known_blockers: actual current sellable shares and broker fee schedule still unknown.

## Iteration 6

- current_baseline: real-data diagnostics are price-scale correct, but inventory-deviation duration is based on fill snapshots.
- hypothesis: duration must count replay minutes to avoid understating temporary under-allocation risk.
- expected_result: tests pass and `max_inventory_deviation_duration` increases for multi-minute open Pair scenarios.
- files_changed: `core/inventory_ledger.py`, `research/replay.py`, `tests/test_replay.py`, docs.
- commands_run: pending `python -m pytest`; rerun 603236 replay.
- test_result: pending.
- metric_result: pending.
- observed_failure: 603236 replay showed max deviation duration of 1 even when a Pair stayed open for many minutes.
- decision: MODIFY.
- next_highest_value_question: with duration fixed, are today's 603236 candidate trades still acceptable after under-allocation time is considered?
- known_blockers: actual current sellable shares and broker fee schedule still unknown.

## Iteration 7

- current_baseline: replay can validate completed S->B, but user wants intraday BS/SB prompts without fee gating.
- hypothesis: a stateless prompt layer can flag first-leg SB/BS opportunities while keeping accounting conservative.
- expected_result: CLI `prompt` emits `SB_OPEN`, `BS_OPEN`, or `HOLD`; tests cover both directions.
- files_changed: `research/prompts.py`, `app/cli.py`, `tests/test_prompts.py`, README and docs.
- commands_run: `python -m pytest`; `python -m app.cli prompt --symbol 603236 --bankroll 8000000 --scan --max-prompts 8`; `python -m app.cli prompt --symbol 603236 --bankroll 8000000 --open-pair-side SB --open-pair-price 53.98 --open-pair-qty 15100`.
- test_result: 28 passed.
- metric_result: latest 603236 prompt was `HOLD` because latest bar was 15:00; scan found `SB_OPEN` at 10:14 and several `BS_OPEN` prompts during the later VWAP discount; open SB example produced `SB_CLOSE` with gross spread 1.17/share.
- observed_failure: previous CLI could only replay, not answer "can I do BS or SB now?"
- decision: KEEP.
- next_highest_value_question: what thresholds avoid over-alerting while still catching useful 603236 intraday swings?
- known_blockers: current real cash balance for BS remains unknown unless user provides `--cash`.

## Iteration 8

- current_baseline: stateless prompt layer can issue first-leg SB/BS prompts.
- hypothesis: prompt layer must prioritize open Pair close prompts when an open Pair is supplied.
- expected_result: CLI can produce `SB_CLOSE`/`BS_CLOSE`; tests cover both close directions.
- files_changed: `research/prompts.py`, `app/cli.py`, `tests/test_prompts.py`, README and docs.
- commands_run: `python -m pytest`; stateful 603236 prompt.
- test_result: 28 passed.
- metric_result: example open SB at 53.98 produced `SB_CLOSE` at 52.81 with gross spread 1.17/share.
- observed_failure: parallel Eastmoney requests can disconnect; adapter now retries up to 3 times.
- decision: KEEP.
- next_highest_value_question: should alerts be pushed automatically on a timer or manually polled by CLI?
- known_blockers: no persistent live position state store yet.

## Iteration 9

- current_baseline: user can manually run `prompt` to see current SB/BS state.
- hypothesis: continuous monitoring plus phone push makes the system practical during market hours.
- expected_result: `monitor` loops, fetches latest bars, de-duplicates alerts, and sends non-HOLD prompts to a configured notifier.
- files_changed: `app/cli.py`, `app/notifications.py`, `app/monitoring.py`, `tests/test_notifications.py`, README and docs.
- commands_run: `python -m pytest`; `python -m app.cli monitor --symbol 603236 --bankroll 8000000 --once --notify-provider console`; `python -m app.cli monitor --symbol 603236 --bankroll 8000000 --open-pair-side SB --open-pair-price 53.98 --open-pair-qty 15100 --once --notify-provider console`.
- test_result: 30 passed.
- metric_result: normal latest run produced `HOLD`; open-SB state produced `SB_CLOSE` and emitted a console notification payload.
- observed_failure: no automated alerting path before this iteration.
- decision: KEEP.
- next_highest_value_question: which push provider token should be configured for the user's phone?
- known_blockers: phone push requires user-provided Bark/PushPlus/webhook token.

## Iteration 10

- current_baseline: CLI prompt/monitor exists, but UI is not convenient for new users and trigger logic is still partly single-indicator driven.
- hypothesis: a Streamlit dashboard backed by a three-layer TriggerEngine improves usability and reduces false single-indicator triggers.
- expected_result: UI accepts stock code, held shares, purchasable shares; engine outputs only canonical TradeIntent action types.
- files_changed: `research/trigger_engine.py`, `app/dashboard.py`, `app/cli.py`, `tests/test_trigger_engine.py`, README and docs.
- commands_run: `python -m pytest`; `python -m py_compile app/dashboard.py app/cli.py research/trigger_engine.py`; `python -m app.cli trigger --symbol 603236 --held-qty 151400 --purchasable-qty 15100 --ignore-fees`; Streamlit foreground startup smoke.
- test_result: 42 passed.
- metric_result: 603236 after close returned `NO_TRADE` with `regime_type=LATE_SESSION`.
- observed_failure: detached Streamlit background launch is cleaned up by the tool environment; foreground Streamlit startup succeeded and printed Local URL.
- decision: KEEP.
- next_highest_value_question: persist user position/open-pair state across Streamlit refreshes.
- known_blockers: no persistent position state store yet; real push/mobile integration still requires token.

## Iteration 11

- current_baseline: Streamlit and CLI trigger support A-share Eastmoney minute data only.
- hypothesis: adding a Yahoo Finance minute adapter plus market-specific rules lets the same trigger engine prompt Korean stocks such as Samsung Electronics without changing core accounting semantics.
- expected_result: Streamlit can select Korea/Yahoo, normalize Samsung aliases to `005930.KS`, and apply 1-share lot size with a 15:30 close.
- files_changed: `data/yahoo.py`, `app/dashboard.py`, `app/cli.py`, `research/trigger_engine.py`, `tests/test_yahoo.py`, README and docs.
- commands_run: `python -m pytest`; `python -m py_compile app/dashboard.py app/cli.py research/trigger_engine.py data/yahoo.py`; `python -m app.cli trigger --data-source yahoo --symbol 005930.KS --held-qty 1000 --purchasable-qty 100 --ignore-fees`.
- test_result: 45 passed.
- metric_result: live Yahoo smoke returned `NO_TRADE` for `005930.KS`; after dropping a non-minute-aligned current bar, regime was `MEAN_REVERTING` and deviation had not reached the observation threshold.
- observed_failure: user asked whether a Korean Samsung holding can be prompted; current data source selector had no non-A-share route.
- decision: KEEP.
- next_highest_value_question: should Yahoo live quotes be replaced with a licensed Korean market data source for production use?
- known_blockers: Yahoo has no turnover amount field, so VWAP uses an approximation; Korean broker fee/tax/FX constraints are not yet modeled.

## Iteration 12

- current_baseline: Streamlit shows absolute price lines and raw JSON for the three trigger layers.
- hypothesis: ratio-first market diagnostics and reader-friendly layer cards make the intraday prompt easier to interpret during live trading.
- expected_result: UI shows prominent percent metrics, a zero-suppressed price chart, a percent chart for open/VWAP deviation, and readable Regime/Deviation/Inventory cards before raw JSON.
- files_changed: `app/dashboard.py`, `requirements.txt`, docs.
- commands_run: `python -m pytest`; `python -m py_compile app/dashboard.py`; `python -c "import app.dashboard; print('dashboard import ok')"`.
- test_result: 45 passed.
- metric_result: dashboard import succeeded; UI now renders ratio metrics and reader-friendly layer cards.
- observed_failure: user reported that ratio display was not obvious and three-layer output was not reader friendly.
- decision: KEEP.
- next_highest_value_question: should the UI persist open Pair state and show an explicit close checklist after a trigger?
- known_blockers: browser automation plugin is currently unavailable in this environment, so UI verification relies on compile/import and manual browser refresh.

## Iteration 13

- current_baseline: Streamlit shows current `TradeIntent`, but the intraday chart does not show when earlier SB/BS prompts appeared.
- hypothesis: scanning each closed minute with the same TriggerEngine and overlaying prompt markers on the chart makes signal timing visible without claiming simulated executions.
- expected_result: price chart shows small watch markers and labeled trigger markers for SB/BS, plus a signal detail table.
- files_changed: `app/dashboard.py`, `tests/test_dashboard_signals.py`, docs.
- commands_run: `python -m pytest`; `python -m py_compile app/dashboard.py`.
- test_result: 47 passed.
- metric_result: dashboard signal scan test finds an SB trigger in a synthetic intraday path and ignores no-trade points.
- observed_failure: user asked to mark each timepoint's BS/SB prompt directly inside the chart.
- decision: KEEP.
- next_highest_value_question: add stateful pair simulation so the chart can distinguish first-leg prompts from subsequent close/restore prompts.
- known_blockers: current markers are stateless prompt snapshots, not executed fills or proof of cost-basis reduction.

## Iteration 14

- current_baseline: chart signal markers are generated for every minute that satisfies the same SB/BS condition.
- hypothesis: continuous same-direction prompts represent one opportunity window, not separate opportunities, so the UI should collapse them by default.
- expected_result: chart defaults to trigger-only markers and merges same-direction signals within a configurable cooldown window.
- files_changed: `app/dashboard.py`, `tests/test_dashboard_signals.py`, docs.
- commands_run: `python -m pytest`; `python -m py_compile app/dashboard.py`; `python -c "import app.dashboard; print('dashboard import ok')"`.
- test_result: 48 passed.
- metric_result: continuous synthetic SB triggers collapse to one `SB` marker.
- observed_failure: user noted the chart showed too many prompts and questioned whether there were really that many opportunities.
- decision: KEEP.
- next_highest_value_question: add stateful opportunity lifecycle tracking so one marker can show open/close/expired status.
- known_blockers: current chart still marks prompt opportunities, not actual executed Pair PnL.

## Iteration 15

- current_baseline: dashboard markers are de-duplicated, but trigger eligibility still allowed watch-level deviations to reach inventory execution if net edge was positive.
- hypothesis: a professional decision-support app should require trigger-level deviation strength, liquidity confirmation, and post-cost edge before issuing an actionable trigger.
- expected_result: weak-but-positive setups remain `WATCH_*`; only signals that pass all quality gates can become `TRIGGER_*`.
- files_changed: `research/trigger_engine.py`, `tests/test_trigger_engine.py`, `tests/test_dashboard_signals.py`, `TODO.md`, docs.
- commands_run: `python -m py_compile research/trigger_engine.py tests/test_trigger_engine.py app/dashboard.py`; `python -m pytest`.
- test_result: 50 passed.
- metric_result: synthetic tests now distinguish watch-threshold deviations, trigger-threshold deviations, and weak-liquidity deviations.
- observed_failure: Windows text rewrites exposed broken non-ASCII prompt strings in `trigger_engine.py`; those strings were converted to ASCII to stabilize validation.
- decision: KEEP.
- next_highest_value_question: can the UI summarize recommendation, evidence, invalidation, position impact, and caveats in a trader-readable block?
- known_blockers: no out-of-sample dataset has been defined, so no profitability or production-validity claim is supported.

## Iteration 16

- current_baseline: the engine returns a detailed `TradeIntent`, but the UI still mixes action, evidence, invalidation, position impact, and caveats across metric blocks and layer cards.
- hypothesis: a professional summary block improves trader usability by separating the immediate recommendation from evidence, invalidation, inventory impact, and caveats.
- expected_result: dashboard shows a structured summary before lower-level diagnostics, and the summary builder is reusable and test-covered.
- files_changed: `research/decision_summary.py`, `app/dashboard.py`, `tests/test_decision_summary.py`, `TODO.md`, docs.
- commands_run: `python -m py_compile research/decision_summary.py app/dashboard.py tests/test_decision_summary.py`; `python -m pytest`.
- test_result: 52 passed.
- metric_result: executable and watch-only synthetic intents both produce five summary sections: recommendation, evidence, invalidation, position impact, and caveats.
- observed_failure: none.
- decision: KEEP.
- next_highest_value_question: can replay/evaluation reporting compare trigger-engine behavior against no-trade and simple interpretable baselines over multiple scenarios?
- known_blockers: no out-of-sample dataset has been defined, so no profitability or production-validity claim is supported.

## Iteration 17

- current_baseline: replay can compare a simple S->B baseline to no-trade one scenario at a time, while trigger-engine behavior is inspected separately as latest intents.
- hypothesis: a professional research app needs one report that compares no-trade, a simple interpretable baseline, and trigger-engine signal diagnostics across multiple scenarios.
- expected_result: report covers `mean_revert`, `one_way_up`, and `low_liquidity`; no-trade baseline is explicit; simple S->B replay metrics are included; trigger-engine output is clearly labeled as signal-only.
- files_changed: `research/evaluation_report.py`, `app/cli.py`, `tests/test_evaluation_report.py`, `TODO.md`, docs.
- commands_run: `python -m py_compile research/evaluation_report.py app/cli.py tests/test_evaluation_report.py`; `python -m pytest`; `python -m app.cli evaluate --ignore-fees`.
- test_result: 54 passed.
- metric_result: CLI evaluation emitted three scenario rows. `mean_revert` simple baseline closed a positive net pair under zero fees; `one_way_up` exposed unclosed-pair sell-fly risk; `low_liquidity` stayed no-trade.
- observed_failure: none.
- decision: KEEP.
- next_highest_value_question: can the dashboard make stale, sparse, or approximate data quality visible before confidence is interpreted?
- known_blockers: no out-of-sample dataset has been defined, so no profitability or production-validity claim is supported.

## Iteration 18

- current_baseline: dashboard showed data source captions, but stale, sparse, and approximate data could still sit above high-confidence-looking decision output.
- hypothesis: data-quality diagnostics must be explicit and rendered before the decision summary so users downgrade confidence before interpreting any signal.
- expected_result: dashboard displays a data-quality rollup with stale-data, coverage, sparse-volume, and amount-quality checks; Yahoo/Korea turnover approximation is shown as a warning.
- files_changed: `research/data_quality.py`, `app/dashboard.py`, `tests/test_data_quality.py`, `TODO.md`, docs.
- commands_run: `python -m py_compile research/data_quality.py app/dashboard.py tests/test_data_quality.py`; `python -m pytest`.
- test_result: 58 passed.
- metric_result: tests cover stale live data, sparse/zero-volume data, Yahoo turnover approximation, and recent dense exchange-turnover data.
- observed_failure: none.
- decision: KEEP.
- next_highest_value_question: can chart markers represent a stateful opportunity lifecycle without implying unverified fills or realized PnL?
- known_blockers: no out-of-sample dataset has been defined, so no profitability or production-validity claim is supported.

## Iteration 19

- current_baseline: dashboard chart markers show de-duplicated trigger snapshots but not the later state of an opportunity window.
- hypothesis: a stateful lifecycle scan can mark open, close-ready, expired, and blocked states without implying execution or realized PnL.
- expected_result: dashboard marker rows include lifecycle state and caveat text; tests cover close-ready, expiry, invalidation blocking, and same-side trigger collapse.
- files_changed: `research/opportunity_lifecycle.py`, `app/dashboard.py`, `tests/test_opportunity_lifecycle.py`, `tests/test_dashboard_signals.py`, `TODO.md`, docs.
- commands_run: `python -m py_compile research/opportunity_lifecycle.py app/dashboard.py tests/test_opportunity_lifecycle.py tests/test_dashboard_signals.py`; `python -m pytest`.
- test_result: 62 passed.
- metric_result: lifecycle tests cover close-ready, expiry, invalidation blocking, and same-side trigger collapse.
- observed_failure: dashboard import for lifecycle scanner was initially missing; fixed and revalidated.
- decision: KEEP.
- next_highest_value_question: can persistent position/open-pair state let refreshes preserve the user's actual inventory context?
- known_blockers: no out-of-sample dataset has been defined, so no profitability or production-validity claim is supported.

## Iteration 20

- current_baseline: dashboard inputs are not persisted to a shared runtime state, so monitor/CLI commands can drift from the user-entered inventory context.
- hypothesis: a small JSON position-state store can make dashboard refreshes and CLI monitoring share the same symbol, inventory, sizing, and open-pair context while preserving explicit CLI overrides.
- expected_result: dashboard writes `.runtime/position_state.json`; CLI prompt/monitor/trigger read it unless `--no-position-state` is set; tests cover JSON round-trip and override behavior.
- files_changed: `app/position_state.py`, `app/dashboard.py`, `app/cli.py`, `tests/test_cli.py`, `.gitignore`, `TODO.md`, docs.
- commands_run: `python -m py_compile app/position_state.py app/dashboard.py app/cli.py tests/test_cli.py`; `python -m pytest`.
- test_result: 65 passed.
- metric_result: persistence tests cover JSON round-trip, prompt/monitor context merge, and explicit CLI override precedence.
- observed_failure: `copy` import was initially missing in `app/cli.py`; fixed and revalidated.
- decision: KEEP.
- next_highest_value_question: can the dashboard render evaluation scenario comparisons directly in the app?
- known_blockers: no out-of-sample dataset has been defined, so no profitability or production-validity claim is supported.

## Iteration 21

- current_baseline: scenario evaluation exists in CLI/JSON form, but the dashboard does not render the comparison table for users.
- hypothesis: rendering no-trade, simple S->B replay, and trigger-engine signal diagnostics side by side in the dashboard improves research hygiene during live review.
- expected_result: dashboard shows a scenario evaluation dataframe with explicit caveats; tests cover table flattening and market-aware trade quantity rounding.
- files_changed: `app/dashboard.py`, `tests/test_dashboard_evaluation.py`, `TODO.md`, docs.
- commands_run: `python -m py_compile app/dashboard.py tests/test_dashboard_evaluation.py`; `python -m pytest`.
- test_result: 67 passed.
- metric_result: dashboard evaluation tests cover table flattening and market-aware trade quantity rounding.
- observed_failure: `TODO.md` still contained the already-completed persistent-state item; removed it while completing this dashboard evaluation item.
- decision: KEEP.
- next_highest_value_question: can broker/user fee profile presets prevent accidental zero-fee live guidance?
- known_blockers: no out-of-sample dataset has been defined, so no profitability or production-validity claim is supported.

## Iteration 22

- current_baseline: dashboard and CLI could still default to zero-fee assumptions through the old `ignore_fees` UI/state path, making live guidance too easy to interpret without costs.
- hypothesis: named broker/user fee profiles with a costed default and explicit zero-fee research mode reduce accidental cost-free live guidance.
- expected_result: dashboard exposes fee profile presets and custom manual rates; CLI exposes `--fee-profile`; persisted position state stores the selected profile; zero-fee is only selected through `zero_fee_research` or explicit `--ignore-fees`; tests cover default costed behavior and explicit zero mode.
- files_changed: `core/fee_profiles.py`, `app/position_state.py`, `app/cli.py`, `app/dashboard.py`, `tests/test_fee_profiles.py`, `tests/test_cli.py`, `tests/test_dashboard_evaluation.py`, `TODO.md`, docs.
- commands_run: `python -m py_compile core/fee_profiles.py app/position_state.py app/cli.py app/dashboard.py tests/test_fee_profiles.py tests/test_cli.py tests/test_dashboard_evaluation.py`; `python -m pytest`.
- test_result: 76 passed.
- metric_result: fee-profile tests cover non-zero defaults, explicit zero-fee research mode, custom manual config, persisted profile state, and dashboard fee-model selection.
- observed_failure: dashboard initially missed the fee-profile import and `_scan_signal_markers` signature update; both were fixed and revalidated.
- decision: KEEP.
- next_highest_value_question: can an out-of-sample dataset registry prevent future performance claims from mixing research and validation periods?
- known_blockers: no out-of-sample dataset has been defined, so no profitability or production-validity claim is supported.

## Iteration 23

- current_baseline: scenario evaluation rows were synthetic comparisons without enforced dataset split labels.
- hypothesis: a dataset registry with required split metadata prevents future performance tables from mixing research/in-sample rows with true out-of-sample validation rows.
- expected_result: every evaluation row includes `dataset_id`, `dataset_split`, `is_out_of_sample`, and registry notes; unregistered scenarios fail; dashboard table displays split metadata.
- files_changed: `research/dataset_registry.py`, `research/evaluation_report.py`, `app/dashboard.py`, `tests/test_dataset_registry.py`, `tests/test_evaluation_report.py`, `tests/test_dashboard_evaluation.py`, `TODO.md`, docs.
- commands_run: `python -m py_compile research/dataset_registry.py research/evaluation_report.py app/dashboard.py app/cli.py tests/test_dataset_registry.py tests/test_evaluation_report.py tests/test_dashboard_evaluation.py`; `python -m pytest`.
- test_result: 79 passed.
- metric_result: default synthetic scenarios are all registered as `in_sample`; `out_of_sample` count is 0, so report notes prohibit profitability and production-validity claims.
- observed_failure: dashboard table initially missed the new split columns; fixed and revalidated.
- decision: KEEP.
- next_highest_value_question: can manual fill recording prevent open/close checklist actions from being inferred from signals?
- known_blockers: no real out-of-sample dataset has been defined, so no profitability or production-validity claim is supported.

## Iteration 24 - Manual execution checklist
- Current goal: Make open-pair guidance operationally useful without pretending signal markers are broker executions.
- Done: Added a manual fill recorder, CLI fill entry/listing path, and dashboard execution checklist for SB/BS open pairs.
- Validation: `python -m py_compile app/manual_fills.py app/cli.py app/dashboard.py tests/test_manual_fills.py tests/test_cli_manual_fills.py`; `python -m pytest` -> 85 passed.
- Next: Add data-source delay/licensing caveat panel before live guidance.
- Blockers: None.

## Iteration 25 - Data source caveat panel
- Current goal: Keep live-looking guidance from being mistaken for broker-confirmed market data or licensed production data.
- Done: Added a data-source disclosure model and dashboard caveat panel for Eastmoney and Yahoo Finance feeds.
- Validation: `python -m py_compile research/source_disclosure.py app/dashboard.py tests/test_source_disclosure.py`; `python -m pytest` -> 88 passed.
- Next: Add broker-confirmed position import hooks or manual reconciliation workflow.
- Blockers: No broker-confirmed holdings/fill source is connected yet.

## Iteration 26 - Manual broker position reconciliation
- Current goal: Prevent persisted dashboard/CLI sizing state from being mistaken for broker-confirmed holdings.
- Done: Added manual broker position snapshots, reconciliation reports, CLI `reconcile`, and a dashboard reconciliation panel.
- Validation: `python -m py_compile app/position_reconciliation.py app/cli.py app/dashboard.py tests/test_position_reconciliation.py tests/test_cli_reconciliation.py tests/test_dashboard_reconciliation.py`; `python -m pytest` -> 96 passed.
- Next: Add an explicit pre-trade order ticket checklist.
- Blockers: No live broker API is connected; reconciliation is manual until a broker import is available.

## Iteration 27 - Pre-trade order ticket checklist
- Current goal: Add a final mechanical gate between an actionable signal and any manual order entry.
- Done: Added a pre-trade order ticket checklist that checks actionability, symbol, quantity/lot, broker sellable quantity, broker cash, price-limit proximity, and fee/slippage estimates.
- Validation: `python -m py_compile app/order_ticket.py app/cli.py app/dashboard.py tests/test_order_ticket.py tests/test_dashboard_order_ticket.py`; `python -m pytest` -> 103 passed.
- Next: Add real out-of-sample dataset registration and a locked evaluation run.
- Blockers: No real OOS dataset has been registered yet.

## Iteration 28 - Locked OOS dataset evaluation
- Current goal: Add a real OOS row that is locked against silent file changes before evaluation.
- Done: Captured and registered `000001_20260618_eastmoney_intraday.csv` as a locked OOS CSV dataset with SHA-256 validation and added `evaluate --locked-oos`.
- Validation: `python -m py_compile research/dataset_registry.py research/evaluation_report.py app/cli.py app/dashboard.py tests/test_dataset_registry.py tests/test_evaluation_report.py tests/test_dashboard_evaluation.py`; `python -m pytest` -> 106 passed; `python -m app.cli evaluate --locked-oos --target-qty 151400 --settled-sellable-qty 151400 --purchasable-qty 15100 --trade-qty 15100` -> 1 locked OOS row.
- Next: Add execution-quality/slippage sensitivity bands.
- Blockers: One locked OOS sample is not enough for profitability or production-validity claims.

## Iteration 29 - Execution-quality sensitivity bands
- Current goal: Show whether an actionable edge survives worse fills instead of presenting a single-point estimate.
- Done: Added execution sensitivity bands for base, worse, bad, and tail fills; added CLI `trigger` output and dashboard table support.
- Validation: `python -m py_compile app/execution_sensitivity.py app/cli.py app/dashboard.py tests/test_execution_sensitivity.py tests/test_dashboard_execution_sensitivity.py`; `python -m pytest` -> 110 passed.
- Next: Add more independent locked OOS datasets across symbols/dates.
- Blockers: One locked OOS sample is not enough for profitability or production-validity claims.

## Iteration 30 - Expanded locked OOS coverage
- Current goal: Add more independent locked OOS rows across symbols and dates before any production-validity claim is considered.
- Done: Added Yahoo locked CSV rows for `000001` 2026-06-12, `300750` 2026-06-16, and `000858` 2026-06-17, plus an Eastmoney locked CSV row for `300750` 2026-06-18. Registry now has 5 locked OOS rows across 3 symbols and 4 dates.
- Validation: `python -m py_compile research/dataset_registry.py research/evaluation_report.py app/dashboard.py tests/test_dataset_registry.py tests/test_evaluation_report.py tests/test_dashboard_evaluation.py`; `python -m pytest` -> 111 passed; `python -m app.cli evaluate --locked-oos --target-qty 151400 --settled-sellable-qty 151400 --purchasable-qty 15100 --trade-qty 15100` -> 5 locked OOS rows.
- Next: Add a model-change audit report comparing current trigger thresholds against prior locked evaluation metrics.
- Blockers: Five public-feed OOS rows are still insufficient for profitability or production-validity claims.

## Iteration 31 - Model-change audit report
- Current goal: Make trigger-threshold changes auditable against prior locked OOS signal metrics.
- Done: Added `research/model_audit.py`, baseline `research/baselines/locked_oos_audit_baseline_v1.json`, CLI `audit`, and dashboard audit table helpers.
- Validation: `python -m py_compile research/model_audit.py app/cli.py app/dashboard.py tests/test_model_audit.py tests/test_dashboard_model_audit.py`; `python -m pytest` -> 116 passed; `python -m app.cli audit` -> `status=OK` with 5 locked OOS rows.
- Next: Add a locked OOS dataset capture command.
- Blockers: Five public-feed OOS rows are still insufficient for profitability or production-validity claims.

## Iteration 32

- current_baseline: locked OOS registry has 5 public-feed rows and a stored model-change audit baseline.
- hypothesis: future OOS additions need a reproducible capture path with hash checking and manual registry review, otherwise the audit set can be polluted by ad hoc files.
- expected_result: CLI captures/normalizes minute bars, writes a locked CSV, verifies SHA-256, and emits a `DatasetRecord` snippet without auto-registering the dataset.
- files_changed: `research/oos_capture.py`, `app/cli.py`, `tests/test_oos_capture.py`, `tests/test_cli_oos_capture.py`, `TODO.md`, and docs.
- commands_run: `python -m py_compile research/oos_capture.py app/cli.py tests/test_oos_capture.py tests/test_cli_oos_capture.py`; `python -m pytest`; `python -m app.cli capture-oos --source csv --symbol 000001 --date 20260612 --csv datasets/oos/000001_20260612_yahoo_intraday.csv --output-dir .runtime/<capture_oos_smoke> --min-bars 300`.
- test_result: 121 passed.
- metric_result: capture smoke produced 330 bars and SHA-256 `0470e0fce70e2a5dc13c71a3ce659a05ed7665f7452c994d37820a68791c0f3a`.
- observed_failure: initial CLI parser insertion lacked the execution branch; validation caught silent empty output and the dispatch was fixed before final validation.
- decision: KEEP.
- next_highest_value_question: can threshold experiments report locked-OOS audit deltas without modifying the baseline?
- known_blockers: only five public-feed locked OOS rows are registered, so profitability and production-validity claims remain prohibited.
## Iteration 33

- current_baseline: locked OOS audit can detect threshold and signal-metric drift, but manual parameter experiments previously required code edits or ad hoc runs.
- hypothesis: professional model improvement needs a safe what-if runner that reports locked-OOS audit deltas for candidate threshold sets without changing the stored baseline.
- expected_result: CLI outputs threshold overrides, per-field audit changes, per-scenario metric deltas, and aggregate trigger/watch/no-trade deltas; baseline JSON remains unchanged.
- files_changed: `research/threshold_experiments.py`, `app/cli.py`, `tests/test_threshold_experiments.py`, `tests/test_cli_threshold_experiments.py`, `TODO.md`, and docs.
- commands_run: `python -m py_compile research/threshold_experiments.py app/cli.py tests/test_threshold_experiments.py tests/test_cli_threshold_experiments.py`; `python -m pytest`; `python -m app.cli threshold-experiments --experiments more_selective`.
- test_result: 125 passed.
- metric_result: `more_selective` aggregate locked-OOS deltas were `trigger_count=-61`, `watch_count=-105`, and `no_trade_count=166` across 5 public-feed locked OOS rows.
- observed_failure: initial CLI test expected an outdated fee profile name; validation caught it and the test was corrected to `a_share_conservative`.
- decision: KEEP.
- next_highest_value_question: how should baseline updates be reviewed and approved after audit deltas are inspected?
- known_blockers: threshold deltas are not profitability evidence; only five public-feed locked OOS rows are registered.
## Iteration 34

- current_baseline: threshold experiments can report locked-OOS deltas, but there was no controlled workflow for promoting a reviewed current audit state into the stored baseline.
- hypothesis: a baseline update workflow must be gated by both detected audit deltas and an explicit review token, otherwise accidental writes can erase useful drift signals.
- expected_result: CLI and dashboard expose a preview-only baseline update state; writes require audit status `REVIEW` and exact token `APPROVE_LOCKED_OOS_BASELINE_UPDATE`.
- files_changed: `research/model_audit.py`, `app/cli.py`, `app/dashboard.py`, `tests/test_model_audit_baseline_update.py`, `tests/test_cli_baseline_update.py`, `tests/test_dashboard_baseline_update.py`, `TODO.md`, and docs.
- commands_run: `python -m py_compile research/model_audit.py app/cli.py app/dashboard.py tests/test_model_audit_baseline_update.py tests/test_cli_baseline_update.py tests/test_dashboard_baseline_update.py`; `python -m pytest`; `python -m app.cli audit-baseline-update`.
- test_result: 131 passed.
- metric_result: default baseline-update preview returned `NO_UPDATE_NEEDED`, 5 locked OOS rows, 0 threshold changes, and 0 metric changes.
- observed_failure: dashboard test used identity comparison against a Pandas boolean scalar; changed to value comparison.
- decision: KEEP.
- next_highest_value_question: can threshold-experiment deltas be rendered in the dashboard as a concise comparison table instead of raw JSON?
- known_blockers: baseline promotion is governance only; only five public-feed locked OOS rows are registered, so no profitability or production-validity claim is allowed.
## Iteration 35

- current_baseline: threshold experiments are available through CLI JSON, but dashboard users had to read raw JSON or leave the UI to compare candidate threshold deltas.
- hypothesis: rendering aggregate and per-scenario locked-OOS experiment deltas in dashboard tables makes threshold review more usable without weakening the no-profitability-claim boundary.
- expected_result: dashboard shows built-in threshold experiments with threshold-change count, metric-change count, aggregate trigger/watch/no-trade deltas, and per-scenario metric deltas.
- files_changed: `app/dashboard.py`, `tests/test_dashboard_threshold_experiments.py`, `TODO.md`, and docs.
- commands_run: `python -m py_compile app/dashboard.py tests/test_dashboard_threshold_experiments.py`; `python -m pytest`.
- test_result: 133 passed.
- metric_result: dashboard table builder exposes locked-OOS aggregate deltas such as `delta_trigger_count`, `delta_watch_count`, and `delta_no_trade_count`; per-scenario rows split scenario and metric names for review.
- observed_failure: none.
- decision: KEEP.
- next_highest_value_question: can risk-limit presets constrain intraday sizing by max turnover, open-pair time, and same-day capital at risk?
- known_blockers: experiment deltas are signal diagnostics only; only five public-feed locked OOS rows are registered.
## Iteration 36

- current_baseline: the app had max T ratio and max single trade quantity, but no explicit professional risk preset tying sizing to daily turnover, maximum open-pair time, and same-day capital at risk.
- hypothesis: intraday decision support needs named risk-limit presets so sizing is constrained by operational risk, not only by inventory percentage.
- expected_result: `defensive`, `balanced`, and `active` presets map to trigger rules; sizing is capped by round-trip turnover and capital-at-risk limits; max open-pair minutes is visible through `max_wait_minutes`; CLI/dashboard can select and persist the preset.
- files_changed: `research/risk_limits.py`, `research/trigger_engine.py`, `app/position_state.py`, `app/cli.py`, `app/dashboard.py`, `tests/test_risk_limits.py`, `tests/test_trigger_engine_risk_limits.py`, `tests/test_dashboard_risk_limits.py`, `tests/test_cli.py`, `TODO.md`, and docs.
- commands_run: `python -m py_compile research/risk_limits.py research/trigger_engine.py app/position_state.py app/cli.py app/dashboard.py tests/test_risk_limits.py tests/test_trigger_engine_risk_limits.py tests/test_dashboard_risk_limits.py tests/test_cli.py`; `python -m pytest`; `python -m app.cli trigger --scenario mean_revert --held-qty 10000 --settled-sellable-qty 10000 --purchasable-qty 10000 --max-t-ratio 0.10 --risk-preset defensive --ignore-fees`.
- test_result: 139 passed.
- metric_result: `defensive` preset caps a 10,000-share target at 500 shares for one pair and sets max open-pair wait to 25 minutes; CLI smoke reported `max_wait_minutes=25`.
- observed_failure: initial dashboard/CLI text replacements missed several signatures and state fields; validation caught the gaps and the final tests pass.
- decision: KEEP.
- next_highest_value_question: can completed manual fills be reviewed against the original pre-trade ticket and execution-sensitivity bands?
- known_blockers: risk presets are guardrails, not profitability evidence; only five public-feed locked OOS rows are registered.
## 2026-06-20 - Post-trade review report

- current_baseline: CLI/dashboard could show pre-trade ticket checks and execution sensitivity, but manual fills were not compared back to those assumptions.
- hypothesis: a professional decision-support app needs a post-trade review layer before any fill can influence risk or cost-basis interpretation.
- expected_result: a manual fill is checked against expected side, quantity, ticket limit/reference price, recorded fees/slippage, pre-trade ticket status, and execution sensitivity bands.
- files_changed: `app/post_trade_review.py`, `app/cli.py`, `app/dashboard.py`, `tests/test_post_trade_review.py`, `tests/test_dashboard_post_trade_review.py`, `TODO.md`, and docs.
- commands_run: `python -m py_compile app/post_trade_review.py app/cli.py app/dashboard.py tests/test_post_trade_review.py tests/test_dashboard_post_trade_review.py`; `python -m pytest`; `python -m app.cli trigger --scenario mean_revert --held-qty 10000 --settled-sellable-qty 10000 --purchasable-qty 10000 --max-t-ratio 0.10 --risk-preset defensive --ignore-fees`.
- test_result: 145 passed.
- metric_result: CLI `trigger` now emits `post_trade_review`; no-action smoke correctly returns `post_trade_review.status=NO_ACTION` rather than inferring a fill.
- observed_failure: first CLI smoke exposed an undefined `fee_model` in the trigger output path; fixed by reusing the same branch-local fee model for trigger, ticket, and post-trade review.
- decision: KEEP.
- next_highest_value_question: can live-session risk usage be computed from manual fills against the selected risk-limit preset?
- known_blockers: only five public-feed locked OOS rows are registered, so profitability and production trading validity remain unproven.

## 2026-06-20 - Live-session risk usage from manual fills

- current_baseline: risk-limit presets capped suggested order sizing, but the app did not show how much of the selected preset had already been consumed by manual fills in the current session.
- hypothesis: professional intraday use needs a live risk usage layer that counts only broker/manual fills, not signals or tickets.
- expected_result: the app compares manual session turnover, unclosed pair capital at risk, and max open-pair age against the selected preset.
- files_changed: `app/session_risk.py`, `app/cli.py`, `app/dashboard.py`, `tests/test_session_risk.py`, `tests/test_dashboard_session_risk.py`, `TODO.md`, and docs.
- commands_run: `python -m py_compile app/session_risk.py app/cli.py app/dashboard.py tests/test_session_risk.py tests/test_dashboard_session_risk.py`; `python -m pytest`; `python -m app.cli trigger --scenario mean_revert --held-qty 10000 --settled-sellable-qty 10000 --purchasable-qty 10000 --max-t-ratio 0.10 --risk-preset defensive --ignore-fees`.
- test_result: 150 passed.
- metric_result: CLI `trigger` now emits `live_session_risk_usage`; no-fill smoke reports zero turnover, zero open exposure, and OK usage under the defensive preset.
- observed_failure: none after implementation.
- decision: KEEP.
- next_highest_value_question: can broker/order export scaffolding make manual fills reconcilable against external broker confirmations?
- known_blockers: only five public-feed locked OOS rows are registered, so profitability and production trading validity remain unproven.

## 2026-06-20 - Broker fill import reconciliation scaffold

- current_baseline: manual fills could drive post-trade review and session risk usage, but there was no structured way to compare them with broker-confirmed external fill exports.
- hypothesis: a professional trading-support app needs an import preview that reconciles manual fills against broker export rows before treating manual entries as broker-confirmed evidence.
- expected_result: CSV/JSON broker fill exports can be parsed, exact-match reconciled against manual fills, and surfaced in CLI/dashboard without auto-writing manual fills.
- files_changed: `app/broker_import.py`, `app/cli.py`, `app/dashboard.py`, `tests/test_broker_import.py`, `tests/test_cli_broker_import.py`, `tests/test_dashboard_broker_import.py`, `TODO.md`, and docs.
- commands_run: `python -m py_compile app/broker_import.py app/cli.py app/dashboard.py tests/test_broker_import.py tests/test_cli_broker_import.py tests/test_dashboard_broker_import.py`; `python -m pytest`; `python -m app.cli broker-import --path .runtime\broker_import_smoke\broker.csv --manual-fills-path .runtime\broker_import_smoke\manual_fills.json --symbol 603236`.
- test_result: 157 passed.
- metric_result: CLI broker-import smoke matched one broker export row to one manual fill and returned `status=OK`, `matched_count=1`.
- observed_failure: initial smoke fixture used PowerShell UTF-8 with BOM for manual fills JSON; reran with no-BOM UTF-8 fixture and the import command succeeded.
- decision: KEEP.
- next_highest_value_question: can a session-level execution journal link signal, ticket, manual fill, broker reconciliation, post-trade review, and risk usage into one audit trail?
- known_blockers: only five public-feed locked OOS rows are registered, so profitability and production trading validity remain unproven.

## 2026-06-20 - Session execution journal

- current_baseline: trigger output and dashboard showed signal, ticket, post-trade review, broker reconciliation, and risk usage as separate artifacts, but there was no single audit trail linking their statuses.
- hypothesis: a professional operator needs one session-level journal that shows whether the execution chain is clean, incomplete, warning-only, or blocked.
- expected_result: CLI/dashboard build a read-only journal from `TradeIntent`, `PreTradeOrderTicket`, manual fills, broker reconciliation, post-trade review, and live risk usage.
- files_changed: `app/execution_journal.py`, `app/cli.py`, `app/dashboard.py`, `tests/test_execution_journal.py`, `tests/test_dashboard_execution_journal.py`, `TODO.md`, and docs.
- commands_run: `python -m py_compile app/execution_journal.py app/cli.py app/dashboard.py tests/test_execution_journal.py tests/test_dashboard_execution_journal.py`; `python -m pytest --basetemp .runtime\pytest-tmp`; `python -m app.cli trigger --scenario mean_revert --held-qty 10000 --settled-sellable-qty 10000 --purchasable-qty 10000 --max-t-ratio 0.10 --risk-preset defensive --ignore-fees`.
- test_result: 161 passed, with pytest cache warnings because `.pytest_cache` is not writable in this environment.
- metric_result: CLI `trigger` now emits `execution_journal`; no-action smoke returns a journal with `status=OK` and linked signal/ticket/broker/post-trade/risk stages.
- observed_failure: default pytest temp root was not accessible, so validation used workspace-local `--basetemp .runtime\pytest-tmp`.
- decision: KEEP.
- next_highest_value_question: can broker-only rows be promoted into manual fills only after explicit pair assignment and operator confirmation?
- known_blockers: only five public-feed locked OOS rows are registered, so profitability and production trading validity remain unproven.

## Iteration 39

- current_baseline: broker-import reconciliation identified broker-only rows but could not intentionally promote a reviewed broker row into manual execution state.
- hypothesis: professional use needs a narrow promotion path that remains explicit, pair-assigned, and operator-reviewed instead of auto-importing broker rows.
- expected_result: broker-only rows preview as blocked/review-required until pair_id and the exact review token are supplied; successful promotion writes one manual fill with broker provenance in the note.
- files_changed: `app/broker_import.py`, `app/cli.py`, `app/dashboard.py`, `tests/test_broker_import.py`, `tests/test_cli_broker_import.py`, `tests/test_dashboard_broker_promotion.py`, `TODO.md`, docs.
- commands_run: `python -m py_compile app/broker_import.py app/cli.py app/dashboard.py tests/test_broker_import.py tests/test_cli_broker_import.py tests/test_dashboard_broker_promotion.py`; `python -m pytest tests/test_broker_import.py tests/test_cli_broker_import.py tests/test_dashboard_broker_promotion.py --basetemp .runtime\pytest-tmp -q`; `python -m pytest --basetemp .runtime\pytest-tmp`; CLI `broker-promote` preview/write smoke.
- test_result: focused promotion tests 13 passed; full suite 168 passed; pytest cache warnings only.
- metric_result: CLI smoke returned `REVIEW_REQUIRED` without token and wrote one manual fill only with `APPROVE_BROKER_FILL_PROMOTION`.
- observed_failure: initial smoke fixture used UTF-8 BOM for manual fills JSON; rerun with no-BOM UTF-8 passed.
- decision: KEEP.
- next_highest_value_question: should session execution journals be persisted under `.runtime` for end-of-day review across dashboard/CLI sessions?
- known_blockers: only five public-feed locked OOS rows are registered, so profitability and production-validity claims remain prohibited.

## Iteration 40

- current_baseline: session execution journals were built in memory and shown in CLI/dashboard, but they disappeared after process or dashboard refresh context changed.
- hypothesis: saving each journal snapshot under `.runtime` gives a professional operator an end-of-day audit trail that can be compared across CLI/dashboard sessions without implying fills or PnL.
- expected_result: CLI `trigger` and dashboard persist the current journal, expose the saved path, and show recent saved records for the same symbol.
- files_changed: `app/execution_journal.py`, `app/cli.py`, `app/dashboard.py`, `tests/test_execution_journal.py`, `tests/test_dashboard_execution_journal.py`, `TODO.md`, docs.
- commands_run: `python -m py_compile app/execution_journal.py app/cli.py app/dashboard.py tests/test_execution_journal.py tests/test_dashboard_execution_journal.py`; `python -m pytest tests/test_execution_journal.py tests/test_dashboard_execution_journal.py --basetemp .runtime\pytest-tmp -q`; `python -m pytest --basetemp .runtime\pytest-tmp`; `python -m app.cli trigger --scenario mean_revert --held-qty 10000 --settled-sellable-qty 10000 --purchasable-qty 10000 --max-t-ratio 0.10 --risk-preset defensive --ignore-fees`.
- test_result: focused journal persistence tests 7 passed; full suite 171 passed; pytest cache warnings only.
- metric_result: CLI smoke emitted `execution_journal_path=.runtime\execution_journals\journal-scenario_mean_revert-2026-01-02T093700.json` and a `recent_execution_journals` list.
- observed_failure: first focused test expected `OK` from a deliberately incomplete fee/slippage fill fixture; corrected the assertion to compare persisted status with the report's actual status.
- decision: KEEP.
- next_highest_value_question: can the app enforce end-of-day closeout checks before any cost-basis reduction is counted?
- known_blockers: only five public-feed locked OOS rows are registered, so profitability and production-validity claims remain prohibited.
## Iteration 41

- current_baseline: persisted execution journals preserved session context, but there was no explicit gate preventing cost-basis reduction from being counted before broker reconciliation, inventory restoration, and risk closeout.
- hypothesis: a professional end-of-day workflow needs a closeout report that blocks accounting claims unless every execution evidence gate passes.
- expected_result: CLI/dashboard expose `session_closeout`; countable reduction is non-zero only when closed manual pairs are broker-matched, inventory is restored, and risk usage has no blocked metric.
- files_changed: `app/session_closeout.py`, `app/cli.py`, `app/dashboard.py`, `tests/test_session_closeout.py`, `tests/test_dashboard_session_closeout.py`, `tests/test_cli.py`, `TODO.md`, docs.
- commands_run: `python -m py_compile app/session_closeout.py app/cli.py app/dashboard.py tests/test_session_closeout.py tests/test_dashboard_session_closeout.py tests/test_cli.py`; `python -m pytest tests/test_session_closeout.py tests/test_dashboard_session_closeout.py tests/test_cli.py --basetemp .runtime\pytest-tmp -q`; `python -m pytest --basetemp .runtime\pytest-tmp`; `python -m app.cli trigger --scenario mean_revert --held-qty 10000 --settled-sellable-qty 10000 --purchasable-qty 10000 --max-t-ratio 0.10 --risk-preset defensive --ignore-fees --no-position-state`.
- test_result: focused closeout/CLI tests 12 passed; full suite 177 passed; pytest cache warnings only.
- metric_result: CLI smoke emitted `session_closeout.status=NO_ACTION`, `countable=false`, and `countable_cost_basis_reduction=0.0` when no manual fills exist.
- observed_failure: first CLI smoke showed no `session_closeout` field because the payload insertion did not land; added a CLI output regression test and fixed the insertion. Also normalized closeout session date to trading date instead of full timestamp.
- decision: KEEP.
- next_highest_value_question: can a compact end-of-day view compare the current closeout report against recent persisted journals?
- known_blockers: only five public-feed locked OOS rows are registered, so profitability and production-validity claims remain prohibited.
## Iteration 42

- current_baseline: closeout and persisted journals existed as separate artifacts, forcing the operator to mentally compare current accounting gates against recent audit snapshots.
- hypothesis: a compact end-of-day review view improves professional usability by putting current closeout status, countable reduction, latest persisted journal, and recent blocked/warning journal counts in one summary.
- expected_result: CLI `trigger` emits `end_of_day_review`, and dashboard shows a compact end-of-day review panel without changing fills, broker imports, or accounting state.
- files_changed: `app/end_of_day_review.py`, `app/cli.py`, `app/dashboard.py`, `tests/test_end_of_day_review.py`, `tests/test_dashboard_end_of_day_review.py`, `tests/test_cli.py`, `TODO.md`, docs.
- commands_run: `python -m py_compile app/end_of_day_review.py app/cli.py app/dashboard.py tests/test_end_of_day_review.py tests/test_dashboard_end_of_day_review.py tests/test_cli.py`; `python -m pytest tests/test_end_of_day_review.py tests/test_dashboard_end_of_day_review.py tests/test_cli.py --basetemp .runtime\pytest-tmp -q`; `python -m pytest --basetemp .runtime\pytest-tmp`; `python -m app.cli trigger --scenario mean_revert --held-qty 10000 --settled-sellable-qty 10000 --purchasable-qty 10000 --max-t-ratio 0.10 --risk-preset defensive --ignore-fees --no-position-state`.
- test_result: focused review/CLI tests 12 passed; full suite 182 passed; pytest cache warnings only.
- metric_result: CLI smoke emitted `end_of_day_review.status=NO_ACTION`, `recent_journal_count=1`, latest journal status `OK`, and zero countable reduction for the no-fill scenario.
- observed_failure: none after implementation.
- decision: KEEP.
- next_highest_value_question: can end-of-day review attribute each pair's broker match, net cash after fees/slippage, and blocking reason?
- known_blockers: only five public-feed locked OOS rows are registered, so profitability and production-validity claims remain prohibited.
## Iteration 43

- current_baseline: closeout had session-level gates but did not explain which specific pair was closed, open, broker-matched, or responsible for blocking the session.
- hypothesis: per-pair attribution makes end-of-day review more actionable because the operator can inspect each pair's quantities, broker match count, net cash after fees/slippage, and blocking reason.
- expected_result: `session_closeout.pair_attributions` lists pair-level status and appears in the dashboard closeout panel.
- files_changed: `app/session_closeout.py`, `app/dashboard.py`, `tests/test_session_closeout.py`, `tests/test_dashboard_session_closeout.py`, `TODO.md`, docs.
- commands_run: `python -m py_compile app/session_closeout.py app/dashboard.py tests/test_session_closeout.py tests/test_dashboard_session_closeout.py`; `python -m pytest tests/test_session_closeout.py tests/test_dashboard_session_closeout.py --basetemp .runtime\pytest-tmp -q`; `python -m pytest --basetemp .runtime\pytest-tmp`; `python -m app.cli trigger --scenario mean_revert --held-qty 10000 --settled-sellable-qty 10000 --purchasable-qty 10000 --max-t-ratio 0.10 --risk-preset defensive --ignore-fees --no-position-state`.
- test_result: focused closeout attribution tests 7 passed; full suite 184 passed; pytest cache warnings only.
- metric_result: CLI smoke emitted `session_closeout.pair_attributions`; no-fill scenario correctly returned an empty pair attribution array.
- observed_failure: initial bulk edit omitted passing `pair_attributions` into `SessionCloseoutReport`; focused test caught the risk and the return path was fixed.
- decision: KEEP.
- next_highest_value_question: should closeout signoff be exportable only after a reviewed EOD summary passes countable/no-action gates?
- known_blockers: only five public-feed locked OOS rows are registered, so profitability and production-validity claims remain prohibited.
## 2026-06-20 - Reviewed closeout signoff export
- current_baseline: closeout and compact EOD review existed, but reviewed snapshots were only transient CLI/dashboard output.
- hypothesis: professional review needs an explicit signoff artifact that can be written only after the closeout gate is clean and an operator supplies a review token.
- expected_result: signoff preview is always visible, writes require `APPROVE_EOD_CLOSEOUT_SIGNOFF`, and blocked or warning closeouts cannot be exported as reviewed snapshots.
- files_changed: `app/closeout_signoff.py`, `app/cli.py`, `app/dashboard.py`, `tests/test_closeout_signoff.py`, `tests/test_dashboard_closeout_signoff.py`, `tests/test_cli.py`, docs.
- commands_run: `python -m py_compile app/closeout_signoff.py app/cli.py app/dashboard.py tests/test_closeout_signoff.py tests/test_dashboard_closeout_signoff.py tests/test_cli.py`; focused pytest with project-local basetemp/cache; full pytest with project-local basetemp/cache; CLI trigger smoke with signoff token.
- test_result: focused 22 passed; full 190 passed.
- metric_result: CLI smoke wrote `.runtime\closeout_signoff_smoke\eod-signoff-scenario-mean_revert-2026-01-02.json` for a no-action closeout and exposed `closeout_signoff_preview.status=READY`.
- observed_failure: default pytest temp path under user AppData was not writable, so validation was rerun with project-local `.runtime` basetemp/cache.
- decision: KEEP.
- next_highest_value_question: should closeout and EOD review warn when broker/manual-fill files are stale versus the session date?
- known_blockers: signoff snapshots still depend on manual fills and broker exports; they are review artifacts, not broker truth or accounting events.

## 2026-06-20 - Dashboard execution journal history render fix

- Fixed a runtime dashboard crash where `_render_execution_journal_panel` called `_build_execution_journal_history_table`, which was not defined in `app.dashboard`.
- The panel now uses the already imported public helper `build_execution_journal_history_table` from `app.execution_journal`.
- Validation: dashboard py_compile passed; execution journal dashboard tests `7 passed`; full suite `190 passed` with project-local pytest basetemp/cache.

## 2026-06-20 - Dashboard scenario evaluation render fix

- Fixed a runtime dashboard crash where `main()` passed `risk_limit_preset_id` into `_render_evaluation_report`, but the renderer signature did not accept it.
- Added a regression test confirming `_render_evaluation_report` exposes the `risk_limit_preset_id` parameter.
- Validation: dashboard py_compile passed; dashboard evaluation/risk-limit tests `9 passed`; full suite `191 passed` with project-local pytest basetemp/cache.
