# Product Spec

本项目服务于已经独立决定长期持有某只 A 股股票的用户。系统只评估日内闭环库存再平衡是否相对不操作产生净收益，不提供长期投资建议，不连接券商，不自动执行交易。

V1 范围：

- 本地回放和合成场景。
- S->B：先卖出少量已交收底仓，随后买回同等数量。
- 盘中 `prompt`：基于最新分钟线提示 `SB_OPEN`、`BS_OPEN`、`SB_CLOSE`、`BS_CLOSE` 或 `HOLD`。
- 盘中 `monitor`：循环抓取最新分钟线，并通过 console/webhook/Bark/PushPlus 推送非 `HOLD` 提示。
- Streamlit dashboard：输入股票代码、已持有股数、可继续购买股数，输出三层触发后的 `TradeIntent`。
- TriggerEngine：统一输出 `NO_TRADE`、`WATCH_SELL_TO_BUY`、`TRIGGER_SELL_TO_BUY`、`WATCH_BUY_TO_SELL`、`TRIGGER_BUY_TO_SELL`、`MANAGE_OPEN_PAIR`、`FORCE_CLOSE_OR_RESTORE`。
- 账本、费用、库存偏离、未闭合 Pair 和相对不操作收益报告。

V1 不做：

- 先买后卖复杂策略。
- 机器学习。
- Level-2、逐笔委托、订单簿和真实排队。
- 自动下单。
