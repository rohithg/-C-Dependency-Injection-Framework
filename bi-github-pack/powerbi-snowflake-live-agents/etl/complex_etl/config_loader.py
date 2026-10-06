from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import yaml


@dataclass
class PipelineConfig:
    root: Path
    run_id: str
    bronze_dir: Path
    silver_dir: Path
    gold_dir: Path
    quarantine_dir: Path
    state_dir: Path
    report_dir: Path
    raw_dir: Path
    cdc_dir: Path
    api_cache_dir: Path
    max_retries: int = 2
    fail_on_error_gate: bool = True
    settings: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(cls, root: Path | None = None, run_id: str | None = None) -> "PipelineConfig":
        from datetime import datetime, timezone
        import uuid

        root = root or Path(__file__).resolve().parents[1]
        complex_root = root / "complex_etl"
        cfg_path = complex_root / "config" / "pipeline.yaml"
        settings = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) if cfg_path.exists() else {}
        rid = run_id or f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}_{uuid.uuid4().hex[:8]}"
        out = complex_root / "data" / "lake"
        return cls(
            root=complex_root,
            run_id=rid,
            bronze_dir=out / "bronze",
            silver_dir=out / "silver",
            gold_dir=out / "gold",
            quarantine_dir=out / "quarantine",
            state_dir=complex_root / "data" / "state",
            report_dir=complex_root / "data" / "reports",
            raw_dir=complex_root / "data" / "raw",
            cdc_dir=complex_root / "data" / "cdc",
            api_cache_dir=complex_root / "data" / "api_cache",
            max_retries=int(settings.get("max_retries", 2)),
            fail_on_error_gate=bool(settings.get("fail_on_error_gate", True)),
            settings=settings or {},
        )
