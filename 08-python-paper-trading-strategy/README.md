# TVM: Trend-gated, Volatility-targeted Momentum

An automated paper-trading strategy designed to beat buy-and-hold VOO over a
full market cycle, with roughly half the drawdown. Python, daily bars, ETFs only,
runs against an Alpaca paper account.

![Equity curve](results/equity_curve.png)

## Why this can beat VOO

Holding VOO means holding 1.0x the S&P 500 at all times, including through
-34% (2020), -55% (2008) and -50% (2000-02) drawdowns. Three well-documented
effects let a rules-based strategy do better over time:

1. **Trend gate (time-series momentum).** When the index is below its 200-day
   moving average, forward returns are lower and volatility is much higher.
   Stepping aside into T-bills during those regimes skips most of the big
   crashes at the cost of some whipsaw. This is where the drawdown reduction
   comes from.
2. **Volatility targeting.** Sizing exposure to a fixed volatility budget
   (20%/yr) means *more* than 1x in calm uptrends and *less* than 1x in
   turbulent ones. Because volatility clusters, that is a better risk/return
   tradeoff than constant 1x, and it's what allows the strategy to compound
   faster than the index without exceeding its volatility much. Exposure above
   1x is implemented with the 2x ETFs SSO / QLD, so no margin is needed.
   A -34%-style drawdown on the index becomes roughly -21% here.
3. **Relative momentum between SPY and QQQ.** Whichever of the two has the
   better trailing 6-month return is held, re-evaluated at most monthly.
   This is the least robust of the three (it rides a 15-year tech tailwind),
   so the README also reports a SPY-only variant.

In short: own the market when the market is rewarding ownership, own more of
it when it is calm, and own none of it when it is in a downtrend.

## The rules

Every trading day, using closes up to and including today:

| Step | Rule | Default |
|---|---|---|
| Regime | risk-on iff `SPY close > SMA(SPY, 200)`; otherwise 100% in `BIL` (1-3 month T-bills) | `sma_window=200` |
| Asset | hold whichever of `SPY` / `QQQ` has the higher 126-day return; re-pick only after holding the current one at least 21 trading days | `momentum_window=126`, `min_hold_days=21` |
| Size | `exposure = clip(0.20 / realized_vol, 0, 2.0)` where `realized_vol` = max of the two assets' 20-day daily-return std, annualised | `target_vol=0.20`, `vol_window=20`, `max_leverage=2.0` |
| Implement | `exposure <= 1`: `exposure` in the 1x ETF, rest in `BIL`. `exposure > 1`: `(exposure-1)` in the 2x ETF (`SSO`/`QLD`), `(2-exposure)` in the 1x ETF | |
| Rebalance | only trade when the regime flips, the asset changes, or target exposure moves more than 0.10 from what is held | `rebalance_band=0.10` |

All parameters live in [`tvm/config.py`](tvm/config.py) and can be overridden
with a JSON file ([`config.example.json`](config.example.json)).

## Backtest results

Benchmark is VOO; SPY (same index) is spliced in before VOO's Sept 2010
inception. Costs: 2 bps per unit of fund value traded. Exposure above 1x uses
actual SSO/QLD returns from their 2006 inception and a synthetic
`2*r - (T-bill + 0.5% + 0.9% expense)` before that. Signal on close *t*,
position earns *t -> t+1*. Sharpe is excess over T-bills.

```
=== Full history (1994->)  (32.8y, 1288 rebalances) ===
  TVM strategy                 CAGR  13.45%  Vol 17.38%  Sharpe  0.67  MaxDD -22.81%  Calmar  0.59  x 62.66
  VOO buy & hold               CAGR  10.82%  Vol 18.73%  Sharpe  0.51  MaxDD -55.19%  Calmar  0.20  x 29.08
  rolling 3y win rate vs VOO: 69%   5y: 79%   10y: 96%

=== Out-of-sample: dot-com + GFC (1999-04 -> 2010-09)  (11.4y, 370 rebalances) ===
  TVM strategy                 CAGR   4.74%  Vol 14.45%  Sharpe  0.21  MaxDD -22.81%  Calmar  0.21  x  1.70
  VOO buy & hold               CAGR   0.36%  Vol 21.99%  Sharpe  0.01  MaxDD -55.19%  Calmar  0.01  x  1.04

=== VOO era (2010-09 ->)  (16.1y, 723 rebalances) ===
  TVM strategy                 CAGR  16.90%  Vol 18.48%  Sharpe  0.85  MaxDD -20.62%  Calmar  0.82  x 12.39
  VOO buy & hold               CAGR  14.74%  Vol 16.93%  Sharpe  0.81  MaxDD -33.99%  Calmar  0.43  x  9.17
  rolling 3y win rate vs VOO: 73%   5y: 74%   10y: 100%

=== Real 2x ETFs available (2007 ->)  (19.8y, 841 rebalances) ===
  TVM strategy                 CAGR  14.60%  Vol 17.93%  Sharpe  0.76  MaxDD -20.62%  Calmar  0.71  x 14.84
  VOO buy & hold               CAGR  10.86%  Vol 19.55%  Sharpe  0.55  MaxDD -55.19%  Calmar  0.20  x  7.70
```

