# Decisions

## 2026-06-21 - Stop intraday embellishment after debug-field closeout

- Decision: Keep `deviation_bps` only as a compatibility alias for existing VWAP deviation bps.
- Decision: Do not continue adding new intraday UI/detail features in this pass.
- Rationale: The simplified intraday logic is the useful part; additional detail risks making the app noisy again.
- Consequence: The remaining work is review and baseline governance, not more live-page embellishment.

## 2026-06-21 - Sellability belongs in the primary decision card

- Decision: `TradeIntent` JSON exposes inventory feasibility, sellable-after, inventory delta, and capital required as top-level fields.
- Decision: Dashboard top decision card shows those same inventory metrics.
- Rationale: A suggested T action is not operationally meaningful unless the operator can immediately see sellable/capital feasibility.
- Consequence: A-share T+1 and cash constraints are easier to audit, but broker-confirmed account state remains outside the model until explicitly reconciled.

## 2026-06-21 - Show the bps hurdle where the decision is made

- Decision: `TradeIntent` JSON exposes round-trip cost bps, net edge bps, and required edge-buffer bps as top-level fields.
- Decision: Dashboard and decision summary show cost/net/buffer bps near the main trading decision.
- Rationale: A professional operator needs to know not only the action label, but also whether the signal clears costs by enough margin.
- Consequence: Decision output is more auditable, while execution, fills, realized PnL, and baseline updates remain separate workflows.

## 2026-06-21 - Custom fee inputs should show their bps hurdle

- Decision: Dashboard custom fee mode displays a market-aware round-trip cost and break-even bps preview.
- Decision: The preview uses the same `FeeModel` methods as trigger cost gating.
- Rationale: Operators should not have to infer whether a custom fee schedule materially changes the minimum required edge.
- Consequence: Fee assumptions become more auditable, but the preview remains an assumption check rather than broker-confirmed cost evidence.

## 2026-06-21 - Custom fee config must expose market-specific cost fields

- Decision: CLI custom fee configuration includes A-share official fee bps, A-share broker commission/minimum, US SEC fee, US FINRA TAF, US broker commission/minimum, and US platform fee.
- Decision: Dashboard custom fee mode shows market-specific fields and preserves the selected market identity.
- Rationale: Entry gating uses market-aware round-trip cost, so operator-configured costs must not collapse back to a generic fee shape.
- Consequence: Users can align fee assumptions closer to their broker schedule, but the app still treats those inputs as operator-provided assumptions rather than verified brokerage truth.

## 2026-06-21 - Audit REVIEW is a human gate, not an automatic baseline update

- Decision: `ModelChangeAuditReport` includes `review_guidance` explaining whether no baseline update is needed or whether locked-OOS drift requires human review.
- Decision: Dashboard displays review guidance when audit status is `REVIEW`.
- Decision: Custom dashboard fee configs preserve the selected market key.
- Rationale: After model semantics change, audit drift is expected, but it must not be interpreted as proof of improvement or silently promoted into a new baseline.
- Consequence: The stored locked baseline remains unchanged until the explicit review-token workflow is used; US custom fee configs keep US-specific fee routing.

## 2026-06-21 - Live execution language is simple; diagnostics stay behind it

- Decision: The operator-facing lifecycle is `NO_TRADE`, `WATCH`, `ENTER`, `EXIT`, and `ABORT`.
- Decision: Main chart markers show enter/exit/abort events only; richer `PROBE`, `ADD`, `CONFIRM`, `CLOSE_READY`, `BLOCKED`, and `EXPIRED` states remain debug details.
- Decision: Auto ADD is disabled by default and one leg per side is the default live posture.
- Decision: Entry eligibility must clear market-aware true round-trip cost plus a 5 bps edge buffer.
- Decision: A-share and US fee assumptions use explicit market components instead of one generic fee shape.
- Rationale: Professional use needs fast, unambiguous action language and conservative cost gates; detailed diagnostics are still valuable, but not as the primary execution state.
- Consequence: Locked model-audit metrics can drift versus the previous stored baseline. That drift is a review prompt, not a profitability claim or an automatic reason to update the baseline.

