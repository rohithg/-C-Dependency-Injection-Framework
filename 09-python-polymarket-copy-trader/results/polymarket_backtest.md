# Polymarket copy-trading walk-forward backtest

2026-05-01 -> 2026-11-02, $10,000 start, 53 screened wallets, follow top 10 re-picked monthly on the trailing 90 days, 60 min latency, 0.01 slippage per side, Polymarket taker fees, 1% of equity per copied buy (max 5% per market).

| portfolio | total | CAGR | vol | Sharpe | max DD |
|---|---|---|---|---|---|
| Cash | +0.0% | +0.0% | 0.0% | nan | 0.0% |
| Copy: walk-forward top-10 by copyability | +40.0% | +95.0% | 125.1% | 1.14 | -55.7% |
| Copy: today's leaderboard top-10 (biased) | -83.6% | -97.2% | 96.8% | -3.20 | -84.4% |
| Copy: every screened wallet (0.2%/trade) | -12.2% | -22.7% | 74.9% | 0.02 | -42.6% |
| VOO buy & hold | +5.4% | +11.1% | 12.1% | 0.93 | -4.5% |

Walk-forward copy: 1548 buys, 306 sells, 533 resolutions (293 paid out), fees $1,705, realised PnL $1,759.

Skipped leader trades: dust 13939, ends too soon 5232, no cash 3921, market cap reached 3502, not holding 3477, price out of range 1094, moved past max price 960, no price 845, no end date 147

## Followed wallets by month

| month | wallets scored | copied buys | equity at month end | followed |
|---|---|---|---|---|
| 2026-05 | 10 | 122 | 14,414 | almost-never, surf, Kickstand7, 0xc8b9a30184244d427169cf62485dde6041b2b836 |
| 2026-06 | 12 | 860 | 12,439 | surf, almost-never, GCottrell93, ic4cream, 0xc8b9a30184244d427169cf62485dde6041b2b836 |
| 2026-07 | 15 | 145 | 9,148 | surf, almost-never, GCottrell93, TheReturnOfDarthMaul, 0xc8b9a30184244d427169cf62485dde6041b2b836 |
| 2026-08 | 17 | 76 | 10,277 | surf, 0xc8b9a30184244d427169cf62485dde6041b2b836, 0x006cc834Cc092684F1B56626E23BEdB3835c16ea-1729683673397, almost-never, TheReturnOfDarthMaul |
| 2026-09 | 20 | 110 | 12,306 | 0xc8b9a30184244d427169cf62485dde6041b2b836, mr.ozi, 0x006cc834Cc092684F1B56626E23BEdB3835c16ea-1729683673397, TheReturnOfDarthMaul, almost-never, Kickstand7 |
| 2026-10 | 24 | 224 | 13,050 | ArielFilipino, raybanman, mr.ozi, 0x006cc834Cc092684F1B56626E23BEdB3835c16ea-1729683673397, Bloodygoodrep1, TheReturnOfDarthMaul, ic4cream, 0xc8b9a30184244d427169cf62485dde6041b2b836, Kickstand7 |
| 2026-11 | 33 | 11 | 12,831 | fzol, 88888x88888, sumolive, izcikagamoji, MKSafe, raybanman, ArielFilipino, Bloodygoodrep1, mr.ozi, TheReturnOfDarthMaul |

## Who the rules would follow today

'copy return' is what copying the wallet under our rules would have made; 'their record' is what the wallet itself did.

| wallet | copy return | max dd | copied buys | trades seen | score | their record (90d) |
|---|---|---|---|---|---|---|
| fzol | 0.285 | -0.019 | 15 | 76 | 14.225 | 60% win (5 decided), avg $6,968/market, 1/1 months up, mostly politics (100%) |
| 88888x88888 | 0.189 | -0.021 | 18 | 265 | 9.100 | 100% win (1 decided), avg $72,667/market, 1/1 months up, mostly politics (100%) |
| sumolive | 0.138 | -0.030 | 15 | 531 | 4.546 | 100% win (2 decided), avg $93,200/market, 1/1 months up, mostly politics (100%) |
| izcikagamoji | 0.118 | -0.043 | 16 | 22 | 2.741 | 100% win (1 decided), avg $20,538/market, 1/1 months up, mostly politics (100%) |
| MKSafe | 0.060 | -0.025 | 90 | 827 | 2.409 | 80% win (30 decided), avg $3,209/market, 1/1 months up, mostly politics (62%) |
| raybanman | 0.137 | -0.088 | 63 | 3511 | 1.551 | 51% win (45 decided), avg $198,310/market, 1/3 months up, mostly sports (100%) |
| ArielFilipino | 0.483 | -0.316 | 461 | 1159 | 1.528 | 62% win (177 decided), avg $15,708/market, 2/2 months up, mostly sports (100%) |
| Bloodygoodrep1 | 0.129 | -0.091 | 69 | 4007 | 1.419 | 53% win (99 decided), avg $26,450/market, 2/3 months up, mostly sports (67%) |
| TheReturnOfDarthMaul | 0.249 | -0.218 | 245 | 6048 | 1.143 | 76% win (33 decided), avg $129,417/market, 4/4 months up, mostly economics (84%) |
| mr.ozi | 0.182 | -0.172 | 471 | 6912 | 1.059 | 79% win (124 decided), avg $21,192/market, 4/4 months up, mostly politics (55%) |
| 0xc8b9a30184244d427169cf62485dde6041b2b836 | 0.369 | -0.362 | 378 | 3087 | 1.019 | 65% win (161 decided), avg $3,692/market, 3/4 months up, mostly politics (97%) |
| Dragon-Evolution | 0.038 | -0.091 | 62 | 1204 | 0.422 | 77% win (22 decided), avg $59,756/market, 1/1 months up, mostly sports (100%) |
| dromedaryy | 0.012 | -0.428 | 277 | 5527 | 0.028 | 43% win (102 decided), avg $29,177/market, 1/3 months up, mostly politics (69%) |
| ic4cream | -0.081 | -0.408 | 1586 | 5788 | -0.199 | 57% win (1833 decided), avg $3,108/market, 3/4 months up, mostly sports (95%) |
| 0x20D6436849F930584892730C7F96eBB2Ac763856-1768642056357 | -0.062 | -0.275 | 141 | 2203 | -0.226 | 53% win (194 decided), avg $5,597/market, 2/3 months up, mostly sports (95%) |
