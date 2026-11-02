# Kronos-small walk-forward results

Forecast days 2022-01-03 -> 2026-10-30; context 400 bars, horizon 5 days, 8 sampled paths/day. Costs 2 bps per dollar traded.

## Information content

| symbol | window | days | IC exp_ret vs fwd | IC z_ret vs fwd | IC 1d | sign hit-rate | mean exp_ret | mean realised | days exp_ret>0 |
|---|---|---|---|---|---|---|---|---|---|
| QQQ | <= 2024-06 (in training data) | 625 | -0.009 | 0.039 | 0.063 | 0.459 | -0.027 | 0.003 | 0.312 |
| QQQ | 2024-07 -> (out of sample) | 581 | 0.217 | 0.040 | 0.076 | 0.437 | -0.050 | 0.004 | 0.084 |
| SPY | <= 2024-06 (in training data) | 625 | 0.067 | 0.096 | 0.069 | 0.467 | -0.018 | 0.002 | 0.371 |
| SPY | 2024-07 -> (out of sample) | 581 | 0.187 | 0.084 | 0.014 | 0.453 | -0.031 | 0.003 | 0.129 |

## Strategies

**Whole forecast window**

| strategy | CAGR | Vol | Sharpe | MaxDD | turnover/yr |
|---|---|---|---|---|---|
| VOO buy & hold | 11.7% | 17.0% | 0.50 | -24.5% | - |
| TVM adaptive ensemble | 9.7% | 16.4% | 0.41 | -17.3% | - |
| Kronos direction (raw sign) | 13.6% | 15.3% | 0.65 | -14.9% | 36.8 |
| Kronos calibrated (z>0) | 15.0% | 16.6% | 0.69 | -18.8% | 54.7 |
| Kronos calibrated (z>0.5) | 13.1% | 15.0% | 0.63 | -18.8% | 47.2 |
| Kronos relative (SPY vs QQQ) | 9.7% | 19.9% | 0.36 | -26.5% | 43.5 |
| Kronos confidence (<=2x) | 14.2% | 23.7% | 0.51 | -33.5% | 57.0 |
| TVM ensemble + Kronos veto | 8.3% | 7.5% | 0.57 | -8.8% | 17.3 |

**Overlaps Kronos training data (-> 2024-06)**

| strategy | CAGR | Vol | Sharpe | MaxDD | turnover/yr |
|---|---|---|---|---|---|
| VOO buy & hold | 7.3% | 18.1% | 0.27 | -24.5% | - |
| TVM adaptive ensemble | 13.1% | 14.3% | 0.66 | -15.2% | - |
| Kronos direction (raw sign) | 14.3% | 17.8% | 0.62 | -13.7% | 36.8 |
| Kronos calibrated (z>0) | 15.6% | 16.0% | 0.74 | -17.5% | 54.7 |
| Kronos calibrated (z>0.5) | 12.8% | 13.4% | 0.68 | -11.9% | 47.2 |
| Kronos relative (SPY vs QQQ) | 4.3% | 21.5% | 0.13 | -26.5% | 43.5 |
| Kronos confidence (<=2x) | 17.8% | 19.6% | 0.74 | -17.0% | 57.0 |
| TVM ensemble + Kronos veto | 9.5% | 8.4% | 0.66 | -6.4% | 17.3 |

**Out of sample for Kronos (2024-07 ->)**

| strategy | CAGR | Vol | Sharpe | MaxDD | turnover/yr |
|---|---|---|---|---|---|
| VOO buy & hold | 16.5% | 15.8% | 0.79 | -18.7% | - |
| TVM adaptive ensemble | 6.2% | 18.4% | 0.20 | -17.3% | - |
| Kronos direction (raw sign) | 12.9% | 12.2% | 0.72 | -14.9% | 36.8 |
| Kronos calibrated (z>0) | 14.4% | 17.2% | 0.63 | -18.8% | 54.7 |
| Kronos calibrated (z>0.5) | 13.3% | 16.5% | 0.59 | -18.8% | 47.2 |
| Kronos relative (SPY vs QQQ) | 15.6% | 18.0% | 0.67 | -18.4% | 43.5 |
| Kronos confidence (<=2x) | 10.5% | 27.5% | 0.35 | -33.5% | 57.0 |
| TVM ensemble + Kronos veto | 7.0% | 6.4% | 0.46 | -8.8% | 17.3 |