## 2026-06-21 - US market support is explicit, not a Korea/Yahoo alias

- Decision: US stock support uses a distinct `US / Yahoo Finance` market source and CLI source `us_yahoo`.
- Decision: US rules use 1-share lot size and regular-session times of 09:30 open, 15:35 latest open, 15:50 force-restore, and 16:00 close; ordinary A-share/Korea price-limit assumptions are not applied.
- Decision: US defaults use a separate `us_prototype_conservative` fee profile and US-specific source caveats.
- Rationale: The same Yahoo adapter can fetch multiple exchanges, but market mechanics must remain explicit so the dashboard does not silently apply A-share T+1, Korea price limits, or A-share fee assumptions to US stocks.
- Consequence: US support is available for prototype intraday decision support, but it remains unbrokered and cannot support profitability, execution, settlement, FX, or account-state claims.

## 2026-06-21 - Ledger separates countable and non-countable cash

- Decision: The session ledger is derived from `SessionCloseoutReport`, not from raw fills independently.
- Decision: `realized_countable_reduction` only uses closeout-approved countable reduction; blocked pair net cash stays non-countable even when positive.
- Decision: no-action days get an explicit row rather than being mixed with zero-result trading days.
- Rationale: Users need accounting clarity without bypassing closeout gates.
- Consequence: CLI/dashboard now show ledger summary fields, but execution, fills, restored inventory, broker matching, and fees/slippage remain governed by closeout.

## 2026-06-21 - Closeout requires fresh session evidence

- Decision: Closeout includes a `fill_freshness` check comparing manual-fill and broker-export row dates with the selected session date.
- Decision: Stale evidence produces WARN and prevents countable closeout reduction unless all other gates are OK and fresh session rows exist.
- Rationale: A broker export or manual-fill file can exist but still describe an older session; final EOD review must not silently rely on stale evidence.
- Consequence: EOD review inherits closeout freshness warnings and asks the operator to load or record session-date evidence before final signoff.

## 2026-06-21 - Multi-leg lifecycle adds are explicitly bounded

- Decision: Same-side lifecycle ADD markers require max-leg room, total T position-cap room, minimum minutes since the prior leg, and required price improvement versus the prior leg.
- Decision: A same-side trigger that crosses invalidation but fails an add bound should be marked blocked with the failed add constraint in the reason.
- Rationale: Averaging into the same side without visible bounds is not professional decision support; the operator needs to know both why an add is allowed and why it is not.
- Consequence: Lifecycle ADD remains signal-only and cumulative quantity is diagnostic; execution, broker fills, restored inventory, and countable cost-basis reduction remain separate workflows.

## 2026-06-21 - B->S down-regime gating is asymmetric

- Decision: B->S in `WEAK_DOWN` can be allowed only as reduced-size probe after side-specific trigger and exhaustion checks pass.
- Decision: B->S in `STRONG_TREND_DOWN` requires a higher regime-adjusted deviation score and strong downside exhaustion before it can move from watch to trigger.
- Decision: B->S in `CRASH_DOWN` remains blocked rather than mechanically adding into weakness.
- Rationale: Long-holder T logic should distinguish repairable below-VWAP deviations from trend-following downside or crash conditions.
- Consequence: B->S triggers become more selective and can be smaller than the configured base T size; this changes guidance semantics only, not execution, fills, or countable cost-basis accounting.

## 2026-06-20 - Lifecycle markers use staged diagnostic states

- Decision: Chart lifecycle markers should not use generic `OPEN`; they should distinguish `WATCH`, `PROBE`, `ADD`, `CONFIRM`, `CLOSE_READY`, `FORCED_DECISION`, `BLOCKED`, and `EXPIRED`.
- Decision: BS diagnostics should include downside exhaustion and VWAP-anchor classification before regime/sizing policy is hardened.
- Rationale: The operator needs to see whether the model is early probing, adding, confirming, or simply reacting late after a bounce.
- Consequence: The UI can now audit why a minute did or did not trigger without implying execution, fills, PnL, or cost-basis reduction.

