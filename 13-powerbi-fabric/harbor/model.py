"""Build the Harbor & Co. star schema and evaluate the same measures the DAX defines.

Money is decimal cents so the checks match the semantic model to the cent.
The DAX itself lives in the TMDL files. This module is the independent check.
"""
from __future__ import annotations

import csv
import random
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

SEED = 7
START = date(2024, 1, 1)
END = date(2025, 12, 31)
DATE_TABLE_END = date(2026, 1, 5)  # wholesale ships two days after the last order

STORES = [
    {"StoreKey": 1, "Store": "Seattle Pike", "City": "Seattle", "State": "WA", "Region": "West"},
    {"StoreKey": 2, "Store": "Portland Pearl", "City": "Portland", "State": "OR", "Region": "West"},
    {"StoreKey": 3, "Store": "Austin Congress", "City": "Austin", "State": "TX", "Region": "South"},
    {"StoreKey": 4, "Store": "Denver LoHi", "City": "Denver", "State": "CO", "Region": "Mountain"},
]

PRODUCTS = [
    {"Product": "House Blend", "Category": "Coffee", "Unit Cost": "4.00", "List Price": "12.00"},
    {"Product": "Espresso Beans", "Category": "Coffee", "Unit Cost": "7.00", "List Price": "18.00"},
    {"Product": "Cold Brew", "Category": "Coffee", "Unit Cost": "1.50", "List Price": "5.00"},
    {"Product": "Loose Tea", "Category": "Coffee", "Unit Cost": "2.00", "List Price": "8.00"},
    {"Product": "Mug", "Category": "Gear", "Unit Cost": "4.00", "List Price": "14.00"},
    {"Product": "Grinder", "Category": "Gear", "Unit Cost": "40.00", "List Price": "89.00"},
    {"Product": "Kettle", "Category": "Gear", "Unit Cost": "18.00", "List Price": "45.00"},
    {"Product": "Filters", "Category": "Gear", "Unit Cost": "1.50", "List Price": "6.00"},
    {"Product": "Croissant", "Category": "Food", "Unit Cost": "1.20", "List Price": "4.50"},
    {"Product": "Cookie", "Category": "Food", "Unit Cost": "0.60", "List Price": "3.00"},
    {"Product": "Sandwich", "Category": "Food", "Unit Cost": "3.20", "List Price": "9.00"},
    {"Product": "Granola", "Category": "Food", "Unit Cost": "2.00", "List Price": "7.00"},
]

CUSTOMERS = [
    ("Ana Ruiz", "Regular"),
    ("Ben Cho", "Regular"),
    ("Cara Singh", "Regular"),
    ("Drew Patel", "Regular"),
    ("Eve Nguyen", "Regular"),
    ("Finn Adler", "Regular"),
    ("Gia Rossi", "Regular"),
    ("Hugo Berg", "Regular"),
    ("Ivy Chen", "Walk-in"),
    ("Jules Park", "Walk-in"),
    ("Kai Mendes", "Walk-in"),
    ("Lena Ortiz", "Walk-in"),
    ("Milo Grant", "Walk-in"),
    ("Noor Hassan", "Walk-in"),
    ("Omar Blake", "Walk-in"),
    ("Priya Shah", "Walk-in"),
    ("Northwind Cafe", "Wholesale"),
    ("Pike Market Cart", "Wholesale"),
    ("Capitol Grocery", "Wholesale"),
    ("LoHi Provisions", "Wholesale"),
    ("Harbor Hotels", "Wholesale"),
    ("Campus Roasters", "Wholesale"),
]

STORE_WEIGHT = {1: Decimal("1.15"), 2: Decimal("0.90"), 3: Decimal("1.00"), 4: Decimal("0.85")}
MONEY = Decimal("0.01")


def money(value: Decimal | str | int) -> Decimal:
    return Decimal(value).quantize(MONEY, rounding=ROUND_HALF_UP)


