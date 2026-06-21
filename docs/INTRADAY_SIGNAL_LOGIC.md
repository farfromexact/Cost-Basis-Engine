# 日内信号触发逻辑说明

本文档说明当前 repo 中 B->S / S->B 日内 T 信号的触发逻辑、风控边界和 UI 中 lifecycle 标记的含义。

代码源头以 `research/trigger_engine.py` 和 `research/opportunity_lifecycle.py` 为准。本文档是对当前实现的结构化解释，不构成收益承诺。

## 1. 目标和边界

系统目标不是预测当天最高点或最低点，而是服务于长期持有单一 A 股底仓时的日内成本优化：

- `S->B`: 先卖出一部分已结算可卖底仓，后续买回，目标是在不改变目标底仓的前提下降低持仓成本。
- `B->S`: 先买入一部分临时仓位，后续用原本已结算可卖底仓卖出恢复，目标是在价格偏低并出现可修复机会时降低成本。
- 只在信号层、决策层和复盘层提供参考，不自动推断真实成交、真实 PnL 或真实成本降低。
- 成本降低只有在双腿闭合、目标库存恢复、费用和滑点扣除后才可以计入。

关键限制：

- A 股 T+1 卖出约束必须显式建模。今天买入的股份当天不能卖出。
- 信号基于已闭合分钟线 `t` 计算，最早成交假设不得早于 `t+1`。
- 不从分钟 OHLCV 中伪造 Level-2、盘口队列、真实逐笔成交或券商确认数据。
- 没有严格 out-of-sample 证据时，不声称模型有盈利能力。

## 2. 核心链路

当前触发引擎的主链路是：

```text
Minute bars + PositionState + FeeModel + RulesConfig
-> FeatureSnapshot
-> RegimeDecision
-> DeviationDecision
-> InventoryDecision
-> TradeIntent
```

含义：

- `Minute bars`: 已闭合分钟 OHLCV/amount 数据。
- `PositionState`: 目标底仓、当前持仓、已结算可卖数量、当日已买/已卖、现金和进行中的 T pair。
- `FeeModel`: 佣金、印花税、滑点等交易成本估计。
- `RulesConfig`: 时间窗、偏离阈值、风控限制、趋势门控、lifecycle 约束等参数。
- `FeatureSnapshot`: 从分钟线计算出来的价格、VWAP、偏离、趋势、流动性、耗竭度等特征。
- `RegimeDecision`: 判断当前市场状态是否允许做某一侧信号，以及是否需要降仓位或提高触发阈值。
- `DeviationDecision`: 判断当前价格相对 VWAP/锚点是否进入 S->B 或 B->S 观察区。
- `InventoryDecision`: 判断建议数量是否满足 A 股库存、现金、可卖股和风控约束。
- `TradeIntent`: 输出最终动作，例如 `NO_TRADE`、`WATCH_*`、`TRIGGER_*`、`MANAGE_OPEN_PAIR`。

## 3. 特征快照 FeatureSnapshot

每一分钟先生成一份 `FeatureSnapshot`。它是后续所有判断的基础。

主要字段：

- `price`: 当前已闭合分钟的最新价格。
- `vwap`: 当日截至当前分钟的成交额加权均价。
- `anchored_vwap`: 盘中锚定 VWAP，用于辅助判断价格修复目标。
- `vwap_deviation`: 当前价格相对 VWAP 的偏离。
- `day_return`: 当前价格相对开盘价的涨跌幅。
- `day_position`: 当前价格在当日高低区间中的位置。
- `recent_return`: 最近窗口的价格变化。
- `recent_high_breaks` / `recent_low_breaks`: 近期突破高点或低点的次数。
- `amount_ratio`: 当前成交额相对近期成交额的活跃度。
- `time_normalized_zscore`: 时间标准化后的偏离强度。
- `exhaustion_score`: 下跌耗竭或修复条件的综合分数，主要服务于 B->S。
- `anchor_type`: VWAP 当前更像修复目标、阻力位，还是中性参考。
- `minutes_to_close`: 距离收盘的分钟数。
- `near_upper_limit` / `near_lower_limit`: 是否接近涨跌停风险区。