## 2026-06-20 - Research audit modules require explicit execution

- Decision: Scenario evaluation, locked-OOS threshold experiments, model-change audit, and baseline update review belong on `Research / Audit`, not on intraday or execution pages.
- Decision: Each research/audit module should remain idle until the user clicks its run/load button.
- Rationale: These modules load datasets, run baselines, verify locks, and perform governance checks; they are not required for current trading guidance.
- Consequence: Live and execution refreshes become lighter, while research controls remain available for deliberate validation.

## 2026-06-20 - Risk caveats appear as a strip before detailed tables

- Decision: The homepage should show data/source/account risk first as a compact status strip, not as full caveat and quality tables.
- Decision: Detailed `Data source caveats` and `Data quality details` should be collapsed by default and auto-expand only for BAD data or actionable unconfirmed signals.
- Rationale: Professional users need the risk gate visible, but the homepage should prioritize current action, status, and chart context.
- Consequence: Risk warnings remain present without crowding the main trading workflow.

## 2026-06-20 - Live trading decision takes render priority

- Decision: The intraday page should render `Trading decision` and core market metrics before secondary disclosure, data quality, summary, layer, lifecycle, and review panels.
- Decision: Persisted position state is opt-in; when disabled, the app does not load from or save to the position-state file during reruns.
- Rationale: In live use, the user needs the freshest action first, and optional state persistence should not create hidden I/O or stale defaults.
- Consequence: Analysis panels remain available lower on the page or on the review page, but the hot path prioritizes current model guidance.

## 2026-06-20 - Intraday and review workloads are separated

- Decision: The default dashboard page should be `Intraday trading` and should not load execution journals, closeout review, scenario evaluation, locked-OOS experiments, model audit, or baseline review.
- Decision: Those panels belong on `Execution & research review`, where the user deliberately opts into heavier computation and audit side effects.
- Rationale: Streamlit reruns on interaction, so live chart/replay workflows should keep unrelated review work out of the hot path.
- Consequence: The app is more responsive during intraday use, while research hygiene panels remain available when explicitly opened.

## 2026-06-20 - Replay chart selection uses local minute keys

- Decision: Replay chart selection should use a local string `time_key` for event payloads, not the temporal x-field directly.
- Decision: The invisible interaction layer should use full-height minute rules so users can click anywhere inside the chart plot area.
- Rationale: Temporal payloads can be serialized through browser time conventions, and small point hit targets make chart replay feel unreliable.
- Consequence: The x-axis remains time-based for display, but replay state is resolved from a stable local exchange-minute key.

## 2026-06-20 - Replay charts may show full context while model input remains as-of

- Decision: Replay-at-time should keep full-session price and ratio charts visible as context, even though model input is truncated to `bars[:selected_minute]`.
- Decision: As-of outputs remain the decision summary, market metrics, current marker, lifecycle scan, and layer diagnostics.
- Rationale: Hiding all later chart bars makes early replay selections look like data failure and prevents selecting another minute without returning to live.
- Consequence: The UI must clearly state that future visible chart bars are context only and are not used in the selected model state.

## 2026-06-20 - Sparse Yahoo current sessions fall back to latest usable day

- Decision: If Yahoo/Korea `range=1d` returns too few closed-minute bars, the adapter should fetch a 5-day window and use the latest session with enough bars.
- Decision: The dashboard should display the selected session date and bar count in the intraday caption.
- Rationale: A one-point off-hours chart is not useful decision support and can be mistaken for a model failure.
- Consequence: Non-trading-time Yahoo views now prefer the previous usable trading day, but the feed remains public/prototype and not broker-confirmed.

## 2026-06-20 - Replay-at-time is model-only unless state snapshots exist

