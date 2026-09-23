"""
Retail ELT orchestration for Snowflake + dbt.

Daily flow:
  1. Extract stub — placeholder for ERP/CRM/TMS/YMS → Snowflake RAW loads
  2. dbt seed (optional demo) / dbt run — transform staging → intermediate → marts
  3. dbt test — data quality gates on star schema
  4. dbt docs generate — refresh documentation site artifacts

Configure Airflow Variables (or env) for dbt project dir and profiles dir.
Requires: apache-airflow, and dbt on the PATH of the worker (or Astro/Cosmos).
"""

from __future__ import annotations

from datetime import datetime, timedelta

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

# Prefer Airflow Variable in production; Path fallback keeps the DAG importable locally.
DBT_PROJECT_DIR = "{{ var.value.get('retail_dbt_project_dir', '/opt/airflow/dbt/Snowflake-Retail-Data-Warehouse') }}"
DBT_PROFILES_DIR = "{{ var.value.get('retail_dbt_profiles_dir', '/opt/airflow/.dbt') }}"
DBT_TARGET = "{{ var.value.get('retail_dbt_target', 'snowflake') }}"


def extract_to_snowflake_raw(**context) -> str:
    """
    Stub extract task representing incremental loads from source systems
    (NetSuite ERP, CRM, TMS, YMS) into Snowflake RAW landing tables.

    In production this would call Fivetran/Airbyte/custom Python connectors
    or Snowflake Snowpipe / COPY INTO jobs. Here we log the contract only.
    """
    logical_date = context.get("ds", "unknown")
    sources = [
        "NETSUITE.customers → RAW.RAW_CUSTOMERS",
        "NETSUITE.orders → RAW.RAW_ORDERS",
        "NETSUITE.items → RAW.RAW_PRODUCTS",
        "NETSUITE.invoices → RAW.RAW_INVOICES",
        "TMS.shipments → RAW.RAW_SHIPMENTS",
        "YMS.locations → RAW.RAW_LOCATIONS",
    ]
    print(f"[extract] logical_date={logical_date}")
    for src in sources:
        print(f"[extract] queued load: {src}")
    print("[extract] stub complete — replace with real connector / COPY INTO")
    return f"extract_ok:{logical_date}"


with DAG(
    dag_id="retail_elt_daily",
    description="Daily ELT: source extract stub → dbt run → dbt test → docs",
    default_args=DEFAULT_ARGS,
    schedule_interval="0 6 * * *",  # 06:00 UTC daily
    start_date=datetime(2024, 1, 1),
    catchup=False,
    max_active_runs=1,
    tags=["retail", "snowflake", "dbt", "elt", "supply-chain"],
    doc_md=__doc__,
) as dag:

    extract_raw = PythonOperator(
        task_id="extract_sources_to_raw",
        python_callable=extract_to_snowflake_raw,
    )

    dbt_deps = BashOperator(
        task_id="dbt_deps",
        bash_command=(
            f"cd {DBT_PROJECT_DIR} && "
            f"dbt deps --profiles-dir {DBT_PROFILES_DIR}"
        ),
    )

    # Seeds power local/demo warehouses; in prod RAW is loaded by extract above.
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

    dbt_docs = BashOperator(
        task_id="dbt_docs_generate",
        bash_command=(
            f"cd {DBT_PROJECT_DIR} && "
            f"dbt docs generate --profiles-dir {DBT_PROFILES_DIR} --target {DBT_TARGET}"
        ),
    )

    extract_raw >> dbt_deps >> dbt_seed >> dbt_run >> dbt_test >> dbt_docs
