# Locked OOS datasets

This directory stores hash-locked real minute-bar CSVs used for out-of-sample evaluation.

Registered locked samples:

| Scenario | File | Source | Bars | Window | SHA-256 |
| --- | --- | --- | ---: | --- | --- |
| `oos_000001_20260612_yahoo` | `000001_20260612_yahoo_intraday.csv` | Yahoo public chart feed | 330 | `2026-06-12 09:30:00` to `2026-06-12 14:59:00` | `0470e0fce70e2a5dc13c71a3ce659a05ed7665f7452c994d37820a68791c0f3a` |
| `oos_300750_20260616_yahoo` | `300750_20260616_yahoo_intraday.csv` | Yahoo public chart feed | 330 | `2026-06-16 09:30:00` to `2026-06-16 14:59:00` | `bd377511fb4281a87947ade46f01276afa4e4c8e6b35a577d2a74e61417e64f2` |
| `oos_000858_20260617_yahoo` | `000858_20260617_yahoo_intraday.csv` | Yahoo public chart feed | 330 | `2026-06-17 09:30:00` to `2026-06-17 14:59:00` | `5b5a93def674502d3329b00300257e6a6f6f1d3bc17aeec8212d40e5e4c971e2` |
| `oos_300750_20260618_eastmoney` | `300750_20260618_eastmoney_intraday.csv` | Eastmoney public quote endpoint | 240 | `2026-06-18 09:30:00` to `2026-06-18 15:00:00` | `c31ec2034a3b3d80b3d0460cd6602b66413b33728795dbd6c3a2fa5e01d05f1b` |
| `oos_000001_20260618_eastmoney` | `000001_20260618_eastmoney_intraday.csv` | Eastmoney public quote endpoint | 241 | `2026-06-18 09:30:00` to `2026-06-18 15:00:00` | `f49358b32e3a8904ef5b2251d8a749ff79e9175bbc4d3767c5c643183751dc7d` |

Yahoo amount is approximated as `close * volume`. The existing `603236_20260618_eastmoney_intraday.csv` file is intentionally not registered as OOS because 603236 was used during earlier development/smoke checks. These samples improve OOS regression discipline, but five public-feed rows across three symbols and four dates are still not enough for profitability or production-validity claims.