def daterange(start: date, end: date):
    day = start
    while day <= end:
        yield day
        day += timedelta(days=1)


def year_month(day: date) -> str:
    return f"{day.year:04d}-{day.month:02d}"


def season(day: date, category: str) -> Decimal:
    if category == "Coffee" and day.month in (11, 12, 1, 2):
        return Decimal("1.35")
    if category == "Gear" and day.month == 11:
        return Decimal("1.70")
    if category == "Food" and day.month in (6, 7, 8):
        return Decimal("1.15")
    return Decimal("1.00")


def build_dates() -> list[dict]:
    rows = []
    for day in daterange(START, DATE_TABLE_END):
        rows.append({
            "DateKey": int(day.strftime("%Y%m%d")),
            "Date": day.isoformat(),
            "Year": day.year,
            "Quarter": f"Q{(day.month - 1) // 3 + 1}",
            "Month Number": day.month,
            "Month Name": day.strftime("%B"),
            "Year Month": year_month(day),
            "Year Month Number": day.year * 100 + day.month,
            "Day of Week": day.strftime("%A"),
            "Weekday Number": day.weekday() + 1,
            "Day Type": "Weekend" if day.weekday() >= 5 else "Weekday",
        })
    return rows


def build_products() -> list[dict]:
    rows = []
    for key, product in enumerate(PRODUCTS, start=1):
        rows.append({
            "ProductKey": key,
            "Product": product["Product"],
            "Category": product["Category"],
            "Unit Cost": product["Unit Cost"],
            "List Price": product["List Price"],
        })
    return rows


def build_customers() -> list[dict]:
    return [
        {"CustomerKey": key, "Customer": name, "Segment": segment}
        for key, (name, segment) in enumerate(CUSTOMERS, start=1)
    ]


def _product_bias(day: date, product: dict) -> float:
    return float(season(day, product["Category"]))


def build_bronze() -> tuple[list[dict], list[dict]]:
    """Raw sales export, plus the rows the silver step must reject."""
    rng = random.Random(SEED)
    products = PRODUCTS
    kept: list[dict] = []
    order_id = 1000
    for day in daterange(START, END):
        for store in STORES:
            extra = 1 if day.year == 2025 and rng.random() < 0.35 else 0
            for _ in range(1 + rng.randrange(2) + extra):
                order_id += 1
                customer, segment = rng.choice(CUSTOMERS)
                weights = [_product_bias(day, product) for product in products]
                picks = rng.choices(products, weights=weights, k=1 + rng.randrange(3))
                # One line per product on the order.
                seen = []
                for product in picks:
                    if product["Product"] in seen:
                        continue
                    seen.append(product["Product"])
                    qty = 1 + rng.randrange(4 if segment != "Wholesale" else 12)
                    list_price = money(product["List Price"])
                    discount = money(list_price * qty * Decimal("0.10")) if rng.random() < 0.15 else money(0)
                    ship = day + timedelta(days=2 if segment == "Wholesale" else 0)
                    kept.append({
                        "order_id": order_id,
                        "order_date": day.isoformat(),
                        "ship_date": ship.isoformat(),
                        "store": store["Store"],
                        "product": product["Product"],
                        "customer": customer,
                        "segment": segment,
                        "qty": qty,
                        "unit_price": f"{list_price:.2f}",
                        "discount": f"{discount:.2f}",
                        "unit_cost": product["Unit Cost"],
                    })
    dirty = [
        {**kept[0], "qty": "", "order_id": 9},
        {**kept[1], "qty": -3, "order_id": 8},
        dict(kept[2]),  # exact duplicate of a real line
    ]
    return kept + dirty, dirty


def _index(rows: list[dict], key: str) -> dict:
    return {row[key]: row for row in rows}


