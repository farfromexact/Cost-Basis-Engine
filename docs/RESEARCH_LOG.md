# Research Log

## 2026-06-21 - Debug-field alias closeout

Hypothesis: The last in-flight debug-table change should be closed with a naming alias only, not more feature work.

Result: Added `deviation_bps` as a spec-compatible alias for `vwap_deviation_bps` in lifecycle events and signal detail output.

Current interpretation: This is a harmless observability closeout. It does not alter intraday decisions, trigger gates, sizing, or accounting.

## 2026-06-21 - Inventory and sellability top-level decision exposure

Hypothesis: A-share T+1 constraints are important enough that sellable-after, inventory delta, and capital requirement should be visible in the top-level decision, not only in nested diagnostics.

Result: Added top-level inventory fields to `TradeIntent.as_dict()` and added inventory OK / sellable-after / inventory delta / capital-required metrics to the dashboard trading decision card.

Current interpretation: This improves operational transparency. It does not change inventory enforcement, and broker-confirmed holdings are still required before real action.

## 2026-06-21 - Decision-path cost and edge bps exposure

Hypothesis: If the model blocks or allows ENTER based on bps-level round-trip cost and net edge, those exact quantities should be visible in the primary decision path.

Result: Added top-level bps fields to `TradeIntent.as_dict()`, added round-trip cost/net-edge/buffer rows to the decision summary evidence section, and added cost bps/net edge bps metrics to the dashboard top trading decision card.

Current interpretation: This improves interpretability of WATCH versus ENTER. It does not change the trigger logic or evidence boundary.

## 2026-06-21 - Custom fee break-even preview

Hypothesis: Fee configurability is more useful if the operator can immediately see the bps hurdle created by those inputs.

Result: Dashboard custom fee mode now includes a fee preview price and share count, then displays round-trip cost and break-even bps using the market-aware `FeeModel`.

Current interpretation: This makes the cost gate more transparent. It does not alter trigger thresholds, validate broker schedules, route orders, infer fills, or update evaluation baselines.

## 2026-06-21 - Market-specific custom fee plumbing

Hypothesis: Market-aware round-trip gating is incomplete unless the operator can configure the same A-share and US fee fields that the core model uses.

Result: Added CLI arguments for A-share official bps/min-commission fields and US SEC/FINRA/broker/platform fields. Dashboard custom fee mode now preserves the market key and displays the relevant market-specific fields. Focused tests cover custom A-share and US propagation plus existing fee model/profile behavior.

Current interpretation: This improves cost-model configurability and reduces hidden assumptions in live decision support. It does not validate any broker's actual schedule and does not update performance baselines.

## 2026-06-21 - Model-audit review guidance and custom-fee market fix

Hypothesis: A `REVIEW` audit state is useful only if it tells the operator what to do next. The app should clearly separate "current model differs from locked baseline" from "this is an improvement", and should not mutate the baseline automatically.

Result: Added `review_guidance` to model-audit reports and dashboard output. OK reports now state that no baseline update is needed; REVIEW reports now state that drift is a human review gate and baseline updates require the explicit review-token workflow. Also preserved the dashboard custom fee config market key so US custom fees continue using the US fee path.

Current interpretation: This improves governance clarity and fixes market-aware custom fee routing. It does not update the locked baseline, claim improvement, infer fills, or count cost-basis reduction.

## 2026-06-21 - Subtractive intraday execution simplification

Hypothesis: The live layer should not keep adding diagnostic states to the operator-facing workflow. A small state machine plus stricter cost-aware entry gates is more useful than more factors.

Result: Collapsed main lifecycle semantics to `NO_TRADE`, `WATCH`, `ENTER`, `EXIT`, and `ABORT`; filtered the main chart to enter/exit/abort markers; disabled auto-add by default; lowered default max T sizing to 5%; added no-new-pair cutoffs; added A-share official fee components and US SEC/TAF/broker fee components; added unified fee estimation helpers; and made trigger entries require market-aware round-trip cost plus a 5 bps net-edge buffer.

Current interpretation: This is a policy and execution-language simplification. It should reduce false actionability and chart noise, but it also intentionally changes locked-audit metrics versus the previous baseline. The model-audit review state is therefore expected until a human approves a baseline update.

## 2026-06-21 - US/Yahoo market module

Hypothesis: US stock support should be added as an explicit third market route rather than weakening the existing A-share and Korea assumptions.

Result: Added `US / Yahoo Finance` to the dashboard, `--data-source us_yahoo` to CLI trigger paths, a US prototype fee profile, US regular-session rule defaults, US-specific source disclosure, and tests for ticker normalization, rules, fees, caveats, and data quality.

Current interpretation: This is market plumbing and decision-support scaffolding only. Yahoo remains a public prototype feed, turnover amount is still approximated from `close * volume`, and no broker-confirmed US quote, account, fill, FX, or settlement state is modeled.

## 2026-06-21 - Per-session ledger summary

Hypothesis: EOD users need a compact split between realized/countable closeout reduction, blocked non-countable pair cash, and no-action days.

