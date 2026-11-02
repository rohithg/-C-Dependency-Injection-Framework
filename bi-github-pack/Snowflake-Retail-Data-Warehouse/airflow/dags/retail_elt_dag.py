"""
Retail ELT orchestration for Snowflake + dbt.

Daily flow:
  1. Stage seed/export CSVs into Snowflake internal stage (demo) OR
     PUT files from an S3/blob extract landing zone
  2. COPY INTO RAW.* tables (sql/load/01_copy_into_raw.sql)
  3. dbt deps → seed (optional local path) → run → test → docs

Configure Airflow Variables:
  retail_dbt_project_dir, retail_dbt_profiles_dir, retail_dbt_target,
  retail_seed_dir (path to seeds/*.csv on the worker),
  retail_snowsql_conn_id (optional Airflow Snowflake connection)

Requires: apache-airflow, snowflake-connector-python (or SnowSQL on PATH), dbt-snowflake.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta
from pathlib import Path

from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator


DEFAULT_ARGS = {
    "owner": "rohith-gangapuram",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

DBT_PROJECT_DIR = "{{ var.value.get('retail_dbt_project_dir', '/opt/airflow/dbt/Snowflake-Retail-Data-Warehouse') }}"
DBT_PROFILES_DIR = "{{ var.value.get('retail_dbt_profiles_dir', '/opt/airflow/.dbt') }}"
DBT_TARGET = "{{ var.value.get('retail_dbt_target', 'snowflake') }}"
SEED_DIR = "{{ var.value.get('retail_seed_dir', '/opt/airflow/dbt/Snowflake-Retail-Data-Warehouse/seeds') }}"

# Map seed files → stage subfolders used by sql/load/01_copy_into_raw.sql
SEED_TO_STAGE = {
    "raw_customers.csv": "customers",
    "raw_products.csv": "products",
    "raw_orders.csv": "orders",
    "raw_invoices.csv": "invoices",
    "raw_shipments.csv": "shipments",
    "raw_locations.csv": "locations",
}


def stage_and_copy_into_raw(**context) -> str:
    """
    Production-shaped extract/load task:
      - Resolves seed (or extract export) CSVs on the worker
      - PUTs each file into @retail_dw.raw.stg_retail_inbound/<entity>/
      - Runs COPY INTO for every RAW table

    When SNOWFLAKE_* env vars (or an Airflow Snowflake hook) are absent,
    validates files locally and writes a load manifest so the DAG still
    demonstrates the contract end-to-end in CI / portfolio demos.
    """
    logical_date = context.get("ds", "unknown")
    seed_dir = Path(os.environ.get("RETAIL_SEED_DIR", context["params"].get("seed_dir", ".")))
    # Airflow templates seed_dir via params below; also accept env override.
    if "seed_dir" in context.get("params", {}):
        seed_dir = Path(str(context["params"]["seed_dir"]))

    manifest = []
    missing = []
    for filename, stage_folder in SEED_TO_STAGE.items():
        path = seed_dir / filename
        if not path.exists():
            missing.append(str(path))
            continue
        row_count = max(sum(1 for _ in path.open()) - 1, 0)
        manifest.append(
            {
                "file": filename,
                "stage": f"@retail_dw.raw.stg_retail_inbound/{stage_folder}/",
                "rows": row_count,
                "bytes": path.stat().st_size,
            }
        )

    if missing:
        raise FileNotFoundError(
            "Extract/load expected source files missing: " + ", ".join(missing)
        )

    account = os.environ.get("SNOWFLAKE_ACCOUNT")
    user = os.environ.get("SNOWFLAKE_USER")
    password = os.environ.get("SNOWFLAKE_PASSWORD")
    warehouse = os.environ.get("SNOWFLAKE_WAREHOUSE", "transform_wh")
    database = os.environ.get("SNOWFLAKE_DATABASE", "retail_dw")

    print(f"[extract] logical_date={logical_date}")
    for item in manifest:
        print(
            f"[extract] stage {item['file']} → {item['stage']} "
            f"({item['rows']} rows, {item['bytes']} bytes)"
        )

    if not (account and user and password):
        print(
            "[extract] Snowflake credentials not set — validated local files and "
            "skipped PUT/COPY. Wire SNOWFLAKE_* env or an Airflow Snowflake hook "
            "to execute sql/load/01_copy_into_raw.sql."
        )
        return f"extract_validated:{logical_date}:files={len(manifest)}"

    try:
        import snowflake.connector  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "snowflake-connector-python required when SNOWFLAKE_* credentials are set"
        ) from exc

    conn = snowflake.connector.connect(
        account=account,
        user=user,
        password=password,
        warehouse=warehouse,
        database=database,
        schema="raw",
    )
    try:
        cur = conn.cursor()
        cur.execute("create stage if not exists retail_dw.raw.stg_retail_inbound")
        for item in manifest:
            local = seed_dir / item["file"]
            stage = item["stage"]
            # PUT local CSV into stage folder, overwrite for idempotent daily runs
            cur.execute(f"put file://{local} {stage} auto_compress=true overwrite=true")
            print(f"[extract] PUT ok → {stage}")

        copy_sql_path = seed_dir.parent / "sql" / "load" / "01_copy_into_raw.sql"
        if copy_sql_path.exists():
            statements = [
                s.strip()
                for s in copy_sql_path.read_text().split(";")
                if s.strip() and not s.strip().startswith("--")
            ]
            for stmt in statements:
                # Skip CREATE STAGE already handled
                if stmt.lower().startswith("create stage"):
                    continue
                cur.execute(stmt)
                print(f"[extract] COPY executed ({cur.rowcount} rows)")
        else:
            for item in manifest:
                table = item["file"].replace(".csv", "")
                cur.execute(
                    f"""
                    copy into retail_dw.raw.{table}
                    from {item['stage']}
                    file_format = (type = csv field_optionally_enclosed_by = '"'
                                   skip_header = 1 null_if = ('', 'NULL'))
                    match_by_column_name = case_insensitive
                    on_error = 'ABORT_STATEMENT'
                    """
                )
                print(f"[extract] COPY into {table}: {cur.rowcount} rows")
    finally:
        conn.close()

    return f"extract_loaded:{logical_date}:files={len(manifest)}"


with DAG(
    dag_id="retail_elt_daily",
    description="Daily ELT: stage+COPY INTO RAW → dbt run → dbt test → docs",
    default_args=DEFAULT_ARGS,
    schedule_interval="0 6 * * *",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    max_active_runs=1,
    params={"seed_dir": "/opt/airflow/dbt/Snowflake-Retail-Data-Warehouse/seeds"},
    tags=["retail", "snowflake", "dbt", "elt", "supply-chain"],
    doc_md=__doc__,
) as dag:

    extract_raw = PythonOperator(
        task_id="stage_and_copy_into_raw",
        python_callable=stage_and_copy_into_raw,
        op_kwargs={},
    )

    dbt_deps = BashOperator(
        task_id="dbt_deps",
        bash_command=(
            f"cd {DBT_PROJECT_DIR} && "
            f"dbt deps --profiles-dir {DBT_PROFILES_DIR}"
        ),
    )

    # Seeds power local/demo warehouses when RAW is not yet loaded from stage.
    dbt_seed = BashOperator(
        task_id="dbt_seed",
        bash_command=(
            f"cd {DBT_PROJECT_DIR} && "
            f"dbt seed --profiles-dir {DBT_PROFILES_DIR} --target {DBT_TARGET} "
            f"--full-refresh"
        ),
    )

    dbt_run = BashOperator(
        task_id="dbt_run",
        bash_command=(
            f"cd {DBT_PROJECT_DIR} && "
            f"dbt run --profiles-dir {DBT_PROFILES_DIR} --target {DBT_TARGET}"
        ),
    )

    dbt_test = BashOperator(
        task_id="dbt_test",
        bash_command=(
            f"cd {DBT_PROJECT_DIR} && "
            f"dbt test --profiles-dir {DBT_PROFILES_DIR} --target {DBT_TARGET}"
        ),
    )

    dbt_snapshot = BashOperator(
        task_id="dbt_snapshot",
        bash_command=(
            f"cd {DBT_PROJECT_DIR} && "
            f"dbt snapshot --profiles-dir {DBT_PROFILES_DIR} --target {DBT_TARGET}"
        ),
    )

    dbt_docs = BashOperator(
        task_id="dbt_docs_generate",
        bash_command=(
            f"cd {DBT_PROJECT_DIR} && "
            f"dbt docs generate --profiles-dir {DBT_PROFILES_DIR} --target {DBT_TARGET}"
        ),
    )

    extract_raw >> dbt_deps >> dbt_seed >> dbt_run >> dbt_test >> dbt_snapshot >> dbt_docs
