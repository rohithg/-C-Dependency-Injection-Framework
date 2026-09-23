# Overview

{% docs __overview__ %}
# SaaS Analytics Engineering

dbt project demonstrating **metrics-as-code**, reusable dimensional marts, and
CI-friendly analytics engineering for B2B SaaS / consulting-style product analytics.

**Author:** Rohith Gangapuram

## Layered architecture

| Layer | Purpose |
|-------|---------|
| **Seeds / Sources** | Synthetic SaaS raw data (accounts, plans, subscriptions, usage events) |
| **Staging** | Light renaming, typing, and standard tests |
| **Intermediate** | Business logic building blocks (subscription spine, activation, monthly MRR) |
| **Marts** | Conformed dims/facts for BI (`dim_*`, `fct_*`) |
| **Metrics** | Versioned ARR, churn, NRR, activation rate definitions |

## Core SaaS metrics (contracts)

- **ARR** — Active MRR × 12 (non-internal)
- **Logo churn** — Logos lost / logos at prior month end
- **NRR** — Ending MRR of prior cohort / beginning MRR
- **Activation rate** — Accounts meeting product-event heuristic / started accounts

See `models/metrics/` for SQL source of truth and `models/semantic_models/` for
MetricFlow-oriented contracts.
{% enddocs %}

{% docs arr_definition %}
Annual Recurring Revenue. Sum of monthly recurring revenue for currently active,
non-internal paying subscriptions, annualized by multiplying by 12.
{% enddocs %}

{% docs activation_definition %}
An account is activated when it records at least `activation_event_threshold`
product events (excluding signup) within `activation_window_days` of account creation.
{% enddocs %}