Result: Added `app.session_ledger`, which derives a session ledger from `SessionCloseoutReport`. CLI and dashboard now expose the ledger without changing closeout gates.

Current interpretation: This is an accounting presentation layer. Positive blocked pair cash remains non-countable until closeout gates pass and final signoff is reviewed.

## 2026-06-21 - Broker/manual fill freshness checks

Hypothesis: EOD closeout should not treat old manual fills or old broker export rows as sufficient evidence for the current session. Freshness should be explicit before any final signoff.

Result: Added a `fill_freshness` closeout check that compares manual-fill and broker-export row dates against the session date. The EOD review summary now surfaces closeout WARN status caused by freshness issues.

Current interpretation: This is an audit guard. It can warn that execution evidence is stale, but it does not infer fills, route orders, or make stale rows countable.

## 2026-06-21 - Bounded multi-leg lifecycle state

Hypothesis: Multi-leg T opportunities need explicit bounded-state diagnostics before they can be useful in live replay. A same-side add should require leg-count room, total T position-cap room, minimum spacing, and real price improvement versus the prior leg.

Result: Added lifecycle configuration fields for max legs, total T cap, minimum minutes between legs, and minimum add-leg price improvement. `OpportunityEvent` now reports leg count, cumulative suggested T quantity, cap, add improvement, and minutes since the last leg.

Current interpretation: This is still signal-only lifecycle diagnostics. It can explain why an ADD marker appears or is blocked, but it does not infer orders, fills, realized PnL, or countable cost-basis reduction.

## 2026-06-21 - Soft down-regime B/S gating

Hypothesis: B->S should not use the same regime gate in weak-down, strong-down, and crash-like conditions. Weak-down can be probe-only, while strong-down should require both extreme deviation and strong downside exhaustion; crash-like downside should remain blocked.

Result: Added side-specific trigger-score thresholds, regime trigger multipliers, B->S exhaustion gates, and regime position multipliers. `TriggerEngine` now labels `WEAK_DOWN`, `STRONG_TREND_DOWN`, and `CRASH_DOWN` profiles and sizes weak/strong down B->S probes below the base T size when allowed.

Current interpretation: This is a stricter decision-support policy change. It still does not infer fills, route orders, or claim realized cost-basis reduction.

## 2026-06-20 - B/S lifecycle diagnostics stage 1

Hypothesis: Before changing sizing and regime gates, the app needs a richer diagnostic language that explains whether a minute is watch-only, probeable, additive, confirmed, close-ready, forced, blocked, or expired.

Result: Added BS downside exhaustion scoring from minute OHLCV, VWAP anchor classification (`VWAP_REVERSION`, `VWAP_RESISTANCE`, `NEUTRAL`), target rationale, reason codes, blocked reasons, and lifecycle marker states `WATCH`, `PROBE`, `ADD`, `CONFIRM`, `CLOSE_READY`, `FORCED_DECISION`, `BLOCKED`, and `EXPIRED`. Dashboard markers and detail tables now expose these fields.

Current interpretation: This is a diagnostic/state-semantics upgrade, not a complete new trading policy. It does not yet implement full softer regime sizing or persistent multi-leg inventory accounting.

## 2026-06-20 - Button-gated research audit page

Hypothesis: Research validation and model governance should never run as a side effect of live intraday or execution review refreshes.

Result: Split the dashboard into `Execution / EOD review` and `Research / Audit`. The research page shows idle controls by default, and runs scenario evaluation, locked-OOS threshold experiments, model-change audit, or baseline update review only when the corresponding button is clicked.

Current interpretation: This should materially reduce rerun latency and accidental locked-OOS/audit work. It changes workflow gating only, not the research methodology or model output.

## 2026-06-20 - Compact data and account status strip

Hypothesis: The dashboard should keep data/source risk visible without letting detailed caveat tables dominate the homepage.

Result: Added a compact status strip summarizing source grade, broker confirmation, latest bar, bar count, and rollup status. Detailed source caveats and quality checks are now collapsed by default and auto-expand only for BAD data or actionable unconfirmed signals.

Current interpretation: This improves operator focus while preserving risk visibility. It does not make public feeds broker-confirmed or change the strategy evidence boundary.

## 2026-06-20 - Intraday decision priority and idle persistence

Hypothesis: For live use, the first rendered element should be the current `Trading decision`, and optional persisted sidebar state should not load or write unless explicitly enabled.

Result: Moved `Trading decision` and core market metrics to the top of the dashboard flow. Position persistence is now unchecked by default and stays idle during reruns unless the user opts in.

Current interpretation: This improves operational responsiveness and reduces incidental state I/O. It does not change the trigger engine, accounting, or evaluation evidence.

## 2026-06-20 - Lazy dashboard page split

Hypothesis: Live intraday use should avoid constructing execution and research-audit panels on every chart click or refresh.

Result: Added a sidebar page selector. `Intraday trading` renders market/model guidance only, while `Execution & research review` lazy-loads manual fills, broker reconciliation, tickets, sensitivity, post-trade review, risk usage, closeout, execution journals, scenario evaluation, threshold experiments, model audit, and baseline review.

