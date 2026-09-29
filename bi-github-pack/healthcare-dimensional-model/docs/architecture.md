# Architecture — Healthcare Star Schema

**Synthetic demo model only.** No real PHI.

This document describes the dimensional model used to support encounter and claims analytics for a fictional integrated delivery network (IDN). The design mirrors patterns used in EHR + claims warehouses: conformed dimensions, additive facts, and SCD Type 2 history on mutable patient attributes.

---

## Star schema (Mermaid)

```mermaid
erDiagram
    DIM_PATIENT ||--o{ FCT_ENCOUNTERS : "patient_sk"
    DIM_PROVIDER ||--o{ FCT_ENCOUNTERS : "provider_sk"
    DIM_FACILITY ||--o{ FCT_ENCOUNTERS : "facility_sk"
    DIM_DIAGNOSIS ||--o{ FCT_ENCOUNTERS : "primary_dx_sk"
    DIM_DATE ||--o{ FCT_ENCOUNTERS : "encounter_date_sk"

    DIM_PATIENT ||--o{ FCT_CLAIMS : "patient_sk"
    DIM_PROVIDER ||--o{ FCT_CLAIMS : "billing_provider_sk"
    DIM_FACILITY ||--o{ FCT_CLAIMS : "facility_sk"
    DIM_DIAGNOSIS ||--o{ FCT_CLAIMS : "primary_dx_sk"
    DIM_DATE ||--o{ FCT_CLAIMS : "service_date_sk"
    DIM_DATE ||--o{ FCT_CLAIMS : "paid_date_sk"

    DIM_PATIENT {
        bigint patient_sk PK
        string patient_nk
        string enterprise_patient_id
        string first_name_token
        date birth_date
        string sex_cd
        string zip3
        boolean is_current
        date effective_start_dt
        date effective_end_dt
    }

    DIM_PROVIDER {
        bigint provider_sk PK
        string provider_nk
        string npi_synthetic
        string specialty_cd
        string provider_name
    }

    DIM_FACILITY {
        bigint facility_sk PK
        string facility_nk
        string facility_name
        string facility_type
        string region_cd
    }

    DIM_DIAGNOSIS {
        bigint diagnosis_sk PK
        string icd10_cd
        string icd10_desc
        string chapter_cd
        string clinical_group
    }

    DIM_DATE {
        int date_sk PK
        date full_date
        int year_num
        int month_num
        string month_name
        int quarter_num
        boolean is_weekend
    }

    FCT_ENCOUNTERS {
        bigint encounter_sk PK
        string encounter_nk
        bigint patient_sk FK
        bigint provider_sk FK
        bigint facility_sk FK
        bigint primary_dx_sk FK
        int encounter_date_sk FK
        string encounter_type
        int length_of_stay_days
        decimal total_charges_amt
    }

    FCT_CLAIMS {
        bigint claim_sk PK
        string claim_nk
        bigint patient_sk FK
        bigint billing_provider_sk FK
        bigint facility_sk FK
        bigint primary_dx_sk FK
        int service_date_sk FK
        int paid_date_sk FK
        string claim_status
        decimal billed_amt
        decimal allowed_amt
        decimal paid_amt
    }
```

---

## Grain definitions

| Table | Grain | Notes |
|---|---|---|
| `dim_patient` | One row per patient version (SCD2) | `is_current = TRUE` marks the active version |
| `dim_provider` | One row per provider (Type 1) | Synthetic NPI; specialty as attribute |
| `dim_facility` | One row per facility (Type 1) | Site of care / care delivery location |
| `dim_diagnosis` | One row per ICD-10 code | Conformed across encounters & claims |
| `dim_date` | One row per calendar day | Shared conformed date dimension |
| `fct_encounters` | One row per clinical encounter | Primary diagnosis only at grain; secondary dx via bridge (out of scope) |
| `fct_claims` | One row per claim header | Line-level claim detail out of scope for this demo |

---

## Conformed dimensions

`dim_patient`, `dim_provider`, `dim_facility`, `dim_diagnosis`, and `dim_date` are **conformed**: the same surrogate keys are used by both `fct_encounters` and `fct_claims`. This enables cross-domain questions such as:

- Encounter volume vs. claim paid amount by diagnosis chapter
- Provider panel size (encounters) vs. revenue (claims)
- Facility utilization and cost trends on a shared calendar

---

## Load order

```mermaid
flowchart LR
    A[seeds / staging] --> B[dim_date]
    A --> C[dim_diagnosis]
    A --> D[dim_provider]
    A --> E[dim_facility]
    A --> F[dim_patient SCD2]
    F --> G[entity resolution keys]
    B --> H[fct_encounters]
    C --> H
    D --> H
    E --> H
    F --> H
    B --> I[fct_claims]
    C --> I
    D --> I
    E --> I
    F --> I
```

1. Load / generate `dim_date`
2. Load reference dims: diagnosis, provider, facility
3. Resolve enterprise patient keys → load `dim_patient` (SCD2)
4. Load facts with surrogate key lookups

---

## Source systems (synthetic)

| Source alias | Feeds | Notes |
|---|---|---|
| `EHR_ENC` | encounters, diagnosis on visit | Clinical visit events |
| `RCM_CLM` | claims headers | Revenue cycle / billing |
| `MPI_SRC_A` / `MPI_SRC_B` | patient identity fragments | Used in entity-resolution demo |

All source extracts in `seeds/` are labeled **SYNTHETIC**.

---

## Metrics supported (examples)

- Encounter count by type, facility, specialty, diagnosis chapter
- Average length of stay (inpatient)
- Claim paid / allowed / billed amounts by service month
- Denial or rejection rate (`claim_status`)
- Patient panel continuity (SCD2 history of attributed PCP / ZIP3)

---

## Related docs

- [`hipaa-design-notes.md`](hipaa-design-notes.md) — tokenization & least privilege
- [`../entity-resolution/README.md`](../entity-resolution/README.md) — MPI matching approach
- [`../data-quality/README.md`](../data-quality/README.md) — DQ checklist
