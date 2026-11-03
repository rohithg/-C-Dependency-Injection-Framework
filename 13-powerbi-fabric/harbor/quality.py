"""Acceptance checks for the Harbor gold tables.

These are the tests a senior analytics engineer leaves behind so the next
refresh cannot silently change a certified number. `check` returns a list of
problems. An empty list means the batch is safe to publish.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from harbor.model import (
    BATCH_ID,
    OPEN_END,
    START,
    STORE_WEIGHT,
    Catalog,
    inventory_sum_across_dates,
    inventory_units,
    load_csv,
    money,
    revenue,
    season,
    weeks_of_supply,
)


def check(root: Path) -> list[str]:
    problems: list[str] = []
    catalog = Catalog(root)

    def fail(message: str) -> None:
        problems.append(message)

    _keys(catalog, fail)
    _price_history(catalog, fail)
    _sales_match_price_version(catalog, fail)
    _inventory(catalog, fail)
    _budget_uses_launch_price(catalog, fail)
    _batch(root, catalog, fail)
    _reconcile_bronze(root, catalog, fail)
    return problems


def _keys(catalog: Catalog, fail) -> None:
    for name, rows, column in (
        ("date", catalog.dates, "DateKey"),
        ("product", catalog.products, "ProductKey"),
        ("store", catalog.stores, "StoreKey"),
        ("customer", catalog.customers, "CustomerKey"),
        ("price", catalog.prices, "ProductPriceKey"),
    ):
        values = [row[column] for row in rows]
        if len(values) != len(set(values)):
            fail(f"{name} key {column} is not unique")
    days = [date.fromisoformat(row["Date"]) for row in catalog.dates]
    if days != [days[0] + timedelta(days=index) for index in range(len(days))]:
        fail("date table has a gap or is out of order")
    sale_grain = {(row["OrderId"], row["ProductKey"]) for row in catalog.sales}
    if len(sale_grain) != len(catalog.sales):
        fail("fact sales grain is not one row per order and product")


def _price_history(catalog: Catalog, fail) -> None:
    by_product: dict[str, list[dict]] = defaultdict(list)
    for row in catalog.prices:
        by_product[row["Product"]].append(row)
    if len(by_product) != len(catalog.products):
        fail("a product is missing from price history, or history names an unknown product")
    current_price = {row["Product"]: row["List Price"] for row in catalog.products}
    for product, rows in by_product.items():
        ordered = sorted(rows, key=lambda item: item["Valid From"])
        currents = [row for row in ordered if row["Is Current"] == "true"]
        if len(currents) != 1:
            fail(f"{product} should have exactly one current price")
            continue
        if currents[0] is not ordered[-1]:
            fail(f"{product} current flag is not on the latest row")
        if current_price.get(product) != currents[0]["List Price"]:
            fail(f"{product} dimension list price is not the current version")
        if ordered[0]["Valid From"] != START.isoformat():
            fail(f"{product} history does not start on the launch date")
        if ordered[-1]["Valid To"] != OPEN_END.isoformat():
            fail(f"{product} history does not stay open")
        for earlier, later in zip(ordered, ordered[1:]):
            end = date.fromisoformat(earlier["Valid To"])
            start = date.fromisoformat(later["Valid From"])
            if end >= start:
                fail(f"{product} price ranges overlap")
            elif end + timedelta(days=1) != start:
                fail(f"{product} price ranges have a gap")


def _sales_match_price_version(catalog: Catalog, fail) -> None:
    by_key = {int(row["ProductPriceKey"]): row for row in catalog.prices}
    for sale in catalog.sales:
        version = by_key.get(sale["ProductPriceKey"])
        if version is None:
            fail(f"order {sale['OrderId']} points at a missing price key")
            return
        if int(version["ProductKey"]) != sale["ProductKey"]:
            fail(f"order {sale['OrderId']} price key belongs to a different product")
            return
        start = date.fromisoformat(version["Valid From"])
        end = date.fromisoformat(version["Valid To"])
        if not start <= sale["OrderDate"] <= end:
            fail(f"order {sale['OrderId']} on {sale['OrderDate']} is outside its price version")
            return


def _inventory(catalog: Catalog, fail) -> None:
    grain = {(row["DateKey"], row["StoreKey"], row["ProductKey"]) for row in catalog.inventory}
    if len(grain) != len(catalog.inventory):
        fail("inventory grain is not one row per date, store, and product")
    if len(catalog.inventory) != 24 * 4 * 12:
        fail("inventory is not one snapshot per month, store, and product")
    for row in catalog.inventory:
        if row["DateKey"] not in catalog.date_by_key:
            fail("inventory date key is missing from the date table")
            return
        if row["StoreKey"] not in catalog.store_by_key or row["ProductKey"] not in catalog.product_by_key:
            fail("inventory store or product key is missing")
            return
        snapshot = row["Date"]
        if snapshot.month == 12:
            next_month = date(snapshot.year + 1, 1, 1)
        else:
            next_month = date(snapshot.year, snapshot.month + 1, 1)
        if snapshot != next_month - timedelta(days=1):
            fail("inventory snapshot is not a month end")
            return
    year = {"years": (2025,)}
    month = {"year_months": ("2025-03",)}
    if not inventory_units(catalog, year) < inventory_sum_across_dates(catalog, year):
        fail("a year of inventory collapsed to the same number as a sum across dates")
    if inventory_units(catalog, month) != inventory_sum_across_dates(catalog, month):
        fail("a single month of inventory should have only one snapshot")
    march_rows = [row for row in catalog.inventory if row["Date"] == date(2025, 3, 31)]
    if inventory_units(catalog, month) != sum(row["Units On Hand"] for row in march_rows):
        fail("March inventory is not the 31 March snapshot")
    hotels = {"customers": ("Harbor Hotels",), "year_months": ("2025-03",)}
    if weeks_of_supply(catalog, hotels) != weeks_of_supply(catalog, month):
        fail("a customer filter changed weeks of supply")
    if revenue(catalog, hotels) >= revenue(catalog, month):
        fail("the customer filter did not reduce revenue, so the supply check is vacuous")


def _budget_uses_launch_price(catalog: Catalog, fail) -> None:
    house = next(row for row in catalog.products if row["Product"] == "House Blend")
    # March is outside the winter coffee season, so the season factor is 1.
    units = Decimal("22") * STORE_WEIGHT[1] * season(date(2025, 3, 1), "Coffee") * Decimal("1.08")
    launch = money(units * Decimal("12.00"))
    raised = money(units * Decimal("13.00"))
    row = next(
        item for item in catalog.budget
        if item["Year Month"] == "2025-03"
        and item["StoreKey"] == 1
        and item["ProductKey"] == int(house["ProductKey"])
    )
    if row["Budget Amount"] != launch:
        fail("House Blend's March plan does not use the launch price")
    if row["Budget Amount"] == raised:
        fail("House Blend's March plan was rewritten at the new price")


def _batch(root: Path, catalog: Catalog, fail) -> None:
    del root
    for name, rows in (
        ("sales", catalog.sales),
        ("budget", catalog.budget),
        ("inventory", catalog.inventory),
    ):
        found = {row["Batch Id"] for row in rows}
        if found != {BATCH_ID}:
            fail(f"{name} batch id is {sorted(found)}, expected {BATCH_ID}")


def _reconcile_bronze(root: Path, catalog: Catalog, fail) -> None:
    bronze = load_csv(root / "data" / "bronze" / "sales_export.csv")
    seen = set()
    kept = Decimal(0)
    rejected = 0
    for row in bronze:
        try:
            qty = int(row["qty"])
        except (TypeError, ValueError):
            qty = None
        identity = (
            row["order_id"], row["order_date"], row["store"], row["product"],
            row["customer"], row["qty"], row["unit_price"], row["discount"],
        )
        if qty is None or qty <= 0 or identity in seen:
            rejected += 1
            continue
        seen.add(identity)
        kept += money(row["unit_price"]) * qty - money(row["discount"])
    gold = sum((row["Net Amount"] for row in catalog.sales), Decimal(0))
    if money(kept) != money(gold):
        fail(f"bronze kept net {money(kept)} does not equal fact net {money(gold)}")
    quarantine = load_csv(root / "data" / "quarantine" / "rejected_sales.csv")
    if len(quarantine) != rejected:
        fail(f"quarantine has {len(quarantine)} rows and the bronze recount rejected {rejected}")
    reasons = {row["reason"] for row in quarantine}
    if "quantity is blank or not positive" not in reasons or "duplicate line" not in reasons:
        fail(f"quarantine reasons are incomplete: {sorted(reasons)}")


def main() -> None:
    import sys

    root = Path(__file__).resolve().parents[1]
    problems = check(root)
    if problems:
        for problem in problems:
            print(problem)
        sys.exit(1)
    print(f"batch {BATCH_ID} passed {len(problems) or 'all'} acceptance checks")


if __name__ == "__main__":
    main()