Current interpretation: This improves Streamlit runtime behavior and reduces accidental journal/evaluation work during live use. It does not alter model output or research evidence.

## 2026-06-20 - Replay click selection reliability

Hypothesis: Replay click selection should use a wide chart interaction target and a stable local time key, because browser temporal serialization can shift naive exchange timestamps.

Result: Replaced the transparent point click layer with full-height transparent minute rules, changed selection to return `time_key`, and bumped the chart widget key to discard stale Streamlit chart state.

Current interpretation: This should make replay-at-time selection land on the intended minute inside the plot area. It does not change trigger-engine logic or any evidence boundary.

## 2026-06-20 - Replay full-session chart context

Hypothesis: A replay-at-time view should not visually collapse to one point when the selected minute is early in the session; only model inputs need to be truncated.

Result: Replay mode now keeps full-session price and ratio charts for visual context while computing the decision summary, market metrics, current yellow marker, lifecycle scan, and layer cards from bars closed by the selected minute.

Current interpretation: This resolves the misleading empty-chart UX without weakening the no-future-data model computation. Future bars can be visible as chart context, but they are not used by `TriggerEngine` for the selected replay state.

## 2026-06-20 - Yahoo sparse-session fallback

Hypothesis: Outside active trading, Yahoo can return a sparse current session that is not useful for intraday model interpretation; the dashboard should prefer the latest usable completed session.

Result: Added Yahoo 5-day fallback selection. If the 1-day response has too few bars, the adapter picks the most recent session with enough minute bars. The dashboard intraday caption now includes session date and bar count.

Current interpretation: This improves data usability in non-trading windows. Yahoo/Korea remains a prototype feed with approximate turnover amount and is not broker-confirmed execution data.

## 2026-06-20 - Replay-at-time model state

Hypothesis: A professional operator should be able to click any historical minute and see the model state that would have been visible using only bars closed by that minute.

Result: Added chart click selection over transparent minute points. Replay mode stores the nearest closed minute, truncates bars to that point, reruns `TriggerEngine`, updates the decision summary, market metrics, current marker, lifecycle scan, and layer cards, and provides `Back to Live`.

Current interpretation: This is an as-of model replay, not a full account replay. Manual fills, broker imports, execution journals, and account snapshots remain live/current until explicit historical state snapshots are implemented.

## 2026-06-20 - Streamlit width API maintenance

Hypothesis: Streamlit's deprecated `use_container_width` parameter can be replaced by `width="stretch"` without changing dashboard semantics.

Result: Updated dashboard dataframe and Altair chart calls to the current Streamlit width API and verified that no old parameter remains.

Current interpretation: This is UI/runtime maintenance only. It does not affect trigger logic, execution accounting, locked-OOS evaluation, or profitability evidence.

## 2026-06-20 - Current intraday decision marker

Hypothesis: The operator should see the current latest-closed-minute `TradeIntent` on the same price chart as VWAP, because historical lifecycle markers can otherwise look like the only signal annotations.

Result: Added an always-visible current-decision chart marker with a yellow vertical rule, point, and `Current: ...` label. Historical lifecycle markers remain optional and continue to state that no fills, realized PnL, or cost-basis reduction are inferred.

Current interpretation: This improves live readability only. It does not change trigger logic, execution accounting, locked-OOS evaluation, or profitability evidence.

## Iteration 0

Hypothesis: A minimal replay engine with strict inventory and fee accounting is the highest-value baseline because it prevents false cost-basis claims before any strategy research.

Result: Implemented core fee model, inventory ledger, S->B Pair state machine, no-trade comparison, synthetic replay, CLI, and automated tests.

Current interpretation: The project can now distinguish closed realized reduction from open inventory deviation and can surface sell-fly risk in a one-way-up synthetic day.

## Iteration 1

Hypothesis: A cost gate is required before opening a Pair; otherwise a visually successful回补 can still produce negative net cost-basis benefit after minimum commission, taxes, and slippage.

Result: Added signal-time round-trip cost gating, fixed next-minute fill timestamps, and made opening sell fills carry their Pair ID.

Current interpretation: Default configured fees now suppress weak-edge trades; tests can still exercise Pair mechanics by using a zero-fee synthetic research configuration.

## Iteration 2

Hypothesis: CLI replay must expose fee assumptions; otherwise research results cannot be reproduced or audited.

Result: Added explicit fee and slippage CLI parameters plus a unit test for argument-to-config mapping.

Current interpretation: Default CLI remains conservative, while zero-fee synthetic runs can be used only to verify mechanics.

## Iteration 3

Hypothesis: Source documentation must separate checked rule portals from unverified fee/rule assumptions to avoid false precision.

Result: Updated `docs/SOURCES.md` with checked SSE/SZSE rule portals and left tax, transfer-fee, and exact board-rule clauses as pending official checks.

Current interpretation: The code remains runnable without official-source completion, but any real replay must first pin effective rules and user-specific fees.

