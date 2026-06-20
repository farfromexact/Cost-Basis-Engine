# Sources

Access date: 2026-06-19.

Network-backed official-source verification is partial in this workspace run. V1 therefore uses explicit assumptions and records them as implementation defaults, not permanent truth.

## Checked Sources

- Shanghai Stock Exchange official rule portal: https://www.sse.com.cn/lawandrules/sselawsrules/trade/universal/
  - Key conclusion: use this portal to verify SSE trading-rule text and effective dates before replaying SSE securities.
- Shenzhen Stock Exchange official rule portal: https://www.szse.cn/lawrules/rule/trade/index.html
  - Key conclusion: SZSE exposes trading rules under `法律规则 / 本所业务规则 / 交易类`; use this portal to verify SZSE trading-rule text and effective dates before replaying SZSE securities.
- Hong Zhu, Zhi-Qiang Jiang, Sai-Ping Li, Wei-Xing Zhou, "Profitability of simple technical trading rules of Chinese stock exchange indexes", arXiv:1504.04254.
  - Key conclusion: simple technical rules can appear profitable before transaction costs; once transaction costs are included, trading profits may be eliminated.
- Eastmoney trends endpoint used by V1 adapter: `https://push2his.eastmoney.com/api/qt/stock/trends2/get`
  - Key conclusion: V1 can request latest 1-day minute trend rows for research smoke tests. Data license, delay, and production suitability remain pending verification.
- Yahoo Finance chart endpoint used by Korea adapter: `https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range=1d&interval=1m`
  - Key conclusion: V1 can request latest 1-day minute rows for Yahoo symbols such as `005930.KS`. The response has OHLCV, but no turnover amount; V1 approximates amount as `close * volume`.
- Korea Exchange, "Guide to Trading in the Korean Stock Market": https://global.krx.co.kr/contents/GLB/01/0109/0109000000/guide_to_trading_in_the_korean_stock_market.pdf
  - Key conclusion: regular session is 09:00-15:30, trading unit for stocks/ETFs/ETNs is 1 share, and daily price limit is ±30% of base prices.

## Assumptions To Verify

- A-share ordinary stock sellability: same-day bought shares are locked and cannot be sold the same day; buy-then-sell must sell pre-existing settled inventory.
- Default tick size: 0.01 RMB.
- Default board lot size: 100 shares.
- Korean stock default lot size: 1 share.
- Korean stock default daily price limit: ±30%.
- Default fee model values in `core/fee_model.py` are placeholders and must be replaced with the user's broker-specific commission and verified market rules before real use.

## Pending Official Checks

- Exact exchange trading-rule clauses for the target board/security type and replay date.
- Ministry/Tax authority stamp-tax rules effective on the replay date.
- ChinaClear transfer-fee rules effective on the replay date.
- Data vendor documentation and license for any real minute-bar source.
- Korean broker-specific tax, commission, FX, and settlement constraints for the user's account.
