# Polymarket whale-copy walk-forward backtest

2026-05-01 -> 2026-11-02, $10,000 start, 53 screened wallets, follow up to 5 re-picked monthly from wallets whose own settled markets won at least 70% (15+ closed markets, positive settled profit), highest profit first, 60 min latency, 0.01 slippage per side, Polymarket taker fees, 5% of equity per copied buy (max 25% per market), leader buys under $100 ignored, don't-chase 0.10.

| portfolio | total | CAGR | vol | Sharpe | max DD |
|---|---|---|---|---|---|
| Cash | +0.0% | +0.0% | 0.0% | n/a | 0.0% |
| Copy: walk-forward top-5 by settled win rate >= 70% | +72.2% | +194.0% | 148.5% | 1.38 | -53.9% |
| Copy: today's leaderboard top-5 (biased) | -73.8% | -93.0% | 95.0% | -2.16 | -77.8% |
| Copy: every screened wallet (1.0%/trade) | -2.9% | -5.6% | 114.1% | 0.50 | -68.1% |
| VOO buy & hold | +5.6% | +11.4% | 12.1% | 0.95 | -4.5% |

Walk-forward copy: 392 buys, 250 sells, 103 resolutions (75 paid out), fees $1,285, realised PnL $7,773.

Skipped leader trades: dust 8886, no cash 1708, ends too soon 982, moved past max price 653, not holding 483, price out of range 416, no price 212, no end date 80, market cap reached 73, short-horizon market 9

## Followed wallets by month

| month | wallets scored | copied buys | equity at month end | followed |
|---|---|---|---|---|
| 2026-05 | 13 | 0 | 10,000 |  |
| 2026-06 | 17 | 91 | 8,226 | mr.ozi |
| 2026-07 | 18 | 63 | 9,382 | 0x006cc834Cc092684F1B56626E23BEdB3835c16ea-1729683673397, mr.ozi, 0xb4F978BE63cDF75554b0B46a4262a6dB597cc9A7-1779258330186 |
| 2026-08 | 19 | 57 | 13,346 | 0x006cc834Cc092684F1B56626E23BEdB3835c16ea-1729683673397, 0xc8b9a30184244d427169cf62485dde6041b2b836, almost-never |
| 2026-09 | 22 | 57 | 16,424 | 0x006cc834Cc092684F1B56626E23BEdB3835c16ea-1729683673397, 0xc8b9a30184244d427169cf62485dde6041b2b836, mr.ozi, almost-never |
| 2026-10 | 33 | 117 | 17,708 | TheReturnOfDarthMaul, 0x006cc834Cc092684F1B56626E23BEdB3835c16ea-1729683673397, mr.ozi, almost-never, PiEDawg |
| 2026-11 | 46 | 7 | 17,223 | TheReturnOfDarthMaul, Dragon-Evolution, mr.ozi, almost-never, MKSafe |

## Who the rules would follow today

'trailing buy volume' is dollars spent buying, not a profit. 'their record' is what the wallet itself did.

| wallet | their win rate | settled markets | settled pnl | trailing buy volume | buys | their record (90d) |
|---|---|---|---|---|---|---|
| TheReturnOfDarthMaul | 0.750 | 24 | 2,189,261 | 8,023,863 | 5832 | 76% win (33 decided), avg $129,417/market, 4/4 months up, mostly economics (84%) |
| Dragon-Evolution | 0.773 | 22 | 444,053 | 1,314,630 | 1204 | 77% win (22 decided), avg $59,756/market, 1/1 months up, mostly sports (100%) |
| mr.ozi | 0.776 | 107 | 342,840 | 3,178,814 | 4612 | 79% win (126 decided), avg $21,192/market, 4/4 months up, mostly politics (55%) |
| almost-never | 0.757 | 37 | 126,065 | 576,126 | 902 | 76% win (37 decided), avg $16,003/market, 3/3 months up, mostly politics (100%) |
| MKSafe | 0.750 | 24 | 189 | 86,631 | 461 | 80% win (30 decided), avg $3,209/market, 1/1 months up, mostly politics (62%) |