## Iteration 4

Hypothesis: A live minute-bar adapter is needed before user-specific validation; otherwise the project can only validate synthetic mechanics.

Result: Added `data.eastmoney.fetch_intraday_minute_bars`, `--symbol` CLI support, parser tests, and README usage.

Current interpretation: The project can now run a latest-trading-day smoke replay for a supplied A-share code, but the data source remains a research convenience until license and delay are verified.

## Iteration 5

Hypothesis: Eastmoney trend volume must be normalized from hands to shares; otherwise VWAP is inflated by 100x and all VWAP-based signals become invalid.

Result: Fixed the adapter and parser test to multiply trend volume by 100.

Current interpretation: Real-data feature calculations are now internally consistent for amount/volume VWAP.

## Iteration 6

Hypothesis: Inventory-deviation duration must be measured across replay minutes, not only fill events; otherwise under-allocation risk is understated.

Result: Added per-minute ledger snapshots during replay and a regression test.

Current interpretation: `max_inventory_deviation_duration` now better reflects how long the strategy was temporarily under target inventory.

## Iteration 7

Hypothesis: The user needs intraday decision prompts more than fee-gated replay acceptance, so the engine should expose a stateless `SB`/`BS` prompt layer.

Result: Added `research.prompts`, CLI `prompt`, bankroll-to-lot sizing, optional scan mode, and tests for SB, BS, cutoff, cooldown, and lot sizing.

Current interpretation: The project can now provide live-style first-leg prompts while keeping replay/accounting separate.

## Iteration 8

Hypothesis: Prompting must be state-aware; if a Pair is already open, the engine should prioritize closing it rather than issuing a new first-leg prompt.

Result: Added `SB_CLOSE` and `BS_CLOSE` actions plus CLI `--open-pair-side`, `--open-pair-price`, and `--open-pair-qty`.

Current interpretation: The prompt layer can now support both first-leg alerts and open-pair management.

## Iteration 9

Hypothesis: A usable intraday tool must run continuously and push actionable prompt changes to the user's phone, not require manual polling.

Result: Added CLI `monitor`, notification formatting, console/webhook/Bark/PushPlus notification providers, alert de-duplication, and notification tests.

Current interpretation: The project can now poll live minute data and alert on `SB_OPEN`, `BS_OPEN`, `SB_CLOSE`, or `BS_CLOSE`; phone delivery requires the user to provide a notification token or webhook.

## Iteration 10

Hypothesis: A Streamlit UI should be backed by a layered trigger engine rather than the earlier single-path prompt function.

Result: Added `TriggerEngine`, `TradeIntent`, `RegimeDecision`, `DeviationDecision`, `InventoryDecision`, CLI `trigger`, and Streamlit dashboard.

Current interpretation: Users can now enter stock code, held quantity, and purchasable quantity in a browser UI; the system outputs one canonical `TradeIntent` with reasons, blockers, warnings, and layer diagnostics.

## Iteration 11

Hypothesis: The trigger engine can support Korean stocks if data ingestion and market rules are kept separate from the core decision layers.

Result: Added a Yahoo Finance minute-bar adapter, Samsung symbol normalization, Korea/Yahoo Streamlit selection, CLI `trigger --data-source yahoo`, and Korea-specific defaults for lot size, price-limit risk, and close time. The adapter drops non-minute-aligned current bars so signals use closed minutes only.

Current interpretation: Samsung Electronics common stock can be prompted through `005930.KS` or aliases, but Yahoo's lack of turnover amount means VWAP is currently based on `close * volume` and should be treated as a prompt prototype rather than strict research-grade data.

## Iteration 12

Hypothesis: The dashboard should make percent movement and layer decisions visible before raw diagnostics; otherwise a high-price stock can look flat and JSON blocks are too slow to read intraday.

Result: Replaced the single absolute-price Streamlit chart with Altair price and percent charts, added prominent ratio metrics, and rendered Regime/Deviation/Inventory as decision cards with raw JSON moved to a debug expander.

Current interpretation: The page is better suited for quick live reading, while the underlying `TradeIntent` structure remains unchanged.

## Iteration 13

Hypothesis: Users need to see where historical intraday prompts appeared on the chart, not only the latest prompt.

Result: Added a closed-minute signal scan to the dashboard, overlaying watch/trigger SB and BS markers on the price chart and exposing a signal detail table.

Current interpretation: The markers are prompt snapshots generated from data available up to each minute. They are not fills, not stateful pair accounting, and not cost-basis reduction claims.

## Iteration 14

Hypothesis: Repeating the same direction on consecutive minutes should be displayed as one opportunity window, otherwise the chart overstates how many actionable chances existed.

Result: Dashboard markers now default to trigger-only display, collapse continuous same-side signals within a configurable cooldown window, and keep observation markers optional.

Current interpretation: The marker count is now closer to actionable decision moments, while still remaining a prompt visualization rather than execution evidence.

## Iteration 15

Hypothesis: Trigger-level decisions should require more than a positive expected edge; they should also pass explicit deviation-strength and liquidity-confirmation gates.