- Decision: Replay-at-time should recompute market features and `TriggerEngine` output from `bars[:selected_minute]`, so no future bars after the selected closed minute are used.
- Decision: Manual fills, broker imports, execution journals, post-trade review, risk usage, closeout, and account snapshots must remain live/current until the app stores versioned historical state snapshots.
- Rationale: Mixing as-of market replay with current broker/account evidence would be misleading unless the account state is explicitly time-versioned.
- Consequence: Replay mode can answer "what would the model have shown then?" but cannot answer "what was my exact execution/accounting state then?".

## 2026-06-20 - Keep Streamlit calls on current width API

- Decision: Dashboard layout calls should use `width="stretch"` instead of deprecated `use_container_width=True`.
- Rationale: Deprecation warnings obscure real runtime issues and the current API preserves the same stretched layout behavior.
- Consequence: This is a presentation/runtime maintenance change only; it does not alter model behavior, execution state, or evaluation evidence.

## 2026-06-20 - Current chart marker is current guidance, not execution

- Decision: The intraday price chart should always display the current latest-closed-minute `TradeIntent` marker, even when historical SB/BS lifecycle markers are hidden.
- Decision: Historical lifecycle markers remain signal-only and optional; the current marker is also signal-only and must not imply an order, fill, realized PnL, or cost-basis reduction.
- Rationale: Professional users need to distinguish the current decision from back-scanned opportunity windows while keeping the no-execution-inference boundary clear.
- Consequence: The chart can guide the next manual check, but broker-confirmed data, ticket feasibility, fills, restored inventory, and fees/slippage still control any countable result.

## 2026-06-18

- KEEP: Build core engine before dashboard.
- KEEP: V1 implements S->B only; B->S and ML are deferred.
- KEEP: Use deterministic synthetic scenarios before real data.
- KEEP: Treat strategy validity as unproven; V1 verifies accounting and replay mechanics.
- KEEP: Fill candidate orders no earlier than the next minute open.
- KEEP: Suppress opening trades when signal-time expected round-trip edge does not cover configured fees and slippage.
- KEEP: Treat fee defaults as placeholders until broker-specific and official fee sources are pinned.
- KEEP: User-facing Streamlit and CLI trigger output must use `TradeIntent`; individual layers should not assemble their own prompt text.
- KEEP: Current Streamlit input is deliberately small: stock code, held shares, and purchasable shares first; advanced controls are optional.
- KEEP: Non-A-share support must enter through explicit market/data-source selection instead of weakening A-share sellability assumptions.
- KEEP: Korean/Yahoo support uses 1-share lot size, 15:30 close, and ±30% price-limit risk defaults; Yahoo turnover amount is marked as an approximation, not research-grade成交额.

- KEEP: Actionable `TRIGGER_*` intents must pass the signal quality gate: trigger-level deviation score, liquidity confirmation via `min_amount_ratio`, and post-cost edge via `min_net_edge`. Failing any gate remains watch-only.
- KEEP: Trigger-engine user-facing reason strings should stay ASCII-safe until the project standardizes encoding and localization.

- KEEP: User-facing decision summaries must separate recommendation, evidence, invalidation, position impact, and caveats instead of blending them into a single prompt string.
- KEEP: Every decision summary must include a caveat that cost-basis reduction is unrealized until both legs close, target inventory is restored, and fees/slippage are deducted.

- KEEP: Evaluation reports must compare no-trade, a simple interpretable replay baseline, and trigger-engine signal diagnostics side by side.
- KEEP: Trigger-engine evaluation rows are signal diagnostics only; they must not infer fills, realized PnL, or cost-basis reduction.

- KEEP: Dashboard decision output must be preceded by a data-quality rollup covering freshness, coverage, sparse volume, and amount quality.
- KEEP: Yahoo/Korea turnover amount must be treated as approximate and shown as a confidence-downgrading caveat.

- KEEP: Dashboard chart markers should show opportunity lifecycle state, not repeated raw prompt snapshots.
- KEEP: Lifecycle states are signal-only. `OPEN`, `CLOSE_READY`, `EXPIRED`, and `BLOCKED` must not infer fills, realized PnL, or cost-basis reduction.

