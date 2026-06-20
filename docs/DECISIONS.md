# Decisions

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
