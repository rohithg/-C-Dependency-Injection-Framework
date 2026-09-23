# SaaS Analytics Engineering (dbt)

**Rohith Gangapuram** · Analytics Engineer II portfolio project

Metrics-as-code, reusable marts, and CI-friendly dbt for B2B SaaS product analytics—the patterns consulting clients and growth-stage SaaS teams expect in production.

---

## Why this project

Hiring managers for Analytics Engineer II roles look for more than “I can write SQL.” This repo shows:

| Expectation | How this repo demonstrates it |
|-------------|-------------------------------|
| Clear layered modeling | `staging` → `intermediate` → `marts` → `metrics` |
| Metrics as versioned contracts | ARR, logo churn, NRR, activation rate as tested SQL + semantic YAML |
| Warehouse-ready SQL | Snowflake-compatible (timestamps, `dateadd`, `generator`, `qualify`) |
| Test discipline | Generic schema tests + singular metric invariant tests |
| BI-ready marts | `dim_accounts`, `dim_plans`, `fct_subscriptions`, `fct_usage_events` |
| CI mindset | GitHub Actions: `dbt parse`, `docs generate`, notes for `dbt build` |
| Reusable macros | `cents_to_dollars`, `fiscal_year`, `safe_divide` |

---

## Architecture

```text
seeds/                    Synthetic SaaS raw data
models/
  staging/                Thin, typed, tested stubs
  intermediate/           Subscription spine, activation, monthly MRR
  marts/
    core/                 dim_accounts, dim_plans
    finance/              fct_subscriptions
    product/              fct_usage_events
  metrics/                ARR, churn, NRR, activation (source of truth)
  semantic_models/        MetricFlow-oriented contracts
macros/                   Shared Jinja helpers
tests/                    Singular metric invariant tests
analyses/                 Example business questions
.github/workflows/        dbt CI
```

**Design rules used here**

1. **Staging does not invent business logic** — rename, cast, flag.
2. **Intermediate owns reusable logic** — activation windows, MRR spines.
3. **Marts are conformed for consumers** — dims/facts, surrogate keys, tenure.
4. **Metrics are code** — definitions live in SQL models with invariant tests; semantic YAML documents the same contracts for a semantic layer.

---

## Core metric definitions

| Metric | Definition (contract) | Model |
|--------|----------------------|-------|
| **ARR** | Σ (active MRR × 12) for non-internal paying accounts at month end | `metric_arr_monthly` |
| **Logo churn** | Logos with prior-month MRR > 0 and current MRR = 0 ÷ prior logos | `metric_logo_churn_monthly` |
| **NRR** | Ending MRR of prior-month cohort ÷ beginning MRR | `metric_nrr_monthly` |
| **Activation rate** | Accounts with ≥ N product events in W days of signup ÷ started accounts | `metric_activation_rate` |

Activation thresholds are project vars (`activation_event_threshold`, `activation_window_days`) so product can change the heuristic without rewriting marts.

Singular tests enforce invariants such as:

- `arr_usd = mrr_usd * 12`
- `0 ≤ logo_churn_rate ≤ 1`
- `0 ≤ nrr` (and sanity upper bound)
- `0 ≤ activation_rate ≤ 1`
- Latest metric ARR reconciles to active subscription fact ARR

---

## Quick start

### Prerequisites

- Python 3.10+
- dbt Core 1.7+ with `dbt-snowflake` (or `dbt-duckdb` for local offline runs)

```bash
pip install "dbt-core>=1.7,<1.9" "dbt-snowflake>=1.7,<1.9" "dbt-duckdb>=1.7,<1.9"
cp profiles.yml.example ~/.dbt/profiles.yml   # or set DBT_PROFILES_DIR
```

### Run locally (DuckDB — no Snowflake needed)

```bash
# profiles.yml pointing at target: local (see profiles.yml.example)
dbt deps
dbt seed --target local
dbt run --target local
dbt test --target local
dbt docs generate --target local
dbt docs serve
```

### Run on Snowflake

```bash
export SNOWFLAKE_ACCOUNT=... SNOWFLAKE_USER=... # see profiles.yml.example
dbt deps
dbt seed --target dev
dbt build --target dev          # run + test in dependency order
```

### Useful selectors

```bash
dbt build --select path:models/marts
dbt build --select tag:metrics
dbt build --select metric_arr_monthly+           # model + downstream tests
dbt test --select test_type:singular
```

---

## Project map (selected)

### Marts

| Model | Grain | Use |
|-------|-------|-----|
| `dim_accounts` | 1 row / account | Segment, region, activation, current ARR |
| `dim_plans` | 1 row / plan | Tier, list price, seat limits |
| `fct_subscriptions` | 1 row / subscription | MRR/ARR, churn, tenure, fiscal start |
| `fct_usage_events` | 1 row / event | Funnel & engagement analysis |

### Analyses (business questions as SQL)

- `analyses/arr_by_segment_region.sql` — ARR mix for RevOps
- `analyses/nrr_and_churn_trend.sql` — retention health for exec reporting
- `analyses/activation_vs_paid_conversion.sql` — product ↔ revenue
- `analyses/churn_reason_breakdown.sql` — CS prioritization

Run with: `dbt compile --select analysis_name` then execute compiled SQL, or use `dbt show`.

---

## CI / CD

Workflow: [`.github/workflows/dbt-ci.yml`](.github/workflows/dbt-ci.yml)

| Job | What it does |
|-----|----------------|
| **dbt parse + docs generate** | Always runs on PRs via DuckDB profile — catches Jinja/ref errors and produces docs artifacts |
| **dbt build (Snowflake)** | Commented template — enable when `SNOWFLAKE_*` secrets exist |
| **SQLFluff** | Soft lint with Snowflake dialect |

**Operator notes for `dbt build` in CI**

1. Scope a CI role to a dedicated `ANALYTICS_CI` database.
2. Prefer `dbt build` over `dbt run` so tests gate merges.
3. Use slim CI (`state:modified+`) once a production manifest is stored as an artifact.
4. Isolate PR schemas (`DBT_CI_PR_<number>`) to avoid collisions.

---

## Macros

| Macro | Purpose |
|-------|---------|
| `cents_to_dollars(col)` | Integer cents → USD decimal |
| `fiscal_year(ts)` | FY integer from configurable start month |
| `safe_divide(n, d)` | Null-safe division (avoids DIV0) |

---

## Synthetic data

Seeds under `seeds/` model a small B2B SaaS tenant base: plan catalog, subscription lifecycle (active / churned / upgraded / trialing), and product events for activation. Internal demo account `acc_015` is excluded from revenue metrics via `is_internal`.

---

## What “good” looks like for AE II

This project is intentionally opinionated about practices that show up in strong Analytics Engineer II interviews and client delivery:

- **Metric ownership** — one definition, tested, discoverable in docs
- **Consumer-oriented marts** — dims/facts over wide “everything” tables
- **Change safety** — parse/docs in CI; build+test when a warehouse is available
- **Fiscal / money hygiene** — cents at the edge, dollars in marts, safe math macros
- **Product + finance together** — activation next to NRR, not in a separate silo

---

## Author

**Rohith Gangapuram**  
Analytics Engineer · dbt · Snowflake · SaaS metrics

---

## License

MIT — see [LICENSE](LICENSE). Synthetic data only; no customer information.