- KEEP: Dashboard and CLI monitoring should share a persisted user position state by default.
- KEEP: Explicit CLI arguments override persisted position state; saved state is a convenience layer, not an execution or brokerage source of truth.
- KEEP: Runtime position state belongs under `.runtime/` and should not be committed.

- KEEP: Dashboard must show evaluation comparisons in-app, not only through CLI JSON.
- KEEP: Dashboard evaluation rows remain synthetic research comparisons and must label trigger rows as signal-only, with no fills or realized PnL inferred.

- KEEP: Live dashboard and CLI trigger guidance must default to a costed fee profile, not zero fees.
- KEEP: `zero_fee_research` and `--ignore-fees` are explicit research/sensitivity modes only and must not be treated as live guidance.
- KEEP: Fee presets are operational assumptions; broker-specific statements and current tax/fee schedules remain the source of truth.

- KEEP: Every evaluation/performance row must be backed by a dataset registry record and explicit `in_sample` or `out_of_sample` split label.
- KEEP: Unregistered scenarios should fail instead of appearing in performance tables.
- KEEP: Current synthetic fixtures are `in_sample`; with zero registered OOS rows, profitability and production-validity claims remain prohibited.

## 2026-06-20 - Manual fills are required for execution state
- Decision: Signals, lifecycle labels, and chart markers remain decision support only; they do not imply broker execution.
- Decision: Open-pair close/restore progress must be based on manually recorded broker fills until broker-confirmed import is available.
- Rationale: This avoids falsely counting cost-basis reduction from recommendations that were never actually filled.
- Consequence: The app can show a close candidate, but operational state remains incomplete until the user records the matching fill.

## 2026-06-20 - Public quote feeds are not broker-confirmed market data
- Decision: Eastmoney and Yahoo Finance inputs must be labeled as research/prototype feeds, not broker-confirmed market data.
- Decision: Delay and licensing status must be shown before live guidance is interpreted.
- Rationale: Professional users need to separate decision support from executable broker data, account holdings, order acceptance, and final fills.
- Consequence: Any action still requires broker-confirmed price, sellable quantity/cash, order status, and fills.

## 2026-06-20 - Persisted position state must be reconciled before action
- Decision: Persisted dashboard/CLI position state is a convenience cache, not broker truth.
- Decision: If persisted total, sellable, or purchasable capacity exceeds broker/manual snapshot values, live action should be treated as blocked until reconciled.
- Rationale: Overstated sellable shares or buying capacity can turn a useful signal into an invalid or rejected order.
- Consequence: Professional use requires broker-confirmed holdings/cash/order status before executing guidance.

## 2026-06-20 - Actionable signals require pre-trade ticket checks
- Decision: `TRIGGER_*` signals are not sufficient for action; they must pass a pre-trade checklist before manual order entry.
- Decision: Missing broker snapshot, symbol mismatch, invalid lot size, insufficient sellable quantity, insufficient cash, or zero-fee research assumptions block the ticket.
- Rationale: Professional decision support must separate signal quality from order-entry feasibility and broker-preview costs.
- Consequence: A signal can be analytically valid while still being operationally blocked.

## 2026-06-20 - Locked OOS rows must be hash checked
- Decision: Real OOS CSV datasets must be registry-backed and SHA-256 checked before evaluation.
- Decision: A single locked OOS row is useful for regression discipline but still insufficient for profitability or production-validity claims.
- Rationale: Silent data edits or accidental in-sample reuse would contaminate model evaluation.
- Consequence: Future model changes can be judged against a stable OOS row, but broader validation requires more independent symbols/dates.

## 2026-06-20 - Single-point edge is not enough for actionable guidance
- Decision: Actionable guidance must include execution-quality sensitivity bands, not only one estimated net edge.
- Decision: If worse-fill bands exhaust edge, the signal should be treated as fragile or blocked even if the base estimate is positive.
- Rationale: Professional users need to know whether the recommendation survives realistic adverse fills and slippage expansion.
- Consequence: The app separates signal edge from execution robustness; no band implies a routed order or confirmed fill.