Result: Added a `TriggerEngine` signal quality gate. Setups below trigger deviation score, below `min_amount_ratio`, or below `min_net_edge` now return watch intents instead of actionable triggers. Added focused tests for weak deviation and weak liquidity.

Current interpretation: The engine is stricter and more suitable for decision support: watch signals can still inform attention, but actionable prompts now require stronger evidence. This is still not profitability evidence.

## Iteration 16

Hypothesis: Professional users need a stable summary format before reading raw layer diagnostics.

Result: Added `research.decision_summary.build_decision_summary`, with separate recommendation, evidence, invalidation, position impact, and caveats sections. The Streamlit dashboard now renders this summary before the lower-level market and layer views.

Current interpretation: The UI is more decision-support oriented: it shows what to do, why, where the idea fails, how inventory changes, and what caveats apply. It still does not claim profitability or realized cost-basis reduction.

## Iteration 17

Hypothesis: Scenario evaluation should put every candidate next to a no-trade baseline and a simple interpretable baseline, otherwise trigger diagnostics can look more meaningful than they are.

Result: Added `research.evaluation_report`, producing a multi-scenario report with explicit no-trade rows, simple S->B replay metrics, and trigger-engine signal diagnostics. Added `python -m app.cli evaluate` for JSON output and tests covering the report structure and known synthetic baseline behavior.

Current interpretation: The project now has a clearer research comparison surface. Trigger-engine rows remain signal-only; fills and realized PnL are not inferred from them.

## Iteration 18

Hypothesis: Data freshness and source quality must be visible before decision confidence, otherwise stale or approximate data can look like high-conviction guidance.

Result: Added `research.data_quality.build_data_quality_report` and rendered it in the dashboard before the decision summary. The report flags stale bars, insufficient bar coverage, sparse zero-volume data, and approximate turnover amount such as Yahoo/Korea `close * volume` proxies.

Current interpretation: The UI now forces data-quality caveats into the decision workflow. This improves operational safety but does not create strategy validity evidence.

## Iteration 19

Hypothesis: Chart markers should represent the lifecycle of a signal opportunity rather than repeating raw trigger snapshots, because raw markers can be mistaken for multiple executed trades.

Result: Added a lifecycle scanner that turns trigger opportunities into `OPEN`, `CLOSE_READY`, `EXPIRED`, or `BLOCKED` events. Dashboard marker colors, labels, tooltips, and detail rows now surface lifecycle state and repeat the caveat that no fill, PnL, or cost-basis reduction is inferred.

Current interpretation: The chart is closer to trader decision support because it shows whether a signal window later became close-ready, timed out, or invalidated. It still remains signal-only and does not prove execution quality or profitability.

## Iteration 20

Hypothesis: The app cannot be trusted operationally if dashboard inputs and monitoring context diverge during refreshes or command-line monitoring.

Result: Added a shared JSON position-state store for symbol, market source, held quantity, sellable quantity, purchasable quantity, sizing limits, fee toggle, and optional open pair. Dashboard persists the sidebar context by default, while CLI prompt/monitor/trigger read the same state unless explicitly disabled.

Current interpretation: This makes live monitoring less error-prone because the monitor can follow the same inventory context the user reviewed in the dashboard. It still does not create brokerage connectivity, execution proof, or strategy-validity evidence.

## Iteration 21

Hypothesis: Scenario comparisons need to be visible inside the dashboard, otherwise users can over-focus on the latest live prompt without checking no-trade and simple-baseline behavior.

Result: Added a dashboard scenario evaluation section that flattens the existing evaluation report into a table with no-trade baseline, simple S->B replay metrics, trigger scan counts, and a signal-only caveat.

Current interpretation: The dashboard now keeps research hygiene closer to the live decision workflow. The table is still synthetic scenario evaluation and does not prove profitability for the current symbol.

## Iteration 22

Hypothesis: A professional decision-support app should not let live guidance silently use zero-fee assumptions; zero-fee should be explicit and labeled as research-only.

Result: Added named fee profiles with costed A-share and Korea prototype defaults, a low-cost A-share sensitivity preset, custom manual rates, and an explicit `zero_fee_research` profile. Dashboard and CLI now use costed defaults, while persisted position state stores the selected profile.

Current interpretation: The app is less likely to overstate signal quality by omitting fees/slippage. Fee profiles still require broker confirmation and do not establish profitability or execution quality.

## Iteration 23

Hypothesis: Any professional-facing evaluation table needs explicit dataset split metadata; otherwise in-sample research fixtures can be mistaken for out-of-sample validation.

Result: Added `research.dataset_registry` and made evaluation reports resolve scenarios through that registry. Dashboard and JSON outputs now carry `dataset_id`, `dataset_split`, `is_out_of_sample`, split summary, and notes that current synthetic fixtures are in-sample only.

Current interpretation: The app now blocks a common research hygiene failure: unlabeled performance rows. Because no real OOS dataset is registered, the correct interpretation remains no profitability or production-validity claim.

