# Healthcare Dimensional Model

[![Healthcare BI](https://img.shields.io/badge/Healthcare-dimensional%20model-0d3d3a)](#)
[![dbt tests](https://img.shields.io/badge/dbt-data%20quality-FF694B?logo=dbt&logoColor=white)](dbt/)
[![Synthetic data](https://img.shields.io/badge/data-SYNTHETIC%20ONLY-d64545)](SYNTHETIC_DATA_NOTICE.md)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**Rohith Gangapuram** · Analytics Engineering / Healthcare BI portfolio project

> **Synthetic demo only.** All patient, provider, facility, encounter, and claims data in this repository are fabricated. No real PHI, no real member IDs, and no production EHR extracts appear anywhere in this project.

A star-schema dimensional model and analytics-engineering toolkit inspired by EHR and claims work typical of integrated delivery systems (e.g. Kaiser Permanente–style clinical + administrative data). Built to demonstrate skills relevant to **BI Engineer** and **Analytics Engineer** roles in healthcare organizations such as Imagine Pediatrics, health plans, and pediatric/value-based care analytics teams.

---

## What this showcases

| Capability | Where to look |
|---|---|
| EHR-oriented star schema (encounters + claims) | [`sql/ddl/`](sql/ddl/), [`docs/architecture.md`](docs/architecture.md) |
| Staging → dimension / fact ETL | [`sql/etl/`](sql/etl/) |
| SCD Type 2 on `dim_patient` | [`sql/etl/02_load_dim_patient_scd2.sql`](sql/etl/02_load_dim_patient_scd2.sql) |
| dbt-style models + data quality tests | [`dbt/`](dbt/) |
| Referential integrity, date validity, ICD format | [`data-quality/`](data-quality/), [`dbt/models/marts/core/schema.yml`](dbt/models/marts/core/schema.yml) |
| Cross-system patient entity resolution | [`entity-resolution/`](entity-resolution/) |
| HIPAA-aware design (tokenization, least privilege) | [`docs/hipaa-design-notes.md`](docs/hipaa-design-notes.md) |

---

## Domain context

Healthcare analytics warehouses commonly combine:

- **Clinical events** from EHR / encounter systems (visits, diagnoses, providers, facilities)
- **Administrative events** from claims / revenue cycle (billed services, allowed amounts, claim status)
- **Master data** for patients, providers, and facilities that must remain historically accurate (SCD Type 2)

This project models that intersection with a clean star schema:

```
                    ┌──────────────┐
                    │  dim_date    │
                    └──────┬───────┘
                           │
┌──────────────┐    ┌──────┴───────┐    ┌────────────────┐
│ dim_patient  │────┤fct_encounters├────┤ dim_provider   │
└──────────────┘    └──────┬───────┘    └────────────────┘
                           │
                    ┌──────┴───────┐    ┌────────────────┐
                    │fct_claims    ├────┤ dim_facility   │
                    └──────┬───────┘    └────────────────┘
                           │
                    ┌──────┴───────┐
                    │dim_diagnosis │
                    └──────────────┘
```

See [`docs/architecture.md`](docs/architecture.md) for the full Mermaid diagram and grain definitions.

---

## Repository layout

```
healthcare-dimensional-model/
├── README.md
├── docs/
│   ├── architecture.md          # Star schema, grains, load order
│   └── hipaa-design-notes.md    # Educational privacy design notes
├── sql/
│   ├── ddl/                     # CREATE TABLE for dims + facts
│   └── etl/                     # Staging → dims/facts (incl. SCD2)
├── dbt/
│   ├── dbt_project.yml
│   ├── models/
│   │   ├── staging/
│   │   └── marts/core/          # + schema.yml with tests
│   └── tests/                   # Singular data quality tests
├── data-quality/                # DQ checklist + SQL assertions
├── entity-resolution/           # Matching approach + SQL
└── seeds/                       # SYNTHETIC CSV seed data
```

---

## Quick start (read-only exploration)

```bash
# Inspect DDL
ls sql/ddl/

# Review SCD Type 2 patient load
less sql/etl/02_load_dim_patient_scd2.sql

# Review dbt tests for referential integrity & ICD format
less dbt/models/marts/core/schema.yml

# Peek at synthetic seeds (clearly labeled SYNTHETIC)
head -5 seeds/synthetic_patients.csv
```

To run against a warehouse, load `sql/ddl/*.sql`, stage the CSVs under `seeds/`, then execute `sql/etl/` in numeric order. The dbt project is structured for Snowflake / BigQuery / Postgres-compatible dialects (ANSI-leaning SQL).

---

## Design principles

1. **Synthetic only** — every identifier is prefixed or namespaced as demo data (`SYN-`, `DEMO-`, hashed tokens).
2. **HIPAA-aware modeling** — separate tokenized keys from identity attributes; document least-privilege access patterns.
3. **Quality as code** — not-null, unique, relationships, accepted values, and custom SQL tests for clinical code formats.
4. **Historical truth** — SCD Type 2 for patient demographics that change over time (address, PCP attribution, coverage segment).
5. **Entity resolution first** — durable enterprise patient keys before facts are loaded.

---

## Skills demonstrated (role alignment)

Relevant to analytics / BI engineering roles in healthcare (pediatric VBC, health-system BI, payer analytics):

- Dimensional modeling for clinical + claims domains
- dbt-style transformation and testing practices
- Data quality frameworks for regulated data products
- Probabilistic / deterministic patient matching across source systems
- Privacy-preserving warehouse design patterns

---

## Disclaimer

This repository is an **educational portfolio artifact**. The HIPAA notes are **design considerations, not legal advice**. Do not load real PHI into this project. Do not treat the entity-resolution logic as production-ready matching for clinical decisions.

---

## Author

**Rohith Gangapuram**  
Healthcare BI / Analytics Engineering — dimensional models, data quality, entity resolution