这些特征只来自已闭合分钟线，不使用未来分钟。

## 4. 第一步：Regime gate

`RegimeDecision` 先判断当前市场状态，决定是否允许开新 T pair，以及是否需要软门控。

### 4.1 硬门控

以下情况会直接阻止新开仓或阻止某一侧信号：

- 开盘噪音窗口：早于 `start_time`，默认 09:45 之前不打开新 T pair。
- 太晚开仓：晚于 `latest_open_time`，默认 14:35 之后不再打开新 T pair。
- 强制恢复窗口：晚于 `force_restore_time`，默认 14:50 之后进入恢复/收尾优先。
- 涨跌停风险：接近涨停或跌停时不允许用普通均值回归逻辑开新 pair。
- 极低流动性：`amount_ratio` 太低时不允许交易。

### 4.2 市场状态和侧向门控

当前实现把市场大致分为：

- `RANGE` / `MEAN_REVERTING`: 默认区间或均值回归状态，允许双侧观察。
- `STRONG_TREND_UP`: 强上行趋势，通常压制 `S->B`，避免过早卖飞。
- `WEAK_DOWN`: 弱下行趋势，`B->S` 只允许更小尺寸、更高触发要求的 probe。
- `STRONG_TREND_DOWN`: 强下行趋势，`B->S` 只允许更严格的耗竭确认和更小尺寸 probe。
- `CRASH_DOWN`: 崩跌状态，阻止 `B->S`，避免在未确认修复时接下跌刀。
- `LIMIT_RISK` / `ILLIQUID` / `LATE_SESSION`: 风险或时间状态，不适合打开普通新 pair。

### 4.3 Soft regime sizing

不是所有趋势状态都直接禁止交易。部分状态采用软门控：

- 降低建议仓位，例如弱下行或强下行中对 `B->S` 使用更低 position multiplier。
- 提高触发要求，例如趋势下行中要求更高 deviation score。
- 对 `B->S` 增加 downside exhaustion 要求，避免仅因为低于 VWAP 就机械买入。

这使模型可以区分：

- 完全不能做。
- 可以观察但不能触发。
- 可以小仓 probe。
- 可以正常确认。

## 5. 第二步：Deviation candidate

`DeviationDecision` 判断价格偏离是否进入候选区。

### 5.1 S->B 逻辑

当价格显著高于 VWAP 时，进入 `S->B` 候选：

```text
price > VWAP
vwap_deviation >= sb_watch_deviation
```

直觉：

- 价格高于日内成交重心。
- 如果持有可卖底仓，先卖出一小部分。
- 等价格向 VWAP 或预期回归区间回落后买回。

输出内容包括：

- expected reversion price。
- invalidation price。
- gross edge。
- fee/slippage adjusted net edge。
- deviation score。
- reason code，例如 `SB_ABOVE_VWAP`。

### 5.2 B->S 逻辑

当价格显著低于 VWAP 时，进入 `B->S` 候选：

```text
price < VWAP
vwap_deviation <= bs_watch_deviation
```

直觉：

- 价格低于日内成交重心。
- 只有当下跌出现一定修复条件或耗竭迹象时，才考虑先买入临时仓位。
- 后续用原有已结算可卖底仓卖出恢复目标库存。

B->S 不是“低于 VWAP 就买”。它还会检查：

- VWAP 是否可能成为阻力而不是修复目标。
- downside exhaustion score 是否足够。
- 是否仍在连续破低。
- 趋势状态是否要求更高触发阈值。
- 是否有足够原底仓可用于当天恢复。

### 5.3 VWAP resistance downgrade

如果价格低于下行 VWAP，且 VWAP 更像阻力位而不是自然回归目标，B->S 的目标会被降级为更保守的 partial repair。