## 2026-06-20 - Manual fill recorder and execution checklist
- Added manual broker-fill persistence for open-pair execution tracking.
- Added CLI support for recording/listing manual fills and deriving stable pair ids from symbol, side, price, and quantity.
- Added dashboard checklist states so an open pair is not considered closed until the expected manual open and close fills exist.
- Validation: `python -m pytest` -> 85 passed.

## 2026-06-20 - Data source disclosure panel
- Added `research.source_disclosure` to label Eastmoney and Yahoo Finance as research/prototype feeds rather than broker-confirmed data.
- Dashboard now renders delay, licensing, sellability/turnover, and broker-confirmation caveats before decision interpretation.
- Added tests for Eastmoney A-share caveats, Yahoo/Korea prototype caveats, and dashboard disclosure table structure.
- Validation: `python -m pytest` -> 88 passed.

## 2026-06-20 - Manual broker position reconciliation
- Added `app.position_reconciliation` for manual broker/account snapshots and persisted-state comparison.
- Added CLI `reconcile` support for recording/listing reconciliation status from saved position state and manual broker quantities.
- Added dashboard broker reconciliation panel that marks mismatched or overstated total/sellable/purchasable capacity as `BLOCKED` before live sizing is trusted.
- Validation: `python -m pytest` -> 96 passed.

## 2026-06-20 - Pre-trade order ticket checklist
- Added `app.order_ticket` to turn actionable trigger intents into a mechanical pre-trade checklist.
- Dashboard now renders the checklist after broker reconciliation, so suggested orders are checked against broker/manual snapshot capacity before action.
- CLI `trigger` output now includes `pre_trade_order_ticket`, and the previously added `reconcile` command is wired into the parser/dispatcher.
- Validation: `python -m pytest` -> 103 passed.

## 2026-06-20 - Locked OOS dataset evaluation
- Added a real Eastmoney intraday CSV for `000001` on `2026-06-18`, registered as `oos_000001_20260618_eastmoney`.
- Added dataset kind/path/hash metadata, SHA-256 verification before CSV evaluation, and `build_locked_oos_evaluation_report`.
- Added CLI `evaluate --locked-oos` and dashboard evaluation-table fields for locked OOS rows.
- Validation: `python -m pytest` -> 106 passed; locked OOS CLI run emitted one `out_of_sample`/`dataset_locked=true` row.

## 2026-06-20 - Execution-quality sensitivity bands
- Added `app.execution_sensitivity` to stress trigger-engine gross edge against higher slippage and adverse fill bps.
- CLI `trigger` now includes `execution_sensitivity` alongside the pre-trade order ticket.
- Dashboard has table helpers and panel rendering for sensitivity bands so worse-fill robustness is visible before evaluation sections.
- Validation: `python -m pytest` -> 110 passed.

## 2026-06-20 - Expanded locked OOS coverage
- Added four additional locked OOS CSV datasets: `oos_000001_20260612_yahoo`, `oos_300750_20260616_yahoo`, `oos_000858_20260617_yahoo`, and `oos_300750_20260618_eastmoney`.
- Updated registry tests to require multiple symbols and dates, unique dataset IDs, SHA-256 verification, and bar-count checks for every locked OOS row.
- Updated `datasets/oos/README.md` with registered file paths, sources, bar counts, windows, and hashes.
- Validation: `python -m pytest` -> 111 passed; locked OOS CLI run emitted 5 out-of-sample rows.

## 2026-06-20 - Model-change audit report
- Added a stored model-audit baseline with current RulesConfig trigger thresholds and locked OOS signal counts.
- Added report logic that compares current thresholds and locked OOS trigger/watch/no-trade metrics against the baseline.
- Added CLI `audit` JSON output and dashboard table helper for threshold/metric deltas.
- Validation: `python -m pytest` -> 116 passed; `python -m app.cli audit` returned `status=OK`.

## Iteration 32

Hypothesis: OOS evaluation will only stay useful if new locked datasets enter through a reproducible capture command that writes normalized bars, verifies content hash, and preserves a manual registry review step.

Result: Added `research.oos_capture` and CLI `capture-oos` for csv/eastmoney/yahoo sources. The command writes a normalized minute CSV, verifies SHA-256 through the dataset lock checker, and emits a registry snippet plus capability caveat instead of auto-registering the sample.

Current interpretation: The project now has a controlled intake path for expanding locked OOS coverage. This improves research hygiene and regression discipline, but it does not add enough evidence to support profitability or production trading claims.
## Iteration 33

Hypothesis: Threshold tuning should be handled as auditable what-if experiments, not as direct baseline edits, because otherwise model changes can be mistaken for validated improvements.

Result: Added `research.threshold_experiments` and CLI `threshold-experiments`. Built-in experiments currently include `more_selective`, `more_sensitive`, and `execution_strict`; each reuses the locked-OOS audit path and reports threshold changes, scenario metric changes, and aggregate signal-count deltas.

