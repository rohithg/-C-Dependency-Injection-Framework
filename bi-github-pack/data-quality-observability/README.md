# Data Quality Observability

[![Stack](https://img.shields.io/badge/stack-Great%20Expectations%20%7C%20dbt%20tests%20%7C%20SQL-6b2d5c)](docs/architecture.md)

**Rohith Gangapuram** · resume-aligned (ELT modernization · ~80% fewer DQ defects)

Framework that turns dirty source extracts into scored quality reports: nulls, duplicates, referential integrity, amount bounds, status domains, and ship-before-order anomalies.

## Run

```bash
pip install -r requirements.txt
python scripts/run_quality_checks.py
# → reports/quality_scorecard.json + reports/quality_scorecard.md
```

## Resume mapping

| Resume signal | Artifact |
|--|--|
| ELT modernization cutting DQ defects ~80% | Expectation suites + scorecard trend |
| dbt tested pipelines (30% → &lt;2% failure) | `dbt_tests/` singular tests |
| Governance / audit readiness | monitors + docs |
