from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class EtlConfig:
    root: Path
    raw_dir: Path
    out_dir: Path
    sql_dir: Path
    database: str = "ANALYTICS"
    raw_schema: str = "RAW"
    marts_schema: str = "MARTS"
    warehouse: str = "BI_WH"
    role: str = "SYSADMIN"
    load_snowflake: bool = False

    @classmethod
    def from_env(cls, root: Path | None = None, load_snowflake: bool | None = None) -> "EtlConfig":
        root = root or Path(__file__).resolve().parents[1]
        flag = (
            load_snowflake
            if load_snowflake is not None
            else os.getenv("ETL_LOAD_SNOWFLAKE", "").lower() in {"1", "true", "yes"}
        )
        return cls(
            root=root,
            raw_dir=root / "data" / "raw",
            out_dir=root / "data" / "out" / "parquet",
            sql_dir=root / "sql",
            database=os.getenv("SF_DATABASE", "ANALYTICS"),
            raw_schema=os.getenv("SF_SCHEMA_RAW", "RAW"),
            marts_schema=os.getenv("SF_SCHEMA_MARTS", "MARTS"),
            warehouse=os.getenv("SF_WAREHOUSE", "BI_WH"),
            role=os.getenv("SF_ROLE", "SYSADMIN"),
            load_snowflake=flag,
        )

    def snowflake_ready(self) -> bool:
        return bool(os.getenv("SF_ACCOUNT") and os.getenv("SF_USER") and (
            os.getenv("SF_PASSWORD") or os.getenv("SF_PRIVATE_KEY_PATH")
        ))