Current interpretation: The app can now compare candidate threshold directions without mutating the baseline. This is useful for review discipline, but a delta such as fewer triggers is not automatically better and does not prove profitability.
## Iteration 34

Hypothesis: Baseline promotion needs an explicit review gate; otherwise a convenient update command can accidentally normalize unreviewed drift and weaken model-change audit discipline.

Result: Added a baseline update preview/result workflow in `research.model_audit`, CLI `audit-baseline-update`, and a dashboard review gate. A baseline write now requires existing audit deltas plus the exact token `APPROVE_LOCKED_OOS_BASELINE_UPDATE`; without the token the command only previews status and required review fields.

Current interpretation: The app now separates audit review from baseline promotion. This improves governance for model iteration, but a promoted baseline remains a reviewed regression reference only, not profitability evidence.
## Iteration 35

Hypothesis: Professional users need to compare threshold experiments inside the dashboard, because raw CLI JSON slows review and makes it easier to overfocus on one metric.

Result: Added dashboard builders and rendering for locked-OOS threshold experiment comparison. The summary table shows each experiment's audit status, threshold-change count, metric-change count, and aggregate trigger/watch/no-trade deltas; the detail table shows per-scenario metric changes.

Current interpretation: Threshold exploration is now visible in the UI while remaining explicitly labeled as signal-count deltas only. This supports model governance and review, not profitability claims.
## Iteration 36

Hypothesis: A professional intraday tool should not size trades only from a simple target-inventory percentage. It also needs explicit limits for round-trip turnover, open-pair holding time, and same-day capital at risk.

Result: Added `research.risk_limits` with `defensive`, `balanced`, and `active` presets. The trigger engine now caps preliminary quantity by risk preset turnover and capital-at-risk limits, maps preset open-pair minutes into `max_wait_minutes`, and exposes the selected preset through CLI/dashboard state.

Current interpretation: Sizing is now more operationally constrained. The presets reduce accidental over-sizing and make risk assumptions visible, but they remain guardrails and do not prove that any signal is profitable.
## 2026-06-20 - Post-trade review report

Hypothesis: Manual fills should be reviewed against the pre-trade ticket and execution sensitivity bands before the app treats them as clean execution evidence.

Result: Added `app.post_trade_review`, CLI `trigger` output field `post_trade_review`, and a dashboard post-trade review panel. The report checks manual fill presence, pair id, side, quantity, average fill price versus ticket reference, recorded fees/slippage versus ticket estimates, pre-trade ticket status, and whether execution sensitivity was already thin or exhausted.

Current interpretation: The app now has a safer bridge from recommendation to manually recorded execution. This still does not infer fills, route orders, claim realized PnL, or count cost-basis reduction before both legs close, target inventory is restored, and all fees/slippage are deducted.

## 2026-06-20 - Live-session risk usage from manual fills

Hypothesis: Risk presets are not useful enough if the app only applies them before an order; the operator also needs to see how much of the preset has already been consumed by manual fills during the session.

Result: Added `app.session_risk`, CLI `trigger` output field `live_session_risk_usage`, and a dashboard risk usage panel. The report filters manual fills by symbol and session date, then measures gross turnover quantity, unclosed pair exposure, net position delta, and max open-pair age against the selected risk-limit preset.

Current interpretation: The app now exposes live operational risk usage from actual manual fills. This is still a guardrail, not performance evidence, and signals/tickets do not consume risk limits until a manual broker fill exists.

## 2026-06-20 - Broker fill import reconciliation scaffold

Hypothesis: Manual fills should be reconcilable against broker-confirmed exports before they are treated as execution evidence.

Result: Added `app.broker_import`, CLI `broker-import`, and a dashboard broker fill import reconciliation panel. The scaffold accepts CSV or JSON broker fill exports with a documented column set, normalizes broker rows, and reconciles them against manual fills using an exact symbol/side/qty/price/timestamp key.

Current interpretation: The app can now identify matched fills, broker-only fills, manual-only fills, and ambiguous duplicate keys. It deliberately does not auto-write manual fills from broker exports, because pair context and operator confirmation are still required before an imported broker row should affect post-trade review or risk usage.

## 2026-06-20 - Session execution journal

Hypothesis: Separate signal, ticket, fill, broker, review, and risk reports are useful, but a professional intraday workflow needs one audit trail that links them in order.

Result: Added `app.execution_journal`, CLI `trigger` output field `execution_journal`, and a dashboard Session execution journal panel. The journal summarizes the signal, pre-trade ticket, manual fill state, broker reconciliation, post-trade review, and live risk usage with a single aggregate status.

Current interpretation: The app now gives the operator a compact view of whether a session artifact chain is clean, warning-only, or blocked. The journal is read-only and does not route orders, infer fills, mutate manual fills, or create realized PnL/cost-basis claims.

## Iteration 39

Hypothesis: Broker-confirmed rows are useful only if the app can deliberately connect them to an intended pair and then promote them into manual execution state after operator review.

Result: Added a broker-fill promotion preview and write path. The preview blocks missing pair assignment, duplicate manual-fill keys, missing broker rows, and missing review token. The CLI `broker-promote` command writes only after the exact token is supplied.