这避免把所有低于 VWAP 的情况都误判为可均值回归。

## 6. 第三步：Signal quality gate

偏离进入候选区后，还要经过质量门控。

主要检查：

- `deviation_score` 是否达到全局和侧向阈值。
- regime 是否提高了触发 multiplier。
- `B->S` 在弱下行或强下行中，`exhaustion_score` 是否达到 probe/confirm 要求。
- `amount_ratio` 是否达到流动性要求。
- 扣除费用、滑点和风险缓冲后，`net_edge` 是否仍然为正。

如果没有通过质量门控，输出通常是 `WATCH_S_TO_B` 或 `WATCH_B_TO_S`，而不是 trigger。

这类 WATCH 的含义是：

- 价格方向进入观察区。
- 但信号质量、流动性、趋势或 edge 还不够。
- 不应直接视为可交易信号。

## 7. 第四步：Inventory and execution feasibility

即使信号质量足够，也必须满足库存和风控约束。

### 7.1 S->B 库存约束

`S->B` 必须使用已结算可卖底仓：

```text
settled_sellable_qty >= suggested_qty
```

原因：

- 今天买入的股份当天不能卖。
- 不能把不可卖股份当成可卖库存。
- 先卖后买必须保证卖出腿真实可执行。

### 7.2 B->S 库存约束

`B->S` 必须同时满足：

```text
purchasable_qty >= suggested_qty
settled_sellable_qty >= suggested_qty
cash >= estimated_buy_notional if cash is provided
```

原因：

- 买入腿需要现金或购买能力。
- 当天买入的股份不能用于当天卖出。
- 后续卖出恢复只能依赖原本已结算可卖底仓。

所以 B->S 本质上不是“今天买了今天卖”，而是：

```text
先买入临时仓位
再卖出原有可卖底仓
最终恢复目标库存
```

### 7.3 数量约束

建议数量还会受以下参数约束：

- `lot_size`: A 股按手数取整，默认 100 股。
- `minimum_order_qty`: 最小下单数量，默认 100 股。
- `max_t_ratio`: 单次 T pair 相对目标底仓的最大比例。
- `max_single_trade_qty`: 单笔交易上限，如果配置。
- 风险 preset 下的日内周转、同日风险资本、beta 暴露等约束。
- regime position multiplier，例如下行趋势中降低 B->S 尺寸。

如果数量取整后低于最小下单量，输出 `NO_TRADE` 或 watch，不触发。

## 8. TradeIntent 输出

最终输出是 `TradeIntent`。

主要 action：

- `NO_TRADE`: 当前不建议交易。
- `WATCH_S_TO_B`: S->B 进入观察，但未达到触发条件。
- `WATCH_B_TO_S`: B->S 进入观察，但未达到触发条件。
- `TRIGGER_SELL_TO_BUY`: S->B 达到触发条件。
- `TRIGGER_BUY_TO_SELL`: B->S 达到触发条件。
- `MANAGE_OPEN_PAIR`: 已有 open pair，需要管理后续腿。
- `FORCE_CLOSE_OR_RESTORE`: 进入收盘恢复或强制决策窗口。

TradeIntent 同时包含：

- `confidence`
- `suggested_qty`
- `expected_price`
- `invalidation_price`
- `estimated_fee`
- `net_edge`
- `reasons`
- `blockers`
- `feature snapshot`
- `regime/deviation/inventory decision`

## 9. Opportunity lifecycle 标记

UI 图上的 signal marker 来自 `research/opportunity_lifecycle.py`。它是 signal-only 复盘，不代表真实成交。

扫描方式：

```text
for each closed minute t:
    evaluate TriggerEngine on bars[:t]
```

也就是说，每一分钟的判断只使用当时已经闭合的分钟，不使用未来数据。

### 9.1 常见状态