def build_gold(bronze_kept_and_dirty: list[dict], products: list[dict], stores: list[dict], customers: list[dict]):
    product_by_name = _index(products, "Product")
    store_by_name = _index(stores, "Store")
    customer_by_name = _index(customers, "Customer")
    seen = set()
    quarantine = []
    silver = []
    for row in bronze_kept_and_dirty:
        reason = None
        try:
            qty = int(row["qty"])
        except (TypeError, ValueError):
            qty = None
        if qty is None or qty <= 0:
            reason = "quantity is blank or not positive"
        identity = (
            row["order_id"], row["order_date"], row["store"], row["product"],
            row["customer"], row["qty"], row["unit_price"], row["discount"],
        )
        if reason is None and identity in seen:
            reason = "duplicate line"
        if reason:
            quarantine.append({**row, "reason": reason})
            continue
        seen.add(identity)
        product = product_by_name[row["product"]]
        store = store_by_name[row["store"]]
        customer = customer_by_name[row["customer"]]
        qty = int(row["qty"])
        unit_price = money(row["unit_price"])
        discount = money(row["discount"])
        unit_cost = money(product["Unit Cost"])
        net = money(unit_price * qty - discount)
        cost = money(unit_cost * qty)
        order_day = date.fromisoformat(row["order_date"])
        silver.append({
            "OrderId": int(row["order_id"]),
            "OrderDate": row["order_date"],
            "ShipDate": row["ship_date"],
            "DateKey": int(order_day.strftime("%Y%m%d")),
            "ProductKey": product["ProductKey"],
            "StoreKey": store["StoreKey"],
            "CustomerKey": customer["CustomerKey"],
            "Quantity": qty,
            "Net Amount": f"{net:.2f}",
            "Cost Amount": f"{cost:.2f}",
            "Discount Amount": f"{discount:.2f}",
        })

    budget = []
    month_starts = []
    day = date(START.year, START.month, 1)
    while day <= END:
        month_starts.append(day)
        if day.month == 12:
            day = date(day.year + 1, 1, 1)
        else:
            day = date(day.year, day.month + 1, 1)
    for month in month_starts:
        for store in stores:
            for product in products:
                # A monthly plan. It uses store weight and season, not the actual orders,
                # so a store can beat or miss it.
                units = Decimal("22") * STORE_WEIGHT[store["StoreKey"]] * season(month, product["Category"])
                if month.year == 2025:
                    units *= Decimal("1.08")
                amount = money(units * money(product["List Price"]))
                budget.append({
                    "StoreKey": store["StoreKey"],
                    "ProductKey": product["ProductKey"],
                    "Year Month": year_month(month),
                    "Budget Amount": f"{amount:.2f}",
                })
    return silver, quarantine, budget


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def load_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def as_sales(rows: list[dict]) -> list[dict]:
    out = []
    for row in rows:
        out.append({
            **row,
            "OrderId": int(row["OrderId"]),
            "DateKey": int(row["DateKey"]),
            "ProductKey": int(row["ProductKey"]),
            "StoreKey": int(row["StoreKey"]),
            "CustomerKey": int(row["CustomerKey"]),
            "Quantity": int(row["Quantity"]),
            "Net Amount": money(row["Net Amount"]),
            "Cost Amount": money(row["Cost Amount"]),
            "OrderDate": date.fromisoformat(row["OrderDate"]),
            "ShipDate": date.fromisoformat(row["ShipDate"]),
        })
    return out


def as_budget(rows: list[dict]) -> list[dict]:
    return [{
        **row,
        "StoreKey": int(row["StoreKey"]),
        "ProductKey": int(row["ProductKey"]),
        "Budget Amount": money(row["Budget Amount"]),
    } for row in rows]