Current interpretation: Broker imports remain reconciliation scaffolding by default. Promotion is intentionally manual and auditable; it does not relax the rule that realized cost-basis reduction is counted only after both legs close, target inventory is restored, and all fees/slippage are deducted.

## Iteration 40

Hypothesis: A session journal is only operationally useful if it survives the current CLI/dashboard run and can be reviewed later against broker/manual evidence.

Result: Added `.runtime/execution_journals` persistence, recent-record loading, and a flattened history table. CLI `trigger` now returns `execution_journal_path` and `recent_execution_journals`; the dashboard saves the current journal and displays recent records.

Current interpretation: The app now has a lightweight session audit archive suitable for end-of-day review. The archive is evidence organization only; it still does not route orders, infer fills, or count realized cost-basis reduction.
## Iteration 41

Hypothesis: A cost-basis reduction should not be countable merely because manual fills exist; it must pass end-of-day evidence gates.

Result: Added `app.session_closeout` and surfaced `session_closeout` in CLI `trigger` and the dashboard. The report checks closed manual pairs, broker reconciliation, inventory restoration, and open risk-limit breaches before exposing any countable cost-basis reduction after fees/slippage.

Current interpretation: The app now has a stricter accounting guardrail. It can show that a session is not countable, or that a closed pair is countable after all evidence gates pass, but it still makes no profitability claim and depends on broker-confirmed/manual evidence.
## Iteration 42

Hypothesis: Operators need a compact review surface that connects current closeout gates with persisted session journals, rather than reading multiple raw JSON blocks.

Result: Added `app.end_of_day_review`, CLI `trigger` output field `end_of_day_review`, and a dashboard compact end-of-day review panel. The report summarizes closeout countability, latest persisted journal status, recent blocked/warning journal counts, and operator actions.

Current interpretation: The app now provides a more usable end-of-day review layer. It remains audit navigation only; closeout gates and broker/manual evidence remain authoritative for any countable cost-basis reduction.
## Iteration 43

Hypothesis: Session-level closeout status is not enough for professional EOD review; the operator needs to know which pair is countable or blocked.

Result: Added per-pair closeout attribution to `session_closeout`. Each pair now reports buy/sell quantity, fill count, broker matched count, net cash after fees/slippage, countable flag, and blocking reason. The dashboard closeout panel renders the pair attribution table.

Current interpretation: EOD review is now more inspectable. The model still does not infer executions or profitability; pair attribution is derived only from manual fills and broker reconciliation evidence.
## 2026-06-20 - Reviewed closeout signoff export

Hypothesis: A professional EOD workflow needs a deliberate reviewed snapshot, not just transient dashboard state, so operators can distinguish countable/no-action closeouts from unresolved closeout states.

Result: Added `app.closeout_signoff` with preview checks, token-gated write behavior, CLI `trigger` signoff options, and a dashboard preview panel. Writes are allowed only when the closeout is countable or no-action and the review token is supplied.

Current interpretation: The app now has a cleaner end-of-day audit artifact. The snapshot does not imply broker execution, accounting recognition, or profitability.

## 2026-06-20 - Streamlit Cloud import path fix

Hypothesis: The online deployment failed because Streamlit Cloud executed `app/dashboard.py` with the `app/` directory as the script path, leaving the repository root off `sys.path`.

Result: Added a small entrypoint bootstrap to `app.dashboard` before project imports and a regression test for cloud-style importing from the `app/` directory.

Current interpretation: This is a deployment packaging fix only. It does not change model behavior, trading logic, or evaluation results.

## 2026-06-20 - Streamlit Cloud locked-OOS hash fix

Hypothesis: The online scenario evaluation failed because locked dataset hashes were generated from Windows CRLF bytes, while Streamlit Cloud evaluated GitHub checkout files with LF bytes.

Result: Changed locked dataset verification to hash LF-normalized CSV content, updated the five locked-OOS registry hashes to their canonical LF values, and pinned `datasets/oos/*.csv` to LF through `.gitattributes`.

Current interpretation: Cross-platform deployment can now verify the same locked OOS content without weakening the no-profitability-claim boundary.

## 2026-06-20 - Dashboard research panels fail independently

Hypothesis: A professional review dashboard should not lose all downstream audit panels when one research comparison block fails.

Result: Guarded Scenario evaluation, threshold experiments, model audit, and baseline update review independently in the dashboard renderer.

Current interpretation: The dashboard is more operationally resilient: one blocked research panel surfaces its own error while the rest of the audit surface remains visible.

## 2026-06-20 - Streamlit Cloud stale module cache fix

Hypothesis: The deployed app showed the newer guarded dashboard blocks but still used old locked-OOS hashes because Streamlit retained cached imported project modules across reruns.

Result: Dashboard startup now clears cached project submodules before importing app/core/data/research dependencies, forcing redeployed code to load fresh module contents.

Current interpretation: This is a deployment runtime consistency fix. It does not alter strategy logic or evaluation interpretation.
