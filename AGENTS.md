# Project Rules

- Build the core research engine before UI.
- Never claim profitability without strict out-of-sample evidence.
- Only count cost-basis reduction after both legs are closed, target inventory is restored, and all fees/slippage are deducted.
- Model A-share sellability explicitly: today-bought shares are locked and cannot be sold on the same day.
- Do not fabricate Level-2 or order-book features from minute OHLCV data.
- Avoid future leakage: signal on closed minute `t`, fill no earlier than minute `t+1`.
- Compare every candidate with a no-trade baseline and a simple interpretable baseline.
- Keep docs current: `docs/LOOP_STATE.md`, `docs/RESEARCH_LOG.md`, `docs/DECISIONS.md`, and `docs/EVALUATION.md`.