class Catalog:
    """The gold tables, indexed the way relationships index them."""

    def __init__(self, root: Path):
        gold = root / "data" / "gold"
        self.dates = load_csv(gold / "dim_date.csv")
        self.products = load_csv(gold / "dim_product.csv")
        self.stores = load_csv(gold / "dim_store.csv")
        self.customers = load_csv(gold / "dim_customer.csv")
        self.sales = as_sales(load_csv(gold / "fact_sales.csv"))
        self.budget = as_budget(load_csv(gold / "fact_budget.csv"))
        self.date_by_key = {int(row["DateKey"]): row for row in self.dates}
        self.product_by_key = {int(row["ProductKey"]): row for row in self.products}
        self.store_by_key = {int(row["StoreKey"]): row for row in self.stores}
        self.customer_by_key = {int(row["CustomerKey"]): row for row in self.customers}
        self.date_by_iso = {row["Date"]: row for row in self.dates}

    def sales_in(self, filters: dict, *, on: str = "order") -> list[dict]:
        """Apply a filter context to fact sales. `on` is order or ship."""
        rows = []
        for sale in self.sales:
            when = sale["OrderDate"] if on == "order" else sale["ShipDate"]
            day = self.date_by_iso[when.isoformat()]
            product = self.product_by_key[sale["ProductKey"]]
            store = self.store_by_key[sale["StoreKey"]]
            customer = self.customer_by_key[sale["CustomerKey"]]
            if not _match(filters, day, product, store, customer):
                continue
            rows.append(sale)
        return rows

    def budget_in(self, filters: dict) -> list[dict]:
        """Budget ignores customer filters. There is no relationship to carry them."""
        allowed_customers = filters.get("customers") or filters.get("segments")
        date_filters = {k: filters[k] for k in ("years", "year_months", "date_from", "date_to") if k in filters}
        months = None
        if date_filters:
            months = set()
            for row in self.dates:
                if _match(date_filters, row, {}, {}, {}):
                    months.add(row["Year Month"])
        rows = []
        for item in self.budget:
            if months is not None and item["Year Month"] not in months:
                continue
            product = self.product_by_key[item["ProductKey"]]
            store = self.store_by_key[item["StoreKey"]]
            if not _match(
                {k: filters[k] for k in filters if k in ("stores", "regions", "products", "categories")},
                {}, product, store, {},
            ):
                continue
            rows.append(item)
        # Touch the unused name so a customer filter is visibly discarded.
        del allowed_customers
        return rows


def _match(filters: dict, day: dict, product: dict, store: dict, customer: dict) -> bool:
    if "years" in filters and int(day["Year"]) not in filters["years"]:
        return False
    if "year_months" in filters and day["Year Month"] not in filters["year_months"]:
        return False
    if "date_from" in filters and day["Date"] < filters["date_from"]:
        return False
    if "date_to" in filters and day["Date"] > filters["date_to"]:
        return False
    if "stores" in filters and store["Store"] not in filters["stores"]:
        return False
    if "regions" in filters and store["Region"] not in filters["regions"]:
        return False
    if "products" in filters and product["Product"] not in filters["products"]:
        return False
    if "categories" in filters and product["Category"] not in filters["categories"]:
        return False
    if "customers" in filters and customer["Customer"] not in filters["customers"]:
        return False
    if "segments" in filters and customer["Segment"] not in filters["segments"]:
        return False
    return True


def _sum(rows: list[dict], column: str) -> Decimal:
    return money(sum((row[column] for row in rows), Decimal(0)))


def revenue(catalog: Catalog, filters: dict, *, on: str = "order") -> Decimal:
    return _sum(catalog.sales_in(filters, on=on), "Net Amount")


def cost(catalog: Catalog, filters: dict) -> Decimal:
    return _sum(catalog.sales_in(filters), "Cost Amount")


def margin(catalog: Catalog, filters: dict) -> Decimal:
    return money(revenue(catalog, filters) - cost(catalog, filters))


def margin_pct(catalog: Catalog, filters: dict) -> Decimal | None:
    total = revenue(catalog, filters)
    if total == 0:
        return None
    return (margin(catalog, filters) / total).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


def units(catalog: Catalog, filters: dict) -> int:
    return sum(row["Quantity"] for row in catalog.sales_in(filters))


