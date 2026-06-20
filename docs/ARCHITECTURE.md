# Architecture

## Layers

- `core/`: rules, fees, inventory ledger, pair state machine, accounting metrics.
- `data/`: CSV adapter and bar validation.
- `research/`: features, trigger engine, baseline strategy, fill simulation, replay, scenarios, evaluation.
- `app/`: CLI, monitor, notification, and Streamlit entrypoints.
- `tests/`: unit and scenario tests.

## Trigger Engine

`research.trigger_engine.TriggerEngine` is the main prompt path for UI usage:

`MarketData + PositionState + FeeModel + RulesConfig -> FeatureSnapshot -> RegimeDecision -> DeviationDecision -> InventoryDecision -> TradeIntent`

The layers are intentionally serial:

- Regime blocks unsuitable market states first.
- Deviation estimates whether the current displacement has enough gross/net edge.
- Inventory checks A-share sellability, purchasable quantity, open-pair priority, lot size, and maximum inventory deviation.
- TradeIntent is the only user-facing output object.

This avoids single-indicator triggering. VWAP deviation can create a candidate, but it cannot produce a trigger unless regime, net edge, and inventory all pass.

## Replay Contract

At minute `t`, the strategy may only use bars up to and including `t`. If it emits an order, V1 simulates a conservative market fill at the next minute open and records the fill timestamp as that next minute. This avoids using the current bar high/low to manufacture ideal fills.

Before opening an S->B Pair, replay applies a round-trip cost gate using only information available at signal time: signal price, planned buyback price, configured fees, and configured slippage. If the expected gross spread cannot cover estimated costs, the order is suppressed.

## Accounting Contract

Closed cost-basis benefit requires:

1. sell leg and buy leg both exist;
2. quantities match;
3. all fees and slippage are deducted;
4. end-of-day inventory restoration is reported separately.
