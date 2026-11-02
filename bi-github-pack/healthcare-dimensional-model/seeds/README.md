# Seeds — SYNTHETIC ONLY

All CSV files in this directory are **fabricated demo data**. They contain:

- Synthetic patient / member IDs (`SYN-EHR-*`, `SYN-CLM-*`)
- Fictional given/family names
- Synthetic provider NPIs (`100000000x` — not real NPIs)
- Fictional facility names
- Public ICD-10-CM code examples (abbreviated)

**Do not** replace these with real PHI. **Do not** commit production extracts.

| File | Purpose |
|---|---|
| `synthetic_patients_src_a.csv` | EHR identity extract |
| `synthetic_patients_src_b.csv` | Claims/enrollment identity extract (for matching) |
| `synthetic_providers.csv` | Provider reference |
| `synthetic_facilities.csv` | Facility reference |
| `synthetic_diagnoses.csv` | ICD-10 reference |
| `synthetic_encounters.csv` | Clinical encounter events |
| `synthetic_claims.csv` | Claim header events |

Comment lines beginning with `#` should be stripped or skipped by your loader.
