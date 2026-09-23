# Data Quality — Healthcare Dimensional Model

**Synthetic demo only.** These checks illustrate how analytics engineers encode trust into clinical and claims data products.

---

## Philosophy

1. **Fail the build** on broken referential integrity and invalid clinical code formats.
2. **Warn** on freshness / volume anomalies that may be environmental.
3. Prefer tests co-located with models (`schema.yml`) plus singular SQL tests for complex rules.
4. Document expectations in a checklist that maps cleanly to Great Expectations–style suites or dbt tests.

---

## Great Expectations–style checklist

| Expectation | Target | Severity | Implementation |
|---|---|---|---|
| `expect_column_values_to_not_be_null` | `patient_sk`, `encounter_date_sk`, `icd10_cd` | Error | dbt `not_null` |
| `expect_column_values_to_be_unique` | `encounter_nk`, `claim_nk`, current `enterprise_patient_id` | Error | dbt `unique` |
| `expect_column_values_to_be_in_set` | `encounter_type`, `claim_status`, `sex_cd` | Error | dbt `accepted_values` |
| `expect_column_pair_values_A_to_be_greater_than_B` | `discharge_date >= encounter_date` | Error | singular SQL |
| `expect_column_values_to_match_regex` | ICD-10 format on `icd10_cd` | Error | dbt test / SQL |
| `expect_column_sum_to_be_between` | `paid_amt` monthly totals | Warn | volume SQL |
| `expect_multicolumn_sum_values_to_be_between` | `paid + member_resp ≈ allowed` (±$1) | Warn | singular SQL |
| `expect_compound_columns_to_be_unique` | `(enterprise_patient_id)` where `is_current` | Error | partial unique index + test |
| `expect_column_values_to_be_between` | `length_of_stay_days` 0–365 | Error | singular SQL |
| `expect_table_row_count_to_be_between` | encounters per load | Warn | volume SQL |

---

## SQL assertion suite

Runnable scripts in this folder:

| File | Focus |
|---|---|
| [`dq_referential_integrity.sql`](dq_referential_integrity.sql) | Orphan FKs from facts → dims |
| [`dq_valid_dates.sql`](dq_valid_dates.sql) | Chronology & calendar membership |
| [`dq_diagnosis_format.sql`](dq_diagnosis_format.sql) | ICD-10 pattern & unknown codes |
| [`dq_claims_amounts.sql`](dq_claims_amounts.sql) | Non-negative & reconciliation |
| [`dq_scd2_patient.sql`](dq_scd2_patient.sql) | One current row; non-overlapping dates |

dbt equivalents: [`../dbt/models/marts/core/schema.yml`](../dbt/models/marts/core/schema.yml) and [`../dbt/tests/`](../dbt/tests/).

---

## Operational cadence

| Cadence | Checks |
|---|---|
| Every build (CI) | Uniqueness, not-null, relationships, ICD format, SCD2 current-row |
| Daily | Orphan counts, date chronology, amount reconciliation |
| Weekly | Volume vs. trailing 4-week baseline, denial-rate drift |

---

## Interpreting failures

| Failure | Likely cause | First action |
|---|---|---|
| Orphan `patient_sk` | Entity resolution miss or SCD2 timing | Check crosswalk + load order |
| Invalid ICD-10 | Upstream coding / truncation | Quarantine rows; fix staging cast |
| Overlapping SCD2 | Merge bug | Halt publishes; repair history |
| Negative `paid_amt` | Adjustment sign convention | Confirm source semantics; stage transforms |