![Yearly returns](results/yearly_returns.png)

What to expect year to year: TVM beats the index in only ~40-50% of calendar
years. It loses in whipsaw years (2011, 2015-16), in sharp V-shaped recoveries
where the trend gate re-enters late (2019, 2021, 2025-26), and it wins big in
bear markets (2001-02, 2008, 2022) and in calm, trending bull years where it
runs 1.5-2x (2013, 2017). The edge shows up over 5-10 year windows, not
quarters. If you need to beat VOO *every* year, no systematic strategy will do
that.

### Sensitivity (CAGR / MaxDD / Sharpe)

| Variant | 1994-> | 1999-04 -> 2010-09 (OOS) | 2010-09 -> (VOO era) |
|---|---|---|---|
| **VOO buy & hold** | 10.8% / -55.2% / 0.51 |  0.4% / -55.2% / 0.01 | 14.7% / -34.0% / 0.81 |
| **TVM default** | 13.4% / -22.8% / 0.67 |  4.7% / -22.8% / 0.21 | 16.9% / -20.6% / 0.85 |
| No leverage (`max_leverage=1`) | 11.5% / -22.8% / 0.71 |  5.3% / -22.8% / 0.27 | 13.6% / -16.0% / 0.90 |
| SPY only (no QQQ momentum) | 10.7% / -32.1% / 0.53 |  0.6% / -32.1% / -0.05 | 14.4% / -22.8% / 0.74 |
| `target_vol=0.15` | 11.4% / -17.0% / 0.68 |  4.5% / -17.0% / 0.21 | 13.9% / -15.4% / 0.87 |
| `target_vol=0.25` | 15.2% / -28.8% / 0.67 |  5.3% / -28.8% / 0.23 | 19.7% / -22.9% / 0.87 |
| `sma_window=150` | 11.9% / -28.6% / 0.60 |  3.9% / -27.7% / 0.15 | 15.0% / -28.6% / 0.77 |
| `sma_window=250` | 13.2% / -23.1% / 0.65 |  6.4% / -22.3% / 0.32 | 15.3% / -22.3% / 0.77 |
| `momentum_window=63` | 13.3% / -21.9% / 0.67 |  4.9% / -21.9% / 0.22 | 16.4% / -18.9% / 0.84 |
| `momentum_window=252` | 11.7% / -28.4% / 0.58 |  1.4% / -28.4% / -0.02 | 15.9% / -24.0% / 0.79 |
| `vol_window=60` | 12.5% / -23.0% / 0.63 |  4.0% / -22.5% / 0.16 | 15.6% / -23.0% / 0.81 |
| `min_hold_days=0` | 13.0% / -31.9% / 0.65 |  3.3% / -31.9% / 0.11 | 17.2% / -21.7% / 0.86 |
| `rebalance_band=0.20` | 13.7% / -24.2% / 0.68 |  4.9% / -24.2% / 0.22 | 17.1% / -22.0% / 0.86 |
| `cost_bps=10` (5x default costs) | 11.2% / -28.5% / 0.56 |  2.7% / -28.5% / 0.07 | 14.5% / -23.3% / 0.74 |

Takeaways:

- Every variant cuts max drawdown to about half of VOO's or better. On CAGR,
  every variant except SPY-only beats VOO over the full 33 years and over the
  out-of-sample window; in the 2010-2026 bull run the lower-risk settings (no
  leverage, 15% vol target, 5x costs) trail VOO by ~1%/yr while still halving
  drawdown. The structure is what matters; exact parameters are second order.
