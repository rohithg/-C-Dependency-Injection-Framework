# Senior ETL — step-by-step walkthrough

This document explains **every step** of `etl/senior_etl`, the enterprise pipeline a senior data engineer would design and operate.

## What problem it solves

In production you rarely “just load a CSV.” You must:

1. Guarantee producers won’t silently break consumers (**contracts**)
2. Re-run safely without duplicating facts (**idempotency**)
3. Track who changed what and when (**audit / batch control**)
4. Join facts to the dimension **as it looked on the event date** (**PIT**)
5. Survive missing reference data (**late-arriving / inferred dims**)
6. Model different analytical grains (**transactional / accumulating / periodic facts**)
7. Stop bad data from landing in BI (**anomaly gates + SLA**)

---

## Step 0 — Seed the landing zone

```bash
python3 -m senior_etl seed
```

Creates `data/landing/` files that mimic an enterprise **landing zone** (S3/ADLS equivalent): customers (with PII), products, orders (with milestone dates), order lines (includes unknown product `P999`), and FX rates.

---

## Step 1 — Start a batch (control plane)

Command: `python3 -m senior_etl run --batch-id batch_demo_001`

The platform:

- Creates / resumes a **`batch_id`**
- Fingerprints source files with **SHA-256 checksums**
- Appends a `RUNNING` row to `batch_control.jsonl`
- Emits an audit event `batch_started`

If this `batch_id` already finished successfully, the run **no-ops** (idempotent).  
`python3 -m senior_etl replay --batch-id …` forces a controlled reprocess and marks `REPLAYED`.

**Why seniors care:** backfills and retries must not double-count revenue.

---

## Step 2 — Publish data contracts (schema registry)

Task: `publish_contracts`

- Loads YAML contracts (`contracts/*.yaml`)
- Publishes versions into a file-backed **schema registry**
- Rejects **breaking changes** (removed required fields, dtype changes, PK changes)

**Why seniors care:** analytics breaks when upstream renames `customer_id` → `cust_id` without a contract gate.

---

## Step 3 — Fan-out ingest + contract validation (parallel)

Tasks (run concurrently after contracts):

- `ingest_validate_customers`
- `ingest_validate_products`
- `ingest_validate_orders`
- `ingest_validate_order_lines`

For each entity the pipeline:

1. Reads landing CSV  
2. Validates required columns, nulls, primary-key uniqueness against the contract  
3. Parses dates  
4. **Masks PII** on customers (`email`/`phone` → `***` + last4)  
5. Computes a **row content hash** (`_row_hash`)  
6. Stamps `_batch_id`  
7. Writes bronze parquet partitioned by `batch_id=…`

**Why seniors care:** parallel ingest cuts wall-clock time; hashing enables merge-by-content later; PII never lands clear-text in the lake.

---

## Step 4 — Bronze finalize

Task: `bronze_land`

Lands FX rates into bronze with the same `batch_id`. Bronze is the **immutable raw+technical metadata** layer.

---

## Step 5 — Silver SCD2 dimensions

Task: `silver_scd2_dims`

Builds Type-2 history for customers/products:

- New natural key → insert version 1 (`is_current=true`)
- Tracked attribute change → close old version (`effective_to=as_of`) and open version N+1
- Publishes both full history (`dim_*_scd2`) and current (`dim_*_current`)
- Uses **hash merge on `dim_sk`** so republishing the same version is a no-op

**Why seniors care:** “customer region today” ≠ “customer region on the order date.”

---

## Step 6 — Gold facts (the senior modeling move)

Task: `gold_facts`

### 6a Late-arriving dimensions
Order line `L11` references product `P999` which does not exist yet.  
Pipeline creates an **inferred member** (`UNKNOWN PRODUCT`, `_inferred=true`) so facts aren’t dropped.

### 6b Point-in-time (PIT) join
Joins each fact row to the dimension version where:

`effective_from <= order_date < effective_to`

So historical truth is preserved even after SCD2 updates.

### 6c FX as-of enrichment
`join_asof` picks the latest FX rate on/before the order date (EUR/GBP → USD).

### 6d Three fact styles

| Fact | Grain | Purpose |
|--|--|--|
| `fct_orders_txn` | order line (transactional) | Revenue, margin, detailed BI |
| `fct_order_accumulating` | order (accumulating snapshot) | Promise→ship→deliver pipeline ages |
| `fct_revenue_periodic_daily` | day×region (periodic snapshot) | As-of balances / executive rollups |

### 6e Idempotent load
`delete_insert_by_batch`: remove prior rows for this `batch_id`, then insert.  
Replays replace the same logical batch instead of appending duplicates.

---

## Step 7 — Anomaly + SLA gates

Task: `anomaly_gates`

Checks configurable thresholds:

- row count bounds  
- net revenue USD bounds  

Also records whether total DAG time met `sla_seconds`.

Failures **fail the batch** (status `FAILED` in control table) so bad gold never silently feeds Power BI.

---

## Step 8 — Close the batch

On success:

- Control table → `SUCCESS` or `REPLAYED`
- Audit log → `batch_finished`
- Reports → `reports/latest.json`, per-batch run JSON, anomaly JSON

---

## How to run

```bash
cd bi-github-pack/powerbi-snowflake-live-agents/etl
python3 -m senior_etl seed
python3 -m senior_etl run --batch-id batch_demo_001
python3 -m senior_etl run --batch-id batch_demo_001          # skips (idempotent)
python3 -m senior_etl replay --batch-id batch_demo_001       # controlled backfill
python3 -m pytest senior_etl/tests -q
```

## Mental model

```text
Landing files
  → contract publish + parallel validate/mask/hash
    → bronze (batch partitions)
      → silver SCD2
        → inferred dims + PIT + FX
          → gold (txn / accumulating / periodic)
            → anomaly/SLA gates
              → batch control + audit + reports
```

That end-to-end ownership — contracts, idempotency, temporal correctness, multiple fact patterns, and operational controls — is what separates a senior DE pipeline from a simple script.