## 2026-06-20 - OOS coverage must span independent symbols and dates
- Decision: Locked OOS evaluation should include multiple symbols and dates, not a single convenient sample.
- Decision: Public Yahoo/Eastmoney OOS rows can support regression discipline, but their feed limitations remain visible and they cannot prove profitability.
- Rationale: A model can pass one date or one symbol by accident; independent coverage reduces but does not eliminate overfitting risk.
- Consequence: The app now evaluates 5 locked OOS rows, but production-validity claims remain prohibited until broader, broker/licensed-data validation exists.

## 2026-06-20 - Trigger changes require locked OOS audit
- Decision: Trigger-threshold changes must be compared against a stored locked OOS baseline before being interpreted as improvements.
- Decision: Audit deltas are review prompts, not profitability or production-validity evidence.
- Rationale: A threshold change can silently alter trigger/watch/no-trade counts even when unit tests pass.
- Consequence: Future model edits can be checked through `python -m app.cli audit` before updating the baseline intentionally.

## 2026-06-20 - OOS capture is controlled intake, not automatic registration
- Decision: New locked OOS files should be captured through `python -m app.cli capture-oos` so the normalized CSV and SHA-256 are reproducible.
- Decision: The capture command must emit registry metadata for review but must not automatically add the dataset to `DATASET_REGISTRY`.
- Rationale: OOS rows are evaluation assets; auto-registering convenient captures would weaken the audit boundary and increase overfitting risk.
- Consequence: A human must still review provenance, symbol/date independence, feed limitations, and existing in-sample exposure before adding a captured row to the locked registry.
## 2026-06-20 - Threshold experiments must not mutate the audit baseline
- Decision: Candidate threshold sets should be evaluated through `python -m app.cli threshold-experiments` before any baseline update is considered.
- Decision: Experiment output is a what-if delta report only; it must not write `research/baselines/locked_oos_audit_baseline_v1.json`.
- Rationale: Parameter tuning can easily overfit a small locked-OOS set, so the first artifact should be a review report rather than a promoted model.
- Consequence: Baseline updates require a separate explicit workflow and review step; experiment deltas alone do not justify profitability, production validity, or live trading claims.
## 2026-06-20 - Baseline updates require explicit review token
- Decision: `audit-baseline-update` defaults to preview-only behavior and must not write the baseline without an exact review token.
- Decision: Writes are allowed only when the current audit has deltas and the token `APPROVE_LOCKED_OOS_BASELINE_UPDATE` is supplied after review.
- Rationale: Updating the baseline erases drift signals, so it must be treated as a deliberate governance action rather than a routine validation step.
- Consequence: Baseline promotion can document reviewed current behavior, but it remains a regression reference and does not imply profitability, realized PnL, or production validity.
## 2026-06-20 - Dashboard threshold experiments are review aids only
- Decision: Dashboard threshold experiment tables should show aggregate and per-scenario locked-OOS signal deltas, not inferred fills or realized PnL.
- Decision: More triggers, fewer triggers, or fewer watch states must not be labeled as better without separate evidence.
- Rationale: Threshold exploration is useful for review, but visual tables can create false confidence if signal-count deltas are treated as strategy performance.
- Consequence: The dashboard makes experiments easier to inspect while preserving the no-profitability-claim boundary.
## 2026-06-20 - Intraday sizing must respect explicit risk presets
- Decision: Named risk presets should cap sizing by max round-trip turnover, max open-pair minutes, and max same-day capital at risk.
- Decision: The default `balanced` preset preserves the previous 10% single-pair behavior, while `defensive` and `active` make the operator's risk posture explicit.
- Rationale: Professional users need guardrails that constrain operational exposure before interpreting a trigger as actionable.
- Consequence: Suggested quantity can be lower than `max_t_ratio` when a preset is tighter; this is a risk-control cap, not a performance improvement claim.
## 2026-06-20 - Manual fills require post-trade review
- Decision: Manual fills must be compared back to the pre-trade ticket and execution sensitivity bands before being treated as clean execution evidence.
- Decision: Missing fills, overfills, adverse price versus ticket, missing cost records, blocked tickets, or exhausted sensitivity bands must surface as review warnings or blocks.
- Rationale: Professional users need a closed loop from signal to ticket to actual broker fill; otherwise manual entries can create false confidence.
- Consequence: A recorded fill can support operational review, but it still does not prove profitability or realized cost-basis reduction until the complete pair/accounting conditions are met.