- `WATCH`: 进入观察区，但没有达到 trigger。
- `PROBE`: 达到 trigger，但更适合作为试探性小仓。
- `CONFIRM`: 达到更强确认条件。
- `ADD`: 同方向机会继续发展，且满足加腿约束。
- `CLOSE_READY`: 到达预期修复区，可以考虑闭合 pair。
- `FORCED_DECISION`: 接近收盘，需要恢复或做强制决策。
- `BLOCKED`: 信号被阻止，例如越过 invalidation、反向触发、加腿约束失败。
- `EXPIRED`: 等待太久没有到达 close-ready，机会过期。

### 9.2 PROBE 和 CONFIRM 的区别

当前实现中：

- B->S trigger 如果 downside exhaustion 足够强，更接近 `CONFIRM`；否则是 `PROBE`。
- S->B trigger 如果 deviation score 足够高，更接近 `CONFIRM`；否则是 `PROBE`。

这不是盈亏等级，而是信号成熟度标记。

### 9.3 ADD 约束

同方向追加不是无限加仓，必须满足：

- 同一方向仍然是 trigger。
- 未超过 `max_lifecycle_legs`。
- 累计建议数量未超过 `max_lifecycle_total_t_ratio * target_qty`。
- 距离上一次 leg 至少超过 `min_lifecycle_leg_spacing_minutes`。
- 价格相对上一 leg 有足够改善：
  - B->S 需要更低价格。
  - S->B 需要更高价格。
- 价格不能已经越过 invalidation。

如果方向继续恶化但不满足 ADD 约束，机会会被标为 blocked 或保持等待，而不是自动加仓。

## 10. Replay-at-time 的含义

当 UI 进入 replay-at-time 模式时，逻辑应是：

```text
用户选择某一分钟 t
-> 截取 bars[:t]
-> 用这部分已闭合分钟重新运行 TriggerEngine
-> 渲染当时的 TradeIntent / FeatureSnapshot / Regime / Deviation / Inventory
```

这回答的是：

```text
如果当时只知道 t 之前的数据，模型那一刻会怎么判断？
```

注意：

- replay 不应该使用 t 之后的 future bars 来生成当时的 TradeIntent。
- lifecycle 表可以只显示截至 t 已经发生的状态。
- broker fills、manual fills、execution journal 不会自动倒回到历史账户状态，除非未来实现账户快照。

## 11. Execution journal 和会计边界

日内信号和 lifecycle 不等于真实交易结果。

真正可计入成本降低，需要经过执行和收盘核验：

- 两条腿都已成交。
- 目标库存已恢复。
- A 股可卖约束没有被违反。
- 所有费用、印花税、滑点已经扣除。
- broker/manual fills 和 execution journal 能对应。
- closeout report 没有把未闭合 pair 错计入 realized reduction。

`app/session_ledger.py` 的 ledger 展示只负责把 closeout 结果分类为：

- 可计入的 realized reduction。
- 未闭合或被阻止的 non-countable pair cash。
- no-action day。

它不是信号生成器，也不会把 blocked 机会自动变成收益。

## 12. 当前模型不做什么

当前模型明确不做：

- 不预测日内最高点或最低点。
- 不声称有稳定盈利能力。
- 不从分钟线中推断真实盘口、Level-2 或队列位置。
- 不自动下单。
- 不把 chart marker 当成真实成交。
- 不把未闭合 pair 的浮动收益计入成本降低。
- 不允许今天买入的股份在同一天作为可卖库存使用。

## 13. 主要代码位置

- `research/trigger_engine.py`: 信号触发主引擎，包含 feature、regime、deviation、inventory、TradeIntent。
- `research/opportunity_lifecycle.py`: 逐分钟 lifecycle 扫描和图上 marker。
- `app/dashboard.py`: Streamlit 页面渲染、实时/回放模式、decision summary、图表展示。
- `app/session_ledger.py`: session closeout 后的 ledger 摘要。
- `docs/EVALUATION.md`: 评估和 OOS 约束说明。
- `docs/DECISIONS.md`: 重要设计决策记录。
- `docs/ARCHITECTURE.md`: 系统架构概览。

