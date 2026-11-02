# Polymarket copy-trading walk-forward backtest

2026-05-01 -> 2026-11-02, $10,000 start, 53 screened wallets, follow top 10 re-picked monthly on the trailing 90 days, 60 min latency, 0.01 slippage per side, Polymarket taker fees, 1% of equity per copied buy (max 5% per market).

| portfolio | total | CAGR | vol | Sharpe | max DD |
|---|---|---|---|---|---|
| Cash | +0.0% | +0.0% | 0.0% | nan | 0.0% |
| Copy: walk-forward top-10 by copyability | +114.5% | +354.2% | 128.1% | 1.80 | -58.6% |
| Copy: today's leaderboard top-10 (biased) | -82.0% | -96.7% | 97.0% | -3.00 | -83.4% |
| Copy: every screened wallet (0.2%%/trade) | -14.3% | -26.4% | 74.2% | -0.05 | -45.6% |
| VOO buy & hold | +5.4% | +11.1% | 12.1% | 0.93 | -4.5% |

Walk-forward copy: 1930 buys, 311 sells, 744 resolutions (431 paid out), fees $2,070, realised PnL $7,986.

Skipped leader trades: dust 15181, ends too soon 6577, no cash 4869, market cap reached 3684, not holding 3485, price out of range 1080, no price 845, moved past max price 645, no end date 147

## Followed wallets by month

| month | wallets scored | copied buys | equity at month end | followed |
|---|---|---|---|---|
| 2026-05 | 10 | 78 | 12,971 | almost-never, surf, Kickstand7 |
| 2026-06 | 12 | 884 | 10,954 | surf, almost-never, GCottrell93, ic4cream, 0xc8b9a30184244d427169cf62485dde6041b2b836 |
| 2026-07 | 15 | 148 | 8,168 | surf, almost-never, GCottrell93, TheReturnOfDarthMaul, 0xc8b9a30184244d427169cf62485dde6041b2b836 |
| 2026-08 | 17 | 175 | 10,552 | surf, 0xc8b9a30184244d427169cf62485dde6041b2b836, 0x006cc834Cc092684F1B56626E23BEdB3835c16ea-1729683673397, almost-never, ic4cream, TheReturnOfDarthMaul |
| 2026-09 | 20 | 289 | 15,765 | 0xc8b9a30184244d427169cf62485dde6041b2b836, mr.ozi, 0x006cc834Cc092684F1B56626E23BEdB3835c16ea-1729683673397, ic4cream, TheReturnOfDarthMaul, almost-never, Kickstand7 |
| 2026-10 | 25 | 345 | 20,490 | ArielFilipino, raybanman, 0x006cc834Cc092684F1B56626E23BEdB3835c16ea-1729683673397, mr.ozi, ic4cream, Bloodygoodrep1, TheReturnOfDarthMaul, 0xc8b9a30184244d427169cf62485dde6041b2b836, Kickstand7 |
| 2026-11 | 35 | 11 | 20,209 | fzol, 88888x88888, sumolive, izcikagamoji, MKSafe, raybanman, ArielFilipino, Bloodygoodrep1, mr.ozi, TheReturnOfDarthMaul |

## Who the rules would follow today

| wallet | copy return | max dd | copied buys | trades seen | score |
|---|---|---|---|---|---|
| fzol | 0.285 | -0.019 | 15 | 76 | 14.225 |
| 88888x88888 | 0.189 | -0.021 | 18 | 265 | 9.100 |
| sumolive | 0.138 | -0.030 | 15 | 531 | 4.545 |
| izcikagamoji | 0.118 | -0.043 | 16 | 22 | 2.741 |
| MKSafe | 0.060 | -0.025 | 90 | 827 | 2.409 |
| raybanman | 0.137 | -0.088 | 63 | 3511 | 1.551 |
| ArielFilipino | 0.483 | -0.316 | 461 | 1159 | 1.528 |
| Bloodygoodrep1 | 0.129 | -0.091 | 69 | 4007 | 1.419 |
| mr.ozi | 0.202 | -0.171 | 486 | 6912 | 1.177 |
| TheReturnOfDarthMaul | 0.249 | -0.218 | 245 | 6048 | 1.143 |
| Dragon-Evolution | 0.071 | -0.091 | 77 | 1204 | 0.784 |
| 0xc8b9a30184244d427169cf62485dde6041b2b836 | 0.056 | -0.365 | 379 | 3087 | 0.153 |
| ic4cream | 0.043 | -0.341 | 1619 | 5788 | 0.126 |
| dromedaryy | -0.058 | -0.432 | 284 | 5527 | -0.134 |
| 0x20D6436849F930584892730C7F96eBB2Ac763856-1768642056357 | -0.044 | -0.267 | 173 | 2203 | -0.164 |