## 2026-06-20 - Risk usage is consumed only by manual fills
- Decision: Live-session risk usage must be computed from manual broker fills only, not from signals, chart markers, or pre-trade tickets.
- Decision: The selected risk preset should be evaluated against daily turnover quantity, unclosed same-day capital at risk, and open-pair age.
- Rationale: A professional operator needs to know whether more intraday risk can be added after real fills, while avoiding false risk usage from unexecuted recommendations.
- Consequence: A trigger can still be analytically valid while the session risk usage report blocks adding exposure because the day is already at or above preset limits.

## 2026-06-20 - Broker imports are reconciliation evidence, not automatic fills
- Decision: Broker fill exports may be imported for reconciliation preview, but they must not automatically mutate manual fills.
- Decision: Exact symbol/side/qty/price/timestamp matches are accepted as reconciled; broker-only, manual-only, and ambiguous duplicate rows require operator review.
- Rationale: Broker exports confirm execution facts, but they still do not identify the strategy pair context unless the operator maps them deliberately.
- Consequence: A broker-only fill can guide manual-fill correction, but it cannot affect post-trade review, session risk usage, or cost-basis accounting until explicitly recorded with pair context.

## 2026-06-20 - Execution journal is read-only audit evidence
- Decision: Session execution journals should link signal, ticket, manual fills, broker reconciliation, post-trade review, and risk usage into one ordered audit report.
- Decision: Journal status may summarize warnings and blockers, but it must not mutate fills, broker rows, position state, or accounting ledgers.
- Rationale: Professional users need one place to see where the execution chain is incomplete or blocked without confusing an audit view for execution authority.
- Consequence: A clean journal improves operational review, but it still does not prove profitability, route orders, or count cost-basis reduction.

## 2026-06-20 - Broker-only rows require reviewed promotion

- Decision: Broker-import rows are not auto-written into manual fills.
- Decision: A broker-only row may be promoted only when an operator supplies a pair assignment and the exact review token `APPROVE_BROKER_FILL_PROMOTION`.
- Decision: Promotion must preserve broker provenance in the manual-fill note and must block duplicate exact fill keys.
- Rationale: Broker exports can contain partials, corrections, ambiguous timestamps, or rows unrelated to the app's intended pair; professional workflow needs explicit review before execution state changes.
- Consequence: Broker reconciliation can reduce manual typing, but it still cannot create realized PnL or cost-basis claims by itself.

## 2026-06-20 - Execution journals are persisted audit snapshots

- Decision: Session execution journals should be saved under `.runtime/execution_journals` by default.
- Decision: Saved journals are immutable-style review snapshots for operator comparison, not brokerage truth and not accounting events.
- Decision: CLI/dashboard may display recent saved journals to support end-of-day review, but manual fills, broker reconciliation, inventory restoration, and fees/slippage remain the authoritative inputs for cost-basis accounting.
- Rationale: Professional users need a cross-session audit trail of signal, ticket, fills, broker reconciliation, post-trade review, and risk usage.
- Consequence: The app can now preserve session context for review, but a saved journal alone cannot prove execution quality or profitability.
## 2026-06-20 - End-of-day closeout gates cost-basis accounting

