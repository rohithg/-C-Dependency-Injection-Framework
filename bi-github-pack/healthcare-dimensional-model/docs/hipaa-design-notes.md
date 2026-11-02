# HIPAA-Aware Design Notes (Educational)

> **Not legal advice.** These notes describe common engineering patterns used when designing analytics platforms that *may* process Protected Health Information (PHI) under the U.S. HIPAA Privacy and Security Rules. They are educational portfolio material for analytics engineers. Consult your compliance, privacy, and legal teams before handling real PHI.

**This repository contains only synthetic data.** No real patient identifiers, clinical notes, or production extracts are present.

---

## Goals

1. Minimize exposure of identifiers in analytics pipelines.
2. Separate *identity* from *clinical/administrative facts* where practical.
3. Enforce least-privilege access to warehouse objects and BI semantic models.
4. Make it obvious when data is synthetic vs. production-bound.

---

## What we store in this demo model

| Attribute class | Demo approach | Production consideration |
|---|---|---|
| Enterprise patient key | Synthetic `enterprise_patient_id` (`EMPI-SYN-…`) | Opaque surrogate; never reuse SSN/MRN as PK |
| Name | Tokenized / hashed stand-in (`first_name_token`) | Prefer tokens; restrict clear-text to limited vaults |
| Date of birth | Full date in demo (synthetic) | Often limited to year or age band in broad-access layers |
| Address | ZIP3 only | Prefer geographic aggregation over street address |
| NPI / provider | Synthetic NPI strings | Real NPI is public; still control join sprawl |
| Diagnosis codes | ICD-10 codes (public code set) | Codes alone are not identifiers but can be sensitive in context |
| Free-text notes | **Not stored** | Clinical notes are high-risk; exclude from BI marts by default |

---

## Tokenization pattern

```
Source MRN / Member ID  ──►  Tokenization service  ──►  enterprise_patient_id
                                      │
                                      └── mapping table (highly restricted)
```

Design rules used in this project:

- Facts and most dimensions join on **`patient_sk`** / **`enterprise_patient_id`**, not source MRNs.
- Clear-text identity fields (if ever present) live in a **restricted schema** (`phi_restricted`), not in `marts`.
- Seed CSVs use obvious prefixes: `SYN-`, `DEMO-`, `EMPI-SYN-`.

Example column strategy on `dim_patient`:

| Column | Access tier |
|---|---|
| `patient_sk` | Broad (analysts) |
| `enterprise_patient_id` | Broad (analysts) |
| `first_name_token` | Broad (analysts) — not reversible in demo |
| `birth_date` | Restricted in production marts |
| Source MRN mapping | Break-glass / identity team only |

---

## Least privilege

Recommended warehouse roles (illustrative):

| Role | Can read | Cannot |
|---|---|---|
| `role_bi_analyst` | `marts.*` aggregated / tokenized | `phi_restricted.*`, raw landing |
| `role_data_engineer` | staging + marts (non-prod) | Production PHI mapping tables without ticket |
| `role_privacy_steward` | mapping / audit tables | Unrelated clinical notes |
| `role_service_etl` | write staging, merge dims/facts | Interactive BI tools |

Enforce via:

- Schema-level grants (not table-by-table sprawl)
- Row-access policies / column masking for residual identifiers
- Separate environments: `dev` (synthetic) → `uat` (de-id) → `prod` (controlled)

---

## Pipeline hygiene

1. **Never commit PHI** — CI scans for SSN-like patterns, MRN columns named from real feeds, and unscoped exports.
2. **Label synthetic data** — file headers and README banners; seed filenames include `synthetic_`.
3. **Audit joins** — entity resolution outputs are audited; match scores below threshold do not auto-merge.
4. **Minimize retention** in scratch / temp schemas; TTL on staging clones.
5. **Encrypt in transit and at rest** — warehouse defaults; secrets in a vault, not `.env` in git.

---

## De-identification vs. limited dataset

| Approach | Use when |
|---|---|
| Safe Harbor / Expert Determination de-id | Broad research or vendor sharing |
| Limited Data Set (LDS) | Data use agreements with covered entities / BAAs |
| Tokenized production mart | Internal analytics with need-to-know |

This demo approximates a **tokenized mart**: useful for BI, without shipping clear-text identity.

---

## What this repo deliberately excludes

- Real member or medical record numbers
- Clinical free-text notes
- Full street addresses or precise geolocation
- Images, DICOM, or genomic data
- Production connection strings or credentials

---

## Practical checklist for analytics engineers

- [ ] Confirm BAA / DUA before connecting any warehouse to production PHI sources
- [ ] Prefer synthetic or de-identified datasets for development and CI
- [ ] Keep identity resolution mapping tables out of self-service BI
- [ ] Document grain and PHI classification in `schema.yml` / data catalog
- [ ] Test that masked columns remain masked for analyst roles
- [ ] Review dashboards for quasi-identifier combinations (rare diagnosis + ZIP3 + age)

---

## References (public)

- HHS HIPAA Privacy Rule overview (hhs.gov)
- NIST guidance on de-identification
- Your organization's privacy office & information security policies

Again: **educational only — not legal advice.**
