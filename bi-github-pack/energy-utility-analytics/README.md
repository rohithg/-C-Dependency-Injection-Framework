# Energy Utility Analytics

[![Domain](https://img.shields.io/badge/domain-energy%20%2F%20utility-1f7a4d)](docs/architecture.md)
[![Stack](https://img.shields.io/badge/stack-Power%20BI%20%7C%20DAX%20%7C%20SQL-0b1f17)](dax/energy_measures.dax)

**Rohith Gangapuram** · resume-aligned portfolio project

Interactive + dimensional model for **utility program performance**: kWh, peak demand, incentive spend, and compliance — the same shape of work delivered for energy-sector clients (Nexant 12-state programs / $500M+ program spend; Amplytico-style utility analytics).

## Live demo (local)

```bash
python3 -m http.server 8091 --directory dashboard
```

## What's inside

| Path | Contents |
|--|--|
| `sql/` | Star schema + monthly compliance mart |
| `seeds/` | Synthetic usage fact + utility/program dims |
| `dax/energy_measures.dax` | Certified measures (kWh, peak, compliance, YoY) |
| `glossary/` | Metric definitions with owners |
| `dashboard/` | Interactive Chart.js canvas for LinkedIn screenshots |
| `docs/architecture.md` | Resume → design mapping |

Demo data is **synthetic**. Method mirrors production utility BI.