def orders(catalog: Catalog, filters: dict) -> int:
    return len({row["OrderId"] for row in catalog.sales_in(filters)})


def average_order_value(catalog: Catalog, filters: dict) -> Decimal | None:
    count = orders(catalog, filters)
    if count == 0:
        return None
    return money(revenue(catalog, filters) / count)


def _context_end(filters: dict) -> date:
    if "date_to" in filters:
        return date.fromisoformat(filters["date_to"])
    if "year_months" in filters:
        year, month = map(int, sorted(filters["year_months"])[-1].split("-"))
        if month == 12:
            return date(year, 12, 31)
        return date(year, month + 1, 1) - timedelta(days=1)
    if "years" in filters:
        return date(max(filters["years"]), 12, 31)
    return END


def _without_dates(filters: dict) -> dict:
    return {k: v for k, v in filters.items() if k not in ("years", "year_months", "date_from", "date_to")}


def revenue_ytd(catalog: Catalog, filters: dict) -> Decimal:
    end = _context_end(filters)
    narrowed = {**_without_dates(filters), "date_from": date(end.year, 1, 1).isoformat(), "date_to": end.isoformat()}
    return revenue(catalog, narrowed)


def revenue_py(catalog: Catalog, filters: dict) -> Decimal:
    """SAMEPERIODLASTYEAR for a year, a month, or an explicit date range."""
    shifted = _without_dates(filters)
    if "date_from" in filters or "date_to" in filters:
        start = date.fromisoformat(filters.get("date_from", START.isoformat()))
        end = date.fromisoformat(filters.get("date_to", END.isoformat()))
        shifted["date_from"] = start.replace(year=start.year - 1).isoformat()
        shifted["date_to"] = end.replace(year=end.year - 1).isoformat()
    elif "year_months" in filters:
        shifted["year_months"] = tuple(
            f"{int(item[:4]) - 1}{item[4:]}" for item in filters["year_months"]
        )
    elif "years" in filters:
        shifted["years"] = tuple(year - 1 for year in filters["years"])
    else:
        shifted["date_from"] = START.replace(year=START.year - 1).isoformat()
        shifted["date_to"] = END.replace(year=END.year - 1).isoformat()
    return revenue(catalog, shifted)


def revenue_yoy(catalog: Catalog, filters: dict) -> Decimal:
    return money(revenue(catalog, filters) - revenue_py(catalog, filters))


def revenue_yoy_pct(catalog: Catalog, filters: dict) -> Decimal | None:
    prior = revenue_py(catalog, filters)
    if prior == 0:
        return None
    return (revenue_yoy(catalog, filters) / prior).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


def budget(catalog: Catalog, filters: dict) -> Decimal:
    return _sum(catalog.budget_in(filters), "Budget Amount")


def share_of_category(catalog: Catalog, filters: dict) -> Decimal | None:
    """ALLEXCEPT(DimProduct, DimProduct[Category]): drop the product filter, keep category."""
    total_filters = {k: v for k, v in filters.items() if k != "products"}
    total = revenue(catalog, total_filters)
    if total == 0:
        return None
    return (revenue(catalog, filters) / total).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


def generate(root: Path) -> dict:
    products = build_products()
    stores = list(STORES)
    customers = build_customers()
    bronze, planted = build_bronze()
    sales, quarantine, budget_rows = build_gold(bronze, products, stores, customers)
    dates = build_dates()
    data = root / "data"
    write_csv(data / "bronze" / "sales_export.csv", bronze)
    write_csv(data / "quarantine" / "rejected_sales.csv", quarantine)
    write_csv(data / "gold" / "dim_date.csv", dates)
    write_csv(data / "gold" / "dim_product.csv", products)
    write_csv(data / "gold" / "dim_store.csv", stores)
    write_csv(data / "gold" / "dim_customer.csv", customers)
    # The Fabric notebook joins bronze sales to these lists. Keys match the gold dims.
    write_csv(data / "reference" / "products.csv", products)
    write_csv(data / "reference" / "stores.csv", stores)
    write_csv(data / "reference" / "customers.csv", customers)
    write_csv(data / "gold" / "fact_sales.csv", sales)
    write_csv(data / "gold" / "fact_budget.csv", budget_rows)
    return {
        "bronze_rows": len(bronze),
        "sales_rows": len(sales),
        "quarantine_rows": len(quarantine),
        "planted_bad_rows": len(planted),
        "budget_rows": len(budget_rows),
        "date_rows": len(dates),
        "products": len(products),
        "stores": len(stores),
        "customers": len(customers),
    }