- `target_vol` is the risk dial. 15% gives VOO-like returns at half the
  drawdown; 25% gives ~5%/yr more than VOO at ~-29% max drawdown.
- The QQQ sleeve adds ~2.5%/yr over the long run but is the component most
  exposed to regime change (it rides a tech tailwind). The no-leverage variant
  beats VOO without any 2x ETF and is the most conservative choice.
- Turnover is ~25x of account value per year (regime flips and asset switches
  dominate, not the band), so costs matter: at 10 bps a round trip the edge
  shrinks noticeably. Alpaca is commission-free and SPY/QQQ/BIL spreads are
  ~1 bp, SSO/QLD ~2-3 bp, so 2 bps is a realistic all-in number.

## Running it

```bash
cd 08-python-paper-trading-strategy
pip install -r requirements.txt

# Backtest (downloads ~30y of daily data via yfinance, caches to data_cache/)
python run_backtest.py
python run_backtest.py --start 2015-01-01 --end 2024-12-31 --no-plot
python run_backtest.py --config config.example.json

# Tests (synthetic data, no network)
python -m pytest -q tests

# Paper trading against Alpaca (https://alpaca.markets, free paper account)
export APCA_API_KEY_ID=...  APCA_API_SECRET_KEY=...
python paper_trade.py --dry-run     # print signal, target weights and orders; submit nothing
python paper_trade.py               # submit market orders (paper endpoint only; live is refused)
python paper_trade.py --fake --dry-run   # no credentials: simulate against a fake $100k account
```

`paper_trade.py` is idempotent: run it once per trading day, ideally in the
last ~10 minutes of the session. When the market is open it pulls live IEX
prices from Alpaca and appends them as today's bar so the 200-day check sees
the near-final close; after hours it uses the last daily close and orders fill
at the next open. The (asset, exposure) state is rebuilt from live positions
every run, so a failed order or manual intervention self-heals on the next run.
Only the hold-period counter is persisted in `state/tvm_state.json`; every run
appends a JSON record to `state/trade_log.jsonl`.

### Scheduling

[`.github/workflows/paper-trade.yml`](../.github/workflows/paper-trade.yml)
runs the trader at 15:50 ET each weekday. To enable it, add repository secrets
`ALPACA_PAPER_KEY_ID` / `ALPACA_PAPER_SECRET_KEY` and set the repository
variable `TVM_PAPER_TRADING_ENABLED=true`. Any cron (or a Lambda / Cloud Run
job) that runs `python paper_trade.py` once a day works equally well.

## Project layout

```
tvm/config.py     parameters (dataclass, JSON-overridable)
tvm/strategy.py   pure signal logic: compute_signals / step / target_weights
tvm/backtest.py   execution + cost model, metrics, yearly tables
tvm/data.py       yfinance loader with CSV cache
tvm/broker.py     Broker protocol, AlpacaBroker (REST), FakeBroker
tvm/trader.py     one daily rebalance: reconstruct state -> signal -> orders
run_backtest.py   report + charts in results/
paper_trade.py    CLI for the daily run
tests/            21 unit + integration tests on synthetic data
```

The same `strategy.py` code produces both the backtest and the live orders, so
there is no backtest/live divergence to debug.

## Caveats, honestly

- **Backtests overstate.** Parameters were chosen on 2010-2026 data, then
  checked on 1999-2010; that is weaker than true out-of-sample live results.
  Expect realized performance below the tables above.
- **Trend following has a known failure mode:** choppy, range-bound markets
  (2011, 2015-16) produce repeated small losses from whipsaw, amplified by
  leverage. The 21-day min-hold and the 200-day window reduce but do not remove
  this.
- **Leveraged ETFs** reset daily and underperform 2x the index over long
  sideways stretches (volatility decay). The backtest uses real SSO/QLD prices
  from 2006 so this is priced in, but it is a real cost.
- **Taxes** are ignored. ~25x annual turnover means almost all gains are
  short-term; in a taxable account this strategy's after-tax edge over VOO
  shrinks substantially. It suits tax-advantaged accounts or, as here, paper
  trading.
- **Gap risk.** Exiting at the close after a cross means a 2x position can sit
  through an overnight gap. The vol target shrinks exposure quickly when
  volatility spikes, but not before the first bad day.
- **Data.** yfinance is free and occasionally flaky; the loader caches to
  `data_cache/` and refreshes every 12 hours. For a production system use the
  broker's own bars.

This is an educational paper-trading project, not investment advice.
