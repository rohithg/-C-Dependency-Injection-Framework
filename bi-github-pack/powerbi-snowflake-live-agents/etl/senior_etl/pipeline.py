from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import polars as pl
import yaml

from senior_etl.contracts.registry import (
    SchemaRegistry,
    file_checksum,
    load_contract,
    row_hash,
)
from senior_etl.control.batch import AuditLog, BatchControlStore
from senior_etl.gold.facts import (
    build_accumulating_snapshot,
    build_periodic_snapshot,
    build_transactional_fact,
)
from senior_etl.load.merge import (
    delete_insert_by_batch,
    idempotent_merge_by_hash,
    mask_pii,
    read_parquet,
    write_parquet,
)
from senior_etl.ops.dag import EnterpriseDag, TaskSpec
from senior_etl.quality.anomalies import evaluate_anomalies
from senior_etl.silver.temporal import (
    ensure_inferred_dimension,
    point_in_time_join,
    scd2_merge,
)


class SeniorPlatform:
    def __init__(self, root: Path | None = None, batch_id: str | None = None):
        self.root = root or Path(__file__).resolve().parent
        self.cfg = yaml.safe_load((self.root / "config" / "platform.yaml").read_text())
        self.batch_id = batch_id or datetime.now(timezone.utc).strftime("batch_%Y%m%dT%H%M%SZ")
        self.landing = self.root / "data" / "landing"
        self.lake = self.root / "data" / "lake"
        self.control_dir = self.root / "data" / "control"
        self.reports = self.root / "data" / "reports"
        self.registry = SchemaRegistry(self.control_dir / "schema_registry")
        self.batches = BatchControlStore(self.control_dir / "batch_control.jsonl")
        self.audit = AuditLog(self.control_dir / "audit.jsonl")
        self.metrics: dict[str, Any] = {}

    def run(self, force_replay: bool = False) -> dict[str, Any]:
        if self.batches.already_successful(self.batch_id) and not force_replay:
            return {
                "batch_id": self.batch_id,
                "skipped": True,
                "reason": "batch already SUCCESS/REPLAYED (idempotent no-op)",
            }

        sources = {
            "customers": self.landing / "customers.csv",
            "products": self.landing / "products.csv",
            "orders": self.landing / "orders.csv",
            "order_lines": self.landing / "order_lines.csv",
            "fx": self.landing / "fx_rates.csv",
        }
        checksums = {k: file_checksum(v) for k, v in sources.items() if v.exists()}
        attempt = 1
        prev = self.batches.get(self.batch_id)
        if prev:
            attempt = int(prev.get("attempt", 1)) + (1 if force_replay else 0)
        self.batches.start(self.batch_id, checksums, attempt=attempt)
        self.audit.emit("batch_started", {"batch_id": self.batch_id, "checksums": checksums})

        try:
            outcomes = EnterpriseDag(self._tasks(), max_workers=4).run()
            # SLA check
            total_ms = sum(o.duration_ms for o in outcomes.values())
            self.metrics["total_duration_ms"] = round(total_ms, 2)
            self.metrics["sla_seconds"] = self.cfg.get("sla_seconds", 30)
            self.metrics["sla_ok"] = (total_ms / 1000) <= float(self.cfg.get("sla_seconds", 30))
            status = "REPLAYED" if force_replay else "SUCCESS"
            if force_replay:
                self.batches.mark_replayed(self.batch_id, self.metrics)
            else:
                self.batches.succeed(self.batch_id, self.metrics)
            self.audit.emit("batch_finished", {"batch_id": self.batch_id, "status": status, "metrics": self.metrics})
            report = {
                "batch_id": self.batch_id,
                "status": status,
                "metrics": self.metrics,
                "tasks": {
                    k: {"ok": v.ok, "ms": round(v.duration_ms, 2), "meta": v.meta}
                    for k, v in outcomes.items()
                },
            }
            self.reports.mkdir(parents=True, exist_ok=True)
            (self.reports / f"run_{self.batch_id}.json").write_text(
                json.dumps(report, indent=2) + "\n", encoding="utf-8"
            )
            (self.reports / "latest.json").write_text(
                json.dumps(report, indent=2) + "\n", encoding="utf-8"
            )
            return report
        except Exception as exc:
            self.batches.fail(self.batch_id, str(exc))
            self.audit.emit("batch_failed", {"batch_id": self.batch_id, "error": str(exc)})
            raise

    def _tasks(self) -> list[TaskSpec]:
        return [
            TaskSpec("publish_contracts", self._publish_contracts, retries=1),
            TaskSpec(
                "ingest_validate_customers",
                lambda: self._ingest_entity("customers"),
                depends_on=["publish_contracts"],
                parallel_group="ingest",
            ),
            TaskSpec(
                "ingest_validate_products",
                lambda: self._ingest_entity("products"),
                depends_on=["publish_contracts"],
                parallel_group="ingest",
            ),
            TaskSpec(
                "ingest_validate_orders",
                lambda: self._ingest_entity("orders"),
                depends_on=["publish_contracts"],
                parallel_group="ingest",
            ),
            TaskSpec(
                "ingest_validate_order_lines",
                lambda: self._ingest_entity("order_lines"),
                depends_on=["publish_contracts"],
                parallel_group="ingest",
            ),
            TaskSpec(
                "bronze_land",
                self._bronze_land,
                depends_on=[
                    "ingest_validate_customers",
                    "ingest_validate_products",
                    "ingest_validate_orders",
                    "ingest_validate_order_lines",
                ],
            ),
            TaskSpec("silver_scd2_dims", self._silver_scd2, depends_on=["bronze_land"]),
            TaskSpec("gold_facts", self._gold_facts, depends_on=["silver_scd2_dims"]),
            TaskSpec("anomaly_gates", self._anomaly_gates, depends_on=["gold_facts"]),
        ]

    def _publish_contracts(self) -> dict[str, Any]:
        published = {}
        for name in ["customers", "products", "orders", "order_lines"]:
            contract = load_contract(self.root / "contracts" / f"{name}.yaml")
            published[name] = self.registry.publish(contract)["version"]
        self.audit.emit("contracts_published", published)
        return published

    def _ingest_entity(self, name: str) -> dict[str, Any]:
        contract = load_contract(self.root / "contracts" / f"{name}.yaml")
        path = self.landing / f"{name}.csv"
        df = pl.read_csv(path, infer_schema_length=2000, truncate_ragged_lines=True)
        errors = self.registry.validate_frame(contract, df)
        if errors and self.cfg.get("contracts_strict", True):
            # quarantine invalid and raise for required contract failures
            q = self.lake / "quarantine" / self.batch_id / f"{name}_contract.parquet"
            write_parquet(df, q)
            raise ValueError(f"Contract violations for {name}: {errors}")
        # parse dates lightly
        for f in contract.fields:
            if f.dtype in {"date", "datetime"} and f.name in df.columns:
                df = df.with_columns(pl.col(f.name).str.to_datetime(strict=False).dt.date().alias(f.name))
        if name == "customers":
            df = mask_pii(df, self.cfg.get("pii_columns", {}).get("customers", []))
        out = self.lake / "bronze" / name / f"batch_id={self.batch_id}" / "data.parquet"
        # content hash for merge
        cols = [f.name for f in contract.fields if f.name in df.columns]
        df = df.with_columns(row_hash(df, cols))
        df = df.with_columns(pl.lit(self.batch_id).alias("_batch_id"))
        write_parquet(df, out)
        return {"rows": df.height, "path": str(out)}

    def _bronze_land(self) -> dict[str, Any]:
        # Already written per-entity; record FX bronze too
        fx_path = self.landing / "fx_rates.csv"
        fx = pl.read_csv(fx_path)
        fx = fx.with_columns(
            pl.col("as_of_date").str.to_date(strict=False),
            pl.lit(self.batch_id).alias("_batch_id"),
        )
        write_parquet(fx, self.lake / "bronze" / "fx_rates" / f"batch_id={self.batch_id}" / "data.parquet")
        return {"fx_rows": fx.height}

    def _read_bronze(self, name: str) -> pl.DataFrame:
        return read_parquet(
            self.lake / "bronze" / name / f"batch_id={self.batch_id}" / "data.parquet"
        )

    def _silver_scd2(self) -> dict[str, Any]:
        customers = self._read_bronze("customers").rename({"customer_id": "customer_nk"})
        products = self._read_bronze("products").rename({"product_id": "product_nk"})
        if "is_active" in products.columns and products.schema["is_active"] == pl.Utf8:
            products = products.with_columns(
                pl.col("is_active").str.to_lowercase().is_in(["1", "true", "yes"]).alias("is_active")
            )
        existing_c = read_parquet(self.lake / "silver" / "dim_customer_scd2.parquet")
        existing_p = read_parquet(self.lake / "silver" / "dim_product_scd2.parquet")

        # Use valid_from for as_of when present else batch date
        as_of = date(2026, 2, 12)
        scd_c = scd2_merge(
            existing_c,
            customers.select(
                "customer_nk",
                "customer_name",
                "region_name",
                "country_code",
                "segment",
                "credit_tier",
            ),
            nk="customer_nk",
            track=["customer_name", "region_name", "country_code", "segment", "credit_tier"],
            as_of=as_of,
        )
        scd_p = scd2_merge(
            existing_p,
            products.select(
                "product_nk",
                "product_name",
                "product_category",
                "brand",
                "unit_cost",
                "is_active",
            ),
            nk="product_nk",
            track=["product_name", "product_category", "brand", "unit_cost", "is_active"],
            as_of=as_of,
        )
        # Idempotent publish of SCD2 via hash merge on dim_sk
        if "dim_sk" in scd_c.columns:
            scd_c = scd_c.with_columns(
                row_hash(scd_c, [c for c in scd_c.columns if c != "_row_hash"])
            )
            scd_c = idempotent_merge_by_hash(existing_c, scd_c, ["dim_sk"])
        write_parquet(scd_c, self.lake / "silver" / "dim_customer_scd2.parquet")
        write_parquet(scd_p, self.lake / "silver" / "dim_product_scd2.parquet")
        current_c = scd_c.filter(pl.col("is_current")) if not scd_c.is_empty() else scd_c
        current_p = scd_p.filter(pl.col("is_current")) if not scd_p.is_empty() else scd_p
        write_parquet(current_c, self.lake / "silver" / "dim_customer_current.parquet")
        write_parquet(current_p, self.lake / "silver" / "dim_product_current.parquet")
        return {
            "customer_versions": scd_c.height,
            "product_versions": scd_p.height,
        }

    def _gold_facts(self) -> dict[str, Any]:
        orders = self._read_bronze("orders")
        lines = self._read_bronze("order_lines").rename({"product_id": "product_nk"})
        lines = lines.rename({"customer_id": "customer_nk"}) if "customer_id" in lines.columns else lines
        # bring customer_nk from orders
        orders = orders.with_columns(pl.col("customer_id").alias("customer_nk"))
        txn = build_transactional_fact(lines, orders)
        txn = txn.filter(~pl.col("order_status").is_in(["CANCELLED", "VOID"]))

        scd_c = read_parquet(self.lake / "silver" / "dim_customer_scd2.parquet")
        scd_p = read_parquet(self.lake / "silver" / "dim_product_scd2.parquet")

        # Late-arriving dims before PIT
        current_p = read_parquet(self.lake / "silver" / "dim_product_current.parquet")
        current_p = ensure_inferred_dimension(
            txn,
            current_p,
            fact_nk="product_nk",
            dim_nk="product_nk",
            defaults={
                "product_name": "UNKNOWN PRODUCT",
                "product_category": "UNKNOWN",
                "brand": "UNKNOWN",
                "unit_cost": 0.0,
                "is_active": False,
            },
        )
        write_parquet(current_p, self.lake / "silver" / "dim_product_current.parquet")
        inferred = current_p.filter(pl.col("_inferred") == True)  # noqa: E712
        if not inferred.is_empty():
            if scd_p.is_empty():
                scd_p = inferred
            else:
                cols = list(dict.fromkeys(list(scd_p.columns) + list(inferred.columns)))
                parts = []
                for p in [scd_p, inferred]:
                    for c in cols:
                        if c not in p.columns:
                            p = p.with_columns(pl.lit(None).alias(c))
                    parts.append(p.select(cols))
                scd_p = pl.concat(parts, how="vertical_relaxed").unique(
                    subset=["dim_sk"], keep="last"
                )
            write_parquet(scd_p, self.lake / "silver" / "dim_product_scd2.parquet")

        pit = point_in_time_join(
            txn, scd_c, "customer_nk", "customer_nk", "order_date", "customer_sk"
        )
        pit = point_in_time_join(
            pit, scd_p, "product_nk", "product_nk", "order_date", "product_sk"
        )

        # Attach current attributes for reporting convenience
        pit = pit.join(
            current_p.select("product_nk", "unit_cost", "product_category", "product_name"),
            on="product_nk",
            how="left",
            suffix="_cur",
        )
        pit = pit.join(
            read_parquet(self.lake / "silver" / "dim_customer_current.parquet").select(
                "customer_nk", "region_name", "country_code", "segment"
            ),
            on="customer_nk",
            how="left",
            suffix="_cur",
        )

        fx = self._read_bronze("fx_rates").sort("as_of_date")
        pit = pit.sort("order_date").join_asof(
            fx.rename({"from_currency": "currency_code", "as_of_date": "fx_date", "rate": "fx_to_usd"})
            .select("fx_date", "currency_code", "fx_to_usd")
            .sort("fx_date"),
            left_on="order_date",
            right_on="fx_date",
            by="currency_code",
            strategy="backward",
        )
        pit = pit.with_columns(
            pl.when(pl.col("currency_code") == "USD")
            .then(1.0)
            .otherwise(pl.col("fx_to_usd"))
            .fill_null(1.0)
            .alias("fx_to_usd"),
            (pl.col("quantity") * pl.col("unit_cost").fill_null(0.0)).alias("line_cogs"),
        ).with_columns(
            (pl.col("line_net_amount") - pl.col("line_cogs")).alias("line_gross_margin"),
            (pl.col("line_net_amount") * pl.col("fx_to_usd")).alias("line_net_amount_usd"),
        )

        # Idempotent load: delete+insert by batch_id
        existing = read_parquet(self.lake / "gold" / "fct_orders_txn.parquet")
        pit = pit.with_columns(pl.lit(self.batch_id).alias("_batch_id"))
        merged = delete_insert_by_batch(existing, pit, batch_id=self.batch_id)
        write_parquet(merged, self.lake / "gold" / "fct_orders_txn.parquet")

        snap = build_accumulating_snapshot(orders.with_columns(pl.lit(self.batch_id).alias("_batch_id")))
        existing_snap = read_parquet(self.lake / "gold" / "fct_order_accumulating.parquet")
        write_parquet(
            delete_insert_by_batch(existing_snap, snap, batch_id=self.batch_id),
            self.lake / "gold" / "fct_order_accumulating.parquet",
        )

        periodic = build_periodic_snapshot(merged, as_of=date(2026, 2, 12))
        write_parquet(periodic, self.lake / "gold" / "fct_revenue_periodic_daily.parquet")

        self.metrics["fct_orders_rows"] = merged.height
        self.metrics["accumulating_rows"] = snap.height
        self.metrics["periodic_rows"] = periodic.height
        self.metrics["net_revenue_usd"] = float(merged["line_net_amount_usd"].sum()) if merged.height else 0.0
        return dict(self.metrics)

    def _anomaly_gates(self) -> dict[str, Any]:
        fact = read_parquet(self.lake / "gold" / "fct_orders_txn.parquet")
        findings = evaluate_anomalies(fact, self.cfg.get("anomaly", {}))
        bad = [f for f in findings if not f.ok]
        payload = [{"metric": f.metric, "value": f.value, "ok": f.ok, "detail": f.detail} for f in findings]
        self.reports.mkdir(parents=True, exist_ok=True)
        (self.reports / f"anomalies_{self.batch_id}.json").write_text(
            json.dumps(payload, indent=2) + "\n", encoding="utf-8"
        )
        if bad:
            raise RuntimeError("Anomaly gate failed: " + "; ".join(f"{b.metric}={b.detail}" for b in bad))
        return {"findings": payload}
