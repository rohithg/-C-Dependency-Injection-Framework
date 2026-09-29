# Architecture

```
sample_data/*.csv  →  scripts/run_quality_checks.py
                         ├─ great_expectations-style suites (YAML)
                         ├─ SQL monitors (portable)
                         └─ scorecard JSON/MD
dbt_tests/         →  drop into any dbt project as singular tests
```
