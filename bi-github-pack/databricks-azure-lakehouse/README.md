# Databricks Azure Lakehouse Pipeline

[![Stack](https://img.shields.io/badge/stack-ADLS%20%7C%20ADF%20%7C%20Databricks%20%7C%20Synapse-1a4a7a)](docs/architecture.md)
[![PySpark](https://img.shields.io/badge/PySpark-optimized-0a1628)](jobs/transform_usage.py)

**Rohith Gangapuram** · resume-aligned (Nexant multi-cloud + consulting Iceberg eval)

Portfolio implementation of **ADLS → ADF orchestration → Databricks PySpark → Synapse / SQL endpoint**, with an Iceberg evaluation notebook for a large-table workload.

## Resume mapping

| Resume bullet | Artifact |
|--|--|
| Multi-cloud pipeline ADLS → ADF → Databricks → Synapse | `pipelines/adf_pipeline.json`, `jobs/`, `sql/synapse/` |
| PySpark 4h → 90m on 50M+ rows/day | `jobs/transform_usage.py` (partitioning, AQE, broadcast) |
| Iceberg eval on ~500M-row workload | `notebooks/01_iceberg_evaluation.py` |

## Run locally (PySpark optional)

```bash
pip install -r requirements.txt
python jobs/transform_usage.py --input sample_data --output /tmp/lakehouse_out
python -m pytest tests/ -q
```

## Layout

```
pipelines/     ADF-style pipeline definition (JSON)
jobs/          PySpark bronze→silver→gold transforms
notebooks/     Iceberg evaluation
sql/synapse/   Gold table DDL + external tables
infra/         Unity Catalog / workspace notes
sample_data/   Synthetic bronze CSVs
tests/         Unit tests for transform helpers
```