def lesson_numbers(root: Path) -> dict:
    """The slices the README and the walkthrough quote. Rounded for display."""
    catalog = Catalog(root)
    company_2024 = {"years": (2024,)}
    company_2025 = {"years": (2025,)}
    seattle_march = {"stores": ("Seattle Pike",), "year_months": ("2025-03",)}
    west = {"regions": ("West",), "years": (2025,)}
    house = {"products": ("House Blend",), "categories": ("Coffee",), "years": (2025,)}
    wholesale_march = {"segments": ("Wholesale",), "year_months": ("2025-03",)}
    customer = {"customers": ("Harbor Hotels",), "year_months": ("2025-03",)}
    month_only = {"year_months": ("2025-03",)}

    def pack(filters: dict) -> dict:
        return {
            "revenue": str(revenue(catalog, filters)),
            "cost": str(cost(catalog, filters)),
            "margin": str(margin(catalog, filters)),
            "margin_pct": _pct(margin_pct(catalog, filters)),
            "units": units(catalog, filters),
            "orders": orders(catalog, filters),
            "average_order_value": _money(average_order_value(catalog, filters)),
            "revenue_ytd": str(revenue_ytd(catalog, filters)),
            "revenue_py": str(revenue_py(catalog, filters)),
            "revenue_yoy": str(revenue_yoy(catalog, filters)),
            "revenue_yoy_pct": _pct(revenue_yoy_pct(catalog, filters)),
            "budget": str(budget(catalog, filters)),
            "revenue_by_ship_date": str(revenue(catalog, filters, on="ship")),
        }

    shares = []
    coffee_products = [row["Product"] for row in catalog.products if row["Category"] == "Coffee"]
    for name in coffee_products:
        filters = {"products": (name,), "categories": ("Coffee",), "years": (2025,)}
        shares.append({"product": name, "share": _pct(share_of_category(catalog, filters)), "revenue": str(revenue(catalog, filters))})

    return {
        "counts": {
            "sales_rows": len(catalog.sales),
            "dates": len(catalog.dates),
            "budget_rows": len(catalog.budget),
        },
        "company_2024": pack(company_2024),
        "company_2025": pack(company_2025),
        "seattle_march_2025": pack(seattle_march),
        "west_2025": pack(west),
        "house_blend_2025": {**pack(house), "share_of_coffee": _pct(share_of_category(catalog, house))},
        "coffee_shares_2025": shares,
        "wholesale_march_2025": pack(wholesale_march),
        "harbor_hotels_march_2025": pack(customer),
        "march_2025_budget_ignores_customer": {
            "budget_all_customers": str(budget(catalog, month_only)),
            "budget_one_customer": str(budget(catalog, customer)),
            "revenue_all_customers": str(revenue(catalog, month_only)),
            "revenue_one_customer": str(revenue(catalog, customer)),
        },
    }


def _pct(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return str((value * 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _money(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return str(value)


def grouped(catalog: Catalog, filters: dict, column: str, lookup) -> list[tuple[str, Decimal]]:
    totals = defaultdict(lambda: Decimal(0))
    for sale in catalog.sales_in(filters):
        totals[lookup(sale)] += sale["Net Amount"]
    return sorted(((name, money(amount)) for name, amount in totals.items()), key=lambda item: item[0])
