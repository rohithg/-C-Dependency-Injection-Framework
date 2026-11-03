"""The DAX in the semantic model, checked against the gold tables."""
from __future__ import annotations

import unittest
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from harbor.model import (
    Catalog,
    budget,
    inventory_sum_across_dates,
    inventory_units,
    price_lift,
    revenue,
    revenue_py,
    revenue_ytd,
    weekly_units,
    weeks_of_supply,
)
from harbor.quality import check

ROOT = Path(__file__).resolve().parents[1]


class MeasureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = Catalog(ROOT)

    def test_date_table_has_no_gaps(self):
        days = [date.fromisoformat(row["Date"]) for row in self.catalog.dates]
        self.assertEqual(days, [days[0] + timedelta(days=i) for i in range(len(days))])
        self.assertEqual(days[0], date(2024, 1, 1))
        self.assertGreaterEqual(days[-1], date(2026, 1, 2))

    def test_every_fact_key_exists(self):
        for sale in self.catalog.sales:
            self.assertIn(sale["DateKey"], self.catalog.date_by_key)
            self.assertIn(sale["ProductKey"], self.catalog.product_by_key)
            self.assertIn(sale["StoreKey"], self.catalog.store_by_key)
            self.assertIn(sale["CustomerKey"], self.catalog.customer_by_key)
            self.assertIn(sale["ShipDate"].isoformat(), self.catalog.date_by_iso)

    def test_revenue_is_the_sum_of_line_net_amount(self):
        filters = {"years": (2025,)}
        expected = sum((row["Net Amount"] for row in self.catalog.sales if row["OrderDate"].year == 2025), Decimal(0))
        self.assertEqual(revenue(self.catalog, filters), expected.quantize(Decimal("0.01")))

    def test_ytd_through_march_is_the_first_quarter(self):
        march = {"year_months": ("2025-03",)}
        quarter = {"date_from": "2025-01-01", "date_to": "2025-03-31"}
        self.assertEqual(revenue_ytd(self.catalog, march), revenue(self.catalog, quarter))
        self.assertGreater(revenue_ytd(self.catalog, march), revenue(self.catalog, march))

    def test_prior_year_is_the_same_month_last_year(self):
        march_2025 = {"year_months": ("2025-03",)}
        march_2024 = {"year_months": ("2024-03",)}
        self.assertEqual(revenue_py(self.catalog, march_2025), revenue(self.catalog, march_2024))

    def test_ship_date_is_a_different_number_for_wholesale(self):
        filters = {"segments": ("Wholesale",), "year_months": ("2025-03",)}
        self.assertNotEqual(revenue(self.catalog, filters), revenue(self.catalog, filters, on="ship"))

    def test_customer_filter_does_not_reach_budget(self):
        month = {"year_months": ("2025-03",)}
        one = {"customers": ("Harbor Hotels",), "year_months": ("2025-03",)}
        self.assertEqual(budget(self.catalog, month), budget(self.catalog, one))
        self.assertLess(revenue(self.catalog, one), revenue(self.catalog, month))

    def test_store_filter_does_reach_budget(self):
        month = {"year_months": ("2025-03",)}
        seattle = {"stores": ("Seattle Pike",), "year_months": ("2025-03",)}
        self.assertLess(budget(self.catalog, seattle), budget(self.catalog, month))

    def test_product_shares_of_a_category_add_up(self):
        coffee = [row for row in self.catalog.products if row["Category"] == "Coffee"]
        total = revenue(self.catalog, {"categories": ("Coffee",), "years": (2025,)})
        parts = sum(
            (revenue(self.catalog, {"products": (row["Product"],), "years": (2025,)}) for row in coffee),
            Decimal(0),
        )
        self.assertEqual(parts, total)

    def test_quarantine_kept_the_bad_bronze_rows(self):
        rejected = (ROOT / "data" / "quarantine" / "rejected_sales.csv").read_text(encoding="utf-8")
        self.assertIn("quantity is blank or not positive", rejected)
        self.assertIn("duplicate line", rejected)

    def test_budget_grain_is_month_store_product(self):
        keys = {(row["Year Month"], row["StoreKey"], row["ProductKey"]) for row in self.catalog.budget}
        self.assertEqual(len(keys), len(self.catalog.budget))
        self.assertEqual(len(self.catalog.budget), 24 * 4 * 12)

    def test_price_history_and_bronze_reconcile(self):
        self.assertEqual(check(ROOT), [])

    def test_each_sale_uses_the_price_in_force_that_day(self):
        by_key = {int(row["ProductPriceKey"]): row for row in self.catalog.prices}
        house_2024 = [
            sale for sale in self.catalog.sales
            if self.catalog.product_by_key[sale["ProductKey"]]["Product"] == "House Blend"
            and sale["OrderDate"].year == 2024
        ]
        house_after = [
            sale for sale in self.catalog.sales
            if self.catalog.product_by_key[sale["ProductKey"]]["Product"] == "House Blend"
            and sale["OrderDate"] >= date(2025, 3, 1)
        ]
        self.assertTrue(house_2024 and house_after)
        self.assertTrue(all(by_key[sale["ProductPriceKey"]]["List Price"] == "12.00" for sale in house_2024))
        self.assertTrue(all(by_key[sale["ProductPriceKey"]]["List Price"] == "13.00" for sale in house_after))
        current = {row["Product"]: row["List Price"] for row in self.catalog.products}
        self.assertEqual(current["House Blend"], "13.00")
        self.assertEqual(current["Grinder"], "99.00")

    def test_price_increase_is_separated_from_selling_more(self):
        lift = price_lift(self.catalog, {"years": (2025,)})
        self.assertEqual(lift["House Blend"], Decimal("1261.20"))
        self.assertEqual(lift["Grinder"], Decimal("7761.00"))
        self.assertEqual(lift["All"], Decimal("9022.20"))
        # 2024 has no price change, so the same units at the launch price match the fact.
        self.assertEqual(price_lift(self.catalog, {"years": (2024,)}), {})

    def test_inventory_is_semi_additive(self):
        year = {"years": (2025,)}
        march = {"year_months": ("2025-03",)}
        seattle = {"stores": ("Seattle Pike",), "year_months": ("2025-03",)}
        self.assertLess(inventory_units(self.catalog, year), inventory_sum_across_dates(self.catalog, year))
        self.assertEqual(inventory_units(self.catalog, year), 1890)
        self.assertEqual(inventory_sum_across_dates(self.catalog, year), 22308)
        self.assertEqual(inventory_units(self.catalog, march), 1875)
        self.assertEqual(inventory_units(self.catalog, march), inventory_sum_across_dates(self.catalog, march))
        self.assertEqual(inventory_units(self.catalog, seattle), 470)
        window = {
            "stores": ("Seattle Pike",),
            "date_from": "2025-03-04",
            "date_to": "2025-03-31",
        }
        from harbor.model import units
        self.assertEqual(weekly_units(self.catalog, seattle), (Decimal(units(self.catalog, window)) / 4).quantize(Decimal("0.01")))
        self.assertEqual(weeks_of_supply(self.catalog, seattle), Decimal("4.87"))

    def test_customer_filter_does_not_change_weeks_of_supply(self):
        month = {"year_months": ("2025-03",)}
        hotels = {"customers": ("Harbor Hotels",), "year_months": ("2025-03",)}
        self.assertEqual(weeks_of_supply(self.catalog, month), weeks_of_supply(self.catalog, hotels))
        self.assertEqual(inventory_units(self.catalog, month), inventory_units(self.catalog, hotels))
        self.assertLess(revenue(self.catalog, hotels), revenue(self.catalog, month))


if __name__ == "__main__":
    unittest.main()
