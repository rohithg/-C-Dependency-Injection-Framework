from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

import polars as pl

from complex_etl.bronze.land import land_bronze, read_bronze_entity
from complex_etl.config_loader import PipelineConfig
from complex_etl.extract.sources import (
    fetch_fx_api_paginated,
    read_cdc_log,
    read_csv_source,
    read_json_source,
)
from complex_etl.gold.marts import (
    build_daily_region_agg,
    build_fct_orders,
    build_monthly_category_agg,
    build_order_product_bridge,
)
from complex_etl.load.lake import read_table, write_layer_table
from complex_etl.orchestrator.dag import DagRunner, Task
from complex_etl.quality.gates import evaluate_gates
from complex_etl.silver.clean import (
    apply_cdc_to_orders,
    clean_customers,
    clean_order_lines,
    clean_orders,
    clean_products,
    write_quarantine,
)
from complex_etl.silver.scd2 import apply_scd2
from complex_etl.state.lineage import LineageGraph
from complex_etl.state.watermarks import WatermarkStore


def _current_dim(scd: pl.DataFrame) -> pl.DataFrame:
    if scd.is_empty():
        return scd
    return scd.filter(pl.col("is_current"))


def run_complex_pipeline(cfg: PipelineConfig, apply_day2_customers: bool = True) -> dict[str, Any]:
    lineage = LineageGraph()
    watermarks = WatermarkStore(cfg.state_dir / "watermarks.json")
    meta: dict[str, Any] = {"tables": {}, "quarantine": {}, "dq": {}}

    def t_extract_land() -> dict[str, Any]:
        customers = read_csv_source(cfg.raw_dir / "customers.csv")
        if apply_day2_customers and (cfg.raw_dir / "customers_day2.csv").exists():
            # Simulate late full extract for SCD2 demo: land day2 as latest bronze batch
            customers = read_csv_source(cfg.raw_dir / "customers_day2.csv")
        products = read_csv_source(cfg.raw_dir / "products.csv")
        orders = read_csv_source(cfg.raw_dir / "orders.csv")
        lines = read_csv_source(cfg.raw_dir / "order_lines.csv")
        promos = read_json_source(cfg.raw_dir / "order_promotions.json")
        fx = fetch_fx_api_paginated(cfg.api_cache_dir, pages=2)
        cdc_since = watermarks.get("orders_cdc", cfg.settings.get("watermarks", {}).get("orders_cdc", "1970-01-01T00:00:00Z"))
        cdc = read_cdc_log(cfg.cdc_dir / "orders_cdc.jsonl", since_iso=cdc_since)

        paths = {
            "customers": land_bronze(customers, "customers", cfg.bronze_dir, cfg.run_id, "erp_csv"),
            "products": land_bronze(products, "products", cfg.bronze_dir, cfg.run_id, "erp_csv"),
            "orders": land_bronze(orders, "orders", cfg.bronze_dir, cfg.run_id, "erp_csv"),
            "order_lines": land_bronze(lines, "order_lines", cfg.bronze_dir, cfg.run_id, "erp_csv"),
            "promotions": land_bronze(promos, "promotions", cfg.bronze_dir, cfg.run_id, "promo_json"),
            "fx_rates": land_bronze(fx, "fx_rates", cfg.bronze_dir, cfg.run_id, "fx_api"),
            "orders_cdc": land_bronze(cdc, "orders_cdc", cfg.bronze_dir, cfg.run_id, "cdc_log"),
        }
        for src, tgt in [
            ("erp_csv.customers", "bronze.customers"),
            ("erp_csv.products", "bronze.products"),
            ("erp_csv.orders", "bronze.orders"),
            ("erp_csv.order_lines", "bronze.order_lines"),
            ("promo_json.order_promotions", "bronze.promotions"),
            ("fx_api.rates", "bronze.fx_rates"),
            ("cdc.orders", "bronze.orders_cdc"),
        ]:
            lineage.add(src, tgt, transform="land_bronze")
        if not cdc.is_empty():
            watermarks.set("orders_cdc", str(cdc["commit_ts"].max()))
        watermarks.bump_now("fx_api")
        watermarks.save()
        return {"bronze_paths": {k: str(v) for k, v in paths.items()}, "cdc_rows": cdc.height}

    def t_silver_clean() -> dict[str, Any]:
        customers = read_bronze_entity(cfg.bronze_dir, "customers", cfg.run_id)
        products = read_bronze_entity(cfg.bronze_dir, "products", cfg.run_id)
        orders_bronze = read_bronze_entity(cfg.bronze_dir, "orders", cfg.run_id)
        lines = read_bronze_entity(cfg.bronze_dir, "order_lines", cfg.run_id)
        cdc = read_bronze_entity(cfg.bronze_dir, "orders_cdc", cfg.run_id)

        # Apply CDC on bronze-shaped orders first (customer_id grain)
        order_cols = [
            "order_id",
            "customer_id",
            "order_date",
            "order_status",
            "order_channel",
            "currency_code",
        ]
        orders_src = orders_bronze.select([c for c in order_cols if c in orders_bronze.columns])
        if not cdc.is_empty():
            orders_src = apply_cdc_to_orders(orders_src, cdc)

        cust_g, cust_b = clean_customers(customers)
        prod_g, prod_b = clean_products(products)
        # cast dates back to string if already date from prior runs
        if "order_date" in orders_src.columns and orders_src.schema["order_date"] != pl.Utf8:
            orders_src = orders_src.with_columns(pl.col("order_date").cast(pl.Utf8))
        ord_g, ord_b = clean_orders(orders_src)
        line_g, line_b = clean_order_lines(lines)

        q = {}
        for name, bad in [
            ("customers", cust_b),
            ("products", prod_b),
            ("orders", ord_b),
            ("order_lines", line_b),
        ]:
            p = write_quarantine(
                bad, cfg.quarantine_dir / cfg.run_id / f"{name}.parquet", f"silver_clean:{name}"
            )
            if p:
                q[name] = str(p)

        write_layer_table(cust_g, cfg.silver_dir / "clean", "customers")
        write_layer_table(prod_g, cfg.silver_dir / "clean", "products")
        write_layer_table(ord_g, cfg.silver_dir / "clean", "orders")
        write_layer_table(line_g, cfg.silver_dir / "clean", "order_lines")
        lineage.add("bronze.customers", "silver.customers", transform="clean+dedupe")
        lineage.add("bronze.products", "silver.products", transform="clean+dedupe")
        lineage.add("bronze.orders+cdc", "silver.orders", transform="cdc_then_clean")
        lineage.add("bronze.order_lines", "silver.order_lines", transform="clean+dedupe")
        meta["quarantine"] = q
        return {
            "customers": cust_g.height,
            "products": prod_g.height,
            "orders": ord_g.height,
            "order_lines": line_g.height,
            "quarantine": q,
        }

    def t_silver_scd2() -> dict[str, Any]:
        from complex_etl.extract.sources import read_csv_source
        from complex_etl.silver.clean import clean_customers

        # Demonstrate SCD2 by applying day1 snapshot then day2 snapshot in-order
        day1_raw = cfg.raw_dir / "customers.csv"
        day2_raw = cfg.raw_dir / "customers_day2.csv"
        day1, _ = clean_customers(read_csv_source(day1_raw))
        existing_c = read_table(cfg.silver_dir / "scd2" / "dim_customer_scd2.parquet")
        scd_c = apply_scd2(
            existing_c,
            day1.select(
                "customer_nk",
                "customer_name",
                "region_name",
                "country_code",
                "segment",
                "credit_tier",
            ),
            natural_key="customer_nk",
            track_columns=["customer_name", "region_name", "country_code", "segment", "credit_tier"],
            as_of=date(2026, 1, 1),
        )
        if apply_day2_customers and day2_raw.exists():
            day2, _ = clean_customers(read_csv_source(day2_raw))
            scd_c = apply_scd2(
                scd_c,
                day2.select(
                    "customer_nk",
                    "customer_name",
                    "region_name",
                    "country_code",
                    "segment",
                    "credit_tier",
                ),
                natural_key="customer_nk",
                track_columns=[
                    "customer_name",
                    "region_name",
                    "country_code",
                    "segment",
                    "credit_tier",
                ],
                as_of=date(2026, 2, 12),
            )

        prod = read_table(cfg.silver_dir / "clean" / "products.parquet")
        existing_p = read_table(cfg.silver_dir / "scd2" / "dim_product_scd2.parquet")
        scd_p = apply_scd2(
            existing_p,
            prod.select(
                "product_nk",
                "product_name",
                "product_category",
                "brand",
                "unit_cost",
                "is_active",
            ),
            natural_key="product_nk",
            track_columns=["product_name", "product_category", "brand", "unit_cost", "is_active"],
            as_of=date(2026, 2, 12),
        )
        write_layer_table(scd_c, cfg.silver_dir / "scd2", "dim_customer_scd2")
        write_layer_table(scd_p, cfg.silver_dir / "scd2", "dim_product_scd2")
        write_layer_table(_current_dim(scd_c), cfg.silver_dir / "scd2", "dim_customer_current")
        write_layer_table(_current_dim(scd_p), cfg.silver_dir / "scd2", "dim_product_current")
        lineage.add("silver.customers.day1+day2", "silver.dim_customer_scd2", transform="scd2")
        lineage.add("silver.products", "silver.dim_product_scd2", transform="scd2")
        return {
            "customer_versions": scd_c.height,
            "customer_current": _current_dim(scd_c).height,
            "product_versions": scd_p.height,
            "product_current": _current_dim(scd_p).height,
            "customer_changed_versions": scd_c.filter(~pl.col("is_current")).height,
        }

    def t_gold_marts() -> dict[str, Any]:
        lines = read_table(cfg.silver_dir / "clean" / "order_lines.parquet")
        orders = read_table(cfg.silver_dir / "clean" / "orders.parquet")
        cust = read_table(cfg.silver_dir / "scd2" / "dim_customer_current.parquet")
        prod = read_table(cfg.silver_dir / "scd2" / "dim_product_current.parquet")
        fx = read_bronze_entity(cfg.bronze_dir, "fx_rates", cfg.run_id)
        promos = read_bronze_entity(cfg.bronze_dir, "promotions", cfg.run_id)

        # Ensure customer_nk on lines via orders already; lines have product_nk
        if "customer_nk" not in lines.columns:
            lines = lines.join(orders.select("order_id", "customer_nk"), on="order_id", how="left")

        fact = build_fct_orders(lines, orders, cust, prod, fx)
        bridge = build_order_product_bridge(fact)
        daily = build_daily_region_agg(fact)
        monthly = build_monthly_category_agg(fact)

        # promotion bridge grain
        promo_bridge = pl.DataFrame()
        if not promos.is_empty() and not fact.is_empty():
            promo_bridge = promos.join(fact.select("order_id").unique(), on="order_id", how="inner")

        write_layer_table(fact, cfg.gold_dir, "fct_orders")
        write_layer_table(bridge, cfg.gold_dir, "bridge_order_product")
        write_layer_table(daily, cfg.gold_dir, "gold_revenue_daily_region")
        write_layer_table(monthly, cfg.gold_dir, "gold_revenue_monthly_category")
        write_layer_table(promo_bridge, cfg.gold_dir, "bridge_order_promo")
        write_layer_table(cust, cfg.gold_dir, "dim_customer_current")
        write_layer_table(prod, cfg.gold_dir, "dim_product_current")

        lineage.add("silver.*", "gold.fct_orders", transform="enrich+fx")
        lineage.add("gold.fct_orders", "gold.gold_revenue_daily_region", transform="aggregate")
        lineage.add("gold.fct_orders", "gold.gold_revenue_monthly_category", transform="aggregate")
        meta["tables"] = {
            "fct_orders": fact.height,
            "daily_region": daily.height,
            "monthly_category": monthly.height,
            "promo_bridge": promo_bridge.height,
        }
        return meta["tables"]

    def t_dq_gates() -> dict[str, Any]:
        tables = {
            "fct_orders": read_table(cfg.gold_dir / "fct_orders.parquet"),
            "dim_customer_scd2": read_table(cfg.silver_dir / "scd2" / "dim_customer_scd2.parquet"),
            "dim_customer_current": read_table(cfg.gold_dir / "dim_customer_current.parquet"),
            "dim_product_current": read_table(cfg.gold_dir / "dim_product_current.parquet"),
        }
        report = evaluate_gates(tables, cfg.settings.get("dq", {}))
        # Quarantine orphan fact rows if referential failed
        fact = tables["fct_orders"]
        if not fact.is_empty():
            orphans = fact.filter(pl.col("product_sk").is_null() | pl.col("customer_sk").is_null())
            if not orphans.is_empty():
                write_quarantine(
                    orphans,
                    cfg.quarantine_dir / cfg.run_id / "fct_orders_orphans.parquet",
                    "dq:referential",
                )
                clean_fact = fact.join(orphans.select("order_line_id"), on="order_line_id", how="anti")
                write_layer_table(clean_fact, cfg.gold_dir, "fct_orders")
                # rebuild aggs from clean fact
                write_layer_table(build_daily_region_agg(clean_fact), cfg.gold_dir, "gold_revenue_daily_region")
                write_layer_table(
                    build_monthly_category_agg(clean_fact), cfg.gold_dir, "gold_revenue_monthly_category"
                )
                # re-eval on cleaned
                tables["fct_orders"] = clean_fact
                report = evaluate_gates(tables, cfg.settings.get("dq", {}))

        payload = [
            {
                "table": r.table,
                "rule": r.rule,
                "severity": r.severity,
                "passed": r.passed,
                "detail": r.detail,
                "bad_rows": r.bad_rows,
            }
            for r in report.results
        ]
        cfg.report_dir.mkdir(parents=True, exist_ok=True)
        dq_path = cfg.report_dir / f"dq_{cfg.run_id}.json"
        dq_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        meta["dq"] = {"path": str(dq_path), "errors": len(report.errors), "warnings": len(report.warnings)}
        if cfg.fail_on_error_gate and report.errors:
            details = "; ".join(f"{e.table}:{e.rule}:{e.detail}" for e in report.errors)
            raise RuntimeError(f"DQ error gate failed: {details}")
        return meta["dq"]

    def t_report() -> dict[str, Any]:
        lineage_path = lineage.save(cfg.report_dir / f"lineage_{cfg.run_id}.json")
        summary = {
            "run_id": cfg.run_id,
            "tables": meta.get("tables", {}),
            "quarantine": meta.get("quarantine", {}),
            "dq": meta.get("dq", {}),
            "lineage": str(lineage_path),
            "gold_dir": str(cfg.gold_dir),
        }
        path = cfg.report_dir / f"run_{cfg.run_id}.json"
        path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        # also write latest pointer
        (cfg.report_dir / "latest_run.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        return summary

    tasks = [
        Task("extract_land_bronze", t_extract_land, retries=cfg.max_retries),
        Task("silver_clean_cdc", t_silver_clean, depends_on=["extract_land_bronze"], retries=cfg.max_retries),
        Task("silver_scd2", t_silver_scd2, depends_on=["silver_clean_cdc"], retries=cfg.max_retries),
        Task("gold_marts", t_gold_marts, depends_on=["silver_scd2"], retries=cfg.max_retries),
        Task("dq_gates", t_dq_gates, depends_on=["gold_marts"], retries=0),
        Task("emit_report", t_report, depends_on=["dq_gates"], retries=0),
    ]
    results = DagRunner(tasks).run()
    return {
        "run_id": cfg.run_id,
        "task_results": {
            k: {
                "ok": v.ok,
                "attempts": v.attempts,
                "duration_ms": round(v.duration_ms, 2),
                "meta": v.meta,
            }
            for k, v in results.items()
        },
        "report": results["emit_report"].meta,
    }
