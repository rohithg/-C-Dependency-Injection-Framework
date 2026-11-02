# Polymarket whale-copy walk-forward backtest

2026-05-01 -> 2026-11-02, $10,000 start, 53 screened wallets, follow top 5 re-picked monthly by trailing buy volume (size, not skill), 60 min latency, 0.01 slippage per side, Polymarket taker fees, 5% of equity per copied buy (max 25% per market), leader buys under $100 ignored, don't-chase 0.10.

| portfolio | total | CAGR | vol | Sharpe | max DD |
|---|---|---|---|---|---|
| Cash | +0.0% | +0.0% | 0.0% | n/a | 0.0% |
| Copy: walk-forward top-5 by trailing buy volume | -79.2% | -95.6% | 207.6% | -0.40 | -89.0% |
| Copy: today's leaderboard top-5 (biased) | -73.8% | -93.0% | 95.0% | -2.16 | -77.8% |
| Copy: every screened wallet (1.0%/trade) | -2.9% | -5.6% | 114.1% | 0.50 | -68.1% |
| VOO buy & hold | +5.6% | +11.4% | 12.1% | 0.95 | -4.5% |

Walk-forward copy: 323 buys, 122 sells, 147 resolutions (80 paid out), fees $347, realised PnL $-8,497.

Skipped leader trades: dust 29001, ends too soon 7677, no cash 6267, price out of range 1428, moved past max price 1005, not holding 673, market cap reached 541, no price 296, no end date 82, short-horizon market 9, unknown market 2

## Followed wallets by month

| month | wallets scored | copied buys | equity at month end | followed |
|---|---|---|---|---|
| 2026-05 | 13 | 66 | 2,761 | S-Works, Kickstand7, GCottrell93, juice-fruit, Cinibengales |
| 2026-06 | 17 | 75 | 2,032 | S-Works, wan123, mr.ozi, Kickstand7, juice-fruit |
| 2026-07 | 18 | 37 | 1,259 | S-Works, rabbitfoot1, ic4cream, wan123, mr.ozi |
| 2026-08 | 19 | 50 | 1,294 | S-Works, rabbitfoot1, ic4cream, wan123, TheReturnOfDarthMaul |
| 2026-09 | 22 | 44 | 2,411 | S-Works, rabbitfoot1, TheReturnOfDarthMaul, 3edmond.dantes, ic4cream |
| 2026-10 | 33 | 49 | 1,747 | 3edmond.dantes, S-Works, gmpm2, totoro3miyazaki, TheReturnOfDarthMaul |
| 2026-11 | 46 | 2 | 1,635 | gmpm2, 3edmond.dantes, totoro3miyazaki, joseph00677, S-Works |

## Who the rules would follow today

'trailing buy volume' is dollars spent buying, not a profit. 'their record' is what the wallet itself did.

| wallet | trailing buy volume | buys | their record (90d) |
|---|---|---|---|
| gmpm2 | 20,485,507 | 10748 | 51% win (497 decided), avg $40,971/market, 1/4 months up, mostly sports (99%) |
| 3edmond.dantes | 16,129,047 | 924 | 63% win (41 decided), avg $393,391/market, 2/4 months up, mostly sports (80%) |
| totoro3miyazaki | 15,937,827 | 899 | 52% win (48 decided), avg $325,262/market, 1/3 months up, mostly sports (96%) |
| joseph00677 | 15,812,709 | 526 | 45% win (22 decided), avg $687,509/market, 1/1 months up, mostly sports (69%) |
| S-Works | 10,433,053 | 1885 | 64% win (67 decided), avg $153,427/market, 2/3 months up, mostly sports (93%) |
