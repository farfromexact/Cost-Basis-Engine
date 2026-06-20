# 降本神器 / Cost Basis Engine

本项目是针对单一股票的本地研究、历史回放和盘中提示引擎。当前重点支持 A 股普通股票，也提供韩国股票的 Yahoo Finance 分钟线提示入口。它只研究“在目标持股数量约束下，闭环做 T 是否相对全天不操作产生净现金收益”，不判断长期投资价值，不自动下单，不承诺盈利。

## 当前能力

- 可配置买卖佣金、最低佣金、印花税、过户费、其他规费和滑点。
- 区分 `settled_sellable_qty` 与 `today_bought_locked_qty`，不会把今日买入误当作当日可卖。
- 支持一个最小 S->B 策略：先卖出少量已交收底仓，之后在更低价格买回同等数量。
- 支持三层触发引擎：`Regime -> Deviation -> Inventory -> TradeIntent`。
- 提供 Streamlit 页面，输入市场/数据源、股票代码、已持有股数、可继续购买股数后自动抓取最新分钟线并输出触发意图。
- 韩国股票入口使用 Yahoo Finance 分钟线，三星普通股可输入 `005930.KS`、`005930`、`三星`；三星优先股可输入 `005935.KS`。
- 逐分钟回放只在第 `t` 根分钟线结束后生成信号，并最早在第 `t+1` 根分钟线开盘模拟成交。
- 内置合成场景、无操作基准、核心指标报告和 pytest 测试。

## 快速运行

```powershell
python -m app.cli replay --scenario mean_revert --target-qty 1000 --settled-sellable-qty 1000 --trade-qty 100
python -m pytest
```

启动 Streamlit：

```powershell
streamlit run app/dashboard.py
```

页面核心输入：

- 市场/数据源；
- 股票代码；
- 已经持有股数；
- 可继续购买股数。

高级输入包括当前可卖股数、单次做 T 上限、是否暂不考虑佣金/税费，以及已有未闭合 Pair。

三层触发 CLI：

```powershell
python -m app.cli trigger --symbol 603236 --held-qty 151400 --purchasable-qty 15100 --ignore-fees
python -m app.cli trigger --data-source yahoo --symbol 005930.KS --held-qty 1000 --purchasable-qty 100 --ignore-fees
```

验证当天实盘分钟线时传入 A 股代码：

```powershell
python -m app.cli replay --symbol 600519 --target-qty 1000 --settled-sellable-qty 1000 --trade-qty 100
```

`--symbol` 会通过东财分钟趋势接口读取最近 1 个交易日数据。该入口只用于研究验证，真实使用前仍需核验数据授权、延迟和字段定义。

韩国股票的 `trigger --data-source yahoo` 会通过 Yahoo chart 接口读取最近 1 个交易日 1 分钟数据。该接口没有真实成交额字段，当前用 `close * volume` 近似成交额，因此只适合做提示原型，不适合直接做严格成交额回测。韩国分支默认使用 1 股交易单位、±30% 日涨跌幅、常规盘 09:00-15:30 的时间框架。

盘中提示 `SB` 或 `BS`：

```powershell
python -m app.cli prompt --symbol 603236 --bankroll 8000000 --scan
```

- `SB_OPEN`: 先卖出一笔可卖底仓，计划回落后买回。
- `BS_OPEN`: 先买入一笔，计划反弹后卖出原有可卖底仓。
- `HOLD`: 当前不提示开新 T。

新触发引擎统一输出：

- `NO_TRADE`
- `WATCH_SELL_TO_BUY`
- `TRIGGER_SELL_TO_BUY`
- `WATCH_BUY_TO_SELL`
- `TRIGGER_BUY_TO_SELL`
- `MANAGE_OPEN_PAIR`
- `FORCE_CLOSE_OR_RESTORE`

如果要让 `BS` 做现金约束校验，传入 `--cash`。

如果已有未闭合 Pair，传入状态让提示器优先处理闭合：

```powershell
python -m app.cli prompt --symbol 603236 --bankroll 8000000 --open-pair-side SB --open-pair-price 53.98 --open-pair-qty 15100
```

## 自动监控和手机提示

启动监控：

```powershell
python -m app.cli monitor --symbol 603236 --bankroll 8000000 --interval-seconds 60
```

默认只在控制台打印。手机推送可选：

```powershell
python -m app.cli monitor --symbol 603236 --bankroll 8000000 --notify-provider bark --notify-token YOUR_BARK_KEY
python -m app.cli monitor --symbol 603236 --bankroll 8000000 --notify-provider pushplus --notify-token YOUR_PUSHPLUS_TOKEN
python -m app.cli monitor --symbol 603236 --bankroll 8000000 --notify-provider webhook --notify-url https://example.com/hook
```

也可以用环境变量，避免 token 出现在命令历史里：

```powershell
$env:CBE_NOTIFY_PROVIDER="pushplus"
$env:CBE_NOTIFY_TOKEN="YOUR_TOKEN"
python -m app.cli monitor --symbol 603236 --bankroll 8000000 --interval-seconds 60
```

监控不会假设你执行了提示。如果你已经开了一腿，重新启动时传入 `--open-pair-side`、`--open-pair-price`、`--open-pair-qty`，它会优先推送闭合提示。

研究账本和 Pair 机制时，可以显式传入零费用配置：

```powershell
python -m app.cli replay --scenario mean_revert --target-qty 1000 --settled-sellable-qty 1000 --trade-qty 100 --min-commission 0 --buy-commission-rate 0 --sell-commission-rate 0 --stamp-tax-rate 0 --transfer-fee-rate 0 --buy-slippage-rate 0 --sell-slippage-rate 0
```

## 当前不能做

- 不连接券商，不自动下单。
- 不使用 Level-2、逐笔委托、主动买卖强度或真实排队位置。
- 不宣称策略盈利；当前只验证账本、费用、库存约束和无未来函数回放框架。

## 核心指标

CLI 会输出 `closed_t_net_pnl`、`excess_pnl_vs_hold`、`ending_quantity_delta`、`eod_inventory_restoration_rate`、`unclosed_pair_rate`、`total_fees`、`estimated_slippage`、`turnover`、`max_inventory_deviation`、`max_inventory_deviation_duration`、`missed_upside_tail`、`trade_count`、`net_pnl_per_10k_turnover` 等指标。