- Decision: Countable cost-basis reduction requires closed manual pairs, complete broker reconciliation, restored inventory, and no blocked risk usage metric.
- Decision: If any gate is blocked, `countable_cost_basis_reduction` must be zero even if a gross pair spread appears favorable.
- Decision: No manual fills produces `NO_ACTION`, not an implied clean accounting result.
- Rationale: Professional review must prevent signals, partial fills, unmatched broker exports, or unresolved open exposure from becoming false realized accounting claims.
- Consequence: The app can now separate operational session review from countable cost-basis evidence.
## 2026-06-20 - Compact EOD review is audit navigation only

- Decision: The compact end-of-day review may compare current closeout state with recent persisted journals.
- Decision: The review must not override closeout gates or create accounting events.
- Decision: Recent blocked or warning journals should keep the review blocked/warning even if the current closeout appears clean.
- Rationale: A professional operator needs quick triage across session artifacts before final signoff.
- Consequence: The app is easier to review at EOD, while broker reconciliation, restored inventory, and risk closeout remain the authority.
## 2026-06-20 - Closeout requires per-pair attribution

- Decision: End-of-day closeout should expose per-pair attribution, not only aggregate session status.
- Decision: A pair is countable only when it is closed, broker-matched, and included in a countable session closeout.
- Decision: Open or unmatched pairs must carry a blocking reason in the review output.
- Rationale: Professional review needs to locate the exact pair causing a blocked closeout or accounting exclusion.
- Consequence: Operators can audit pair-level evidence before signoff without changing the strict session-level gates.
## 2026-06-20 - Closeout signoff writes require explicit review

- Decision: EOD signoff export must be preview-first and write only with the exact token `APPROVE_EOD_CLOSEOUT_SIGNOFF`.
- Decision: Signoff writes are allowed only for countable closeouts or no-action closeouts; blocked or warning closeouts remain non-signable.
- Decision: Dashboard shows signoff readiness but does not write files during refresh.
- Rationale: A reviewed snapshot is useful for professional audit workflow, but automatic writes or blocked-state signoffs would create false assurance.
- Consequence: Signoff artifacts can support review continuity, but they are not broker truth, accounting events, or profitability evidence.

## 2026-06-20 - Dashboard entrypoint owns repository path bootstrap

- Decision: `app/dashboard.py` should make the repository root importable when executed directly by Streamlit Cloud.
- Decision: The bootstrap is limited to `sys.path` setup before project imports and must not alter runtime model behavior.
- Rationale: Local runs often start from the repository root, while Streamlit Cloud may execute the dashboard file with `app/` as the script directory.
- Consequence: Cloud deployment can import project packages consistently without requiring users to tune `PYTHONPATH` manually.

## 2026-06-20 - Locked OOS hashes are LF-normalized

- Decision: Locked CSV dataset hashes should be computed from canonical LF-normalized content.
- Decision: `datasets/oos/*.csv` should be pinned to LF in `.gitattributes`.
- Rationale: Git line-ending conversion can otherwise make the same registered dataset pass on Windows and fail on Linux deployment.
- Consequence: Hash checks remain strict on content while avoiding platform-specific CRLF/LF mismatches.

## 2026-06-20 - Research dashboard panels should not cascade-fail

- Decision: Scenario evaluation, threshold experiments, model-change audit, and baseline update review should render independently.
- Decision: If one panel fails, the dashboard should show a scoped error/warning and continue with later panels.
- Rationale: A single locked dataset or evaluation issue should not hide unrelated audit controls from the operator.
- Consequence: Dashboard visibility is improved, but panel-level failures still require investigation before interpreting that specific panel.

## 2026-06-20 - Dashboard reloads project modules after deploy

- Decision: The Streamlit dashboard should clear cached project submodules before importing dependencies.
- Decision: This cache refresh is limited to local project prefixes: `app.`, `core.`, `data.`, and `research.`.
- Rationale: Streamlit reruns the script inside a long-lived process; stale imported modules can otherwise survive code redeploys and produce impossible mixed-version states.
- Consequence: Deployment behavior is more deterministic, while runtime data state and trading logic remain unchanged.
