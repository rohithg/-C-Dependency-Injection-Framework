# Harbor & Co. commercial analytics

Ticket for a senior BI analyst / analytics engineer. The business asks are at the top. The metric contract below them is what "done" means. The build that answers this ticket is the rest of this folder. The plain-language tour is `WALKTHROUGH.md`.

## The questions

Finance and the store managers asked for one set of numbers, not a spreadsheet per person.

1. Which stores beat the plan in 2025, and by how much?
2. What is margin after discount, and did it hold up versus last year?
3. How much inventory is on the shelf right now, and how many weeks of selling does that cover?
4. House Blend went from $12 to $13 on 1 March 2025. Grinders went from $89 to $99 on 1 June 2025. How much of the growth is the new price, and how much is selling more?
5. A regional manager may see only that region's stores. A customer filter must not change the plan or the shelf.
6. The same question asked tomorrow must return the same number, unless a new batch has been published.

## Grain

| Table | One row is | What you may add up |
|---|---|---|
| Fact sales | One product on one order | Dollars, units. Count orders with a distinct count, not a count of lines. |
| Fact budget | One store, one product, one month | Budget dollars. There is no day, and there is no customer. |
| Fact inventory | One store, one product, one month-end count | Units across stores and products. Never across dates. |
| Product price | One price that was in force for a span of dates | Nothing. It describes a version. |
| Product, store, customer, date | The thing you filter by | Nothing. |

Sales run from 1 January 2024 through 31 December 2025. Wholesale orders ship two days later, so the date table continues through 5 January 2026. Days with no sales still have a date row.

## Certified metrics

Every name below is a measure. A chart does not get to invent a second formula.

| Name | Meaning | What a filter may change | What a filter must not change |
|---|---|---|---|
| Revenue | Sum of line net amount, after discount, by order date | Date, store, product, customer | — |
| Cost | Sum of line cost | Same as revenue | — |
| Margin | Revenue minus cost | Same as revenue | — |
| Margin % | Margin divided by revenue. Blank when revenue is 0 | Same as revenue | — |
| Units | Sum of quantity | Same as revenue | — |
| Orders | Distinct order ids | Same as revenue | — |
| Average order value | Revenue divided by orders | Same as revenue | — |
| Revenue YTD | Revenue from 1 January through the last date in context | Date sets the end. Store, product, and customer stay | — |
| Revenue PY | The same period one year earlier | Same | Blank for 2024, because 2023 was not loaded |
| Revenue YoY and YoY % | Current minus prior, and that gap divided by the prior | Same | YoY % is blank when the prior is 0 |
| Revenue by ship date | Revenue, with the date filter applied to ship date | Same | Order date is unchanged for every other measure |
| Budget | The monthly plan for the year-months in context | Store, product, year-month | Customer, segment, and a single day inside the month |
| Budget variance | Revenue minus budget | Whatever each input allows | — |
| Share of category | This product's revenue divided by its category | Category stays. The product filter is removed from the denominator | Other products in the category |
| Inventory units | Units on hand on the last snapshot inside the dates, summed across store and product | Date, store, product | Customer. Also must not add January to February |
| Weekly units | Units sold in the 28 days ending at the last date in context, divided by 4 | Date, store, product | Customer and segment |
| Weeks of supply | Inventory units divided by weekly units | Date, store, product | Customer and segment |

Money is to the cent. Percents in the lesson notes are shown to two decimal places.

## Rules that are easy to get wrong

**Price.** The sale stores the list price that was legal on the order date, and it stores a key to that version. The product dimension stores only the price a customer would pay today. House Blend's current price is $13. A 2024 sale of House Blend still used $12. The plan was written at the launch price and is not rewritten when a price changes. That is how a price increase can beat an old plan.

**Inventory.** Counts happen on the last day of the month only. "On hand in 2025" means 31 December 2025, not the sum of twelve counts. "On hand in March 2025" means 31 March 2025. Weeks of supply uses the trailing 28 days, even when that window starts in the prior month. For a March slicer the window is 4 March through 31 March.

**Security.** The role `West stores` filters the store dimension to Region = West. Sales, budget, and inventory all follow, because each of them relates to store. It is a static role so it can be tested without a login.

**Freshness.** Every fact row in this publish carries batch id `2026-01-06`. A rebuild of the same batch must be safe to run twice. It replaces the batch. It does not append a second copy.

**Relationships.** Filter flows from the dimension to the fact. Ship date is an inactive second relationship. The price-version table is not related to the product table. Relating both would give two paths from a price to a sale, and the model would refuse to answer.

## Acceptance

Publish is allowed only when all of these are true. `python3 -m harbor.quality` and `python3 -m unittest tests.test_measures` are the check.

- Date table has no gaps from 1 January 2024 through 5 January 2026.
- Every sales, budget, and inventory key exists on its dimension.
- Sales grain is one row per order and product. Budget and inventory grains are one row per store, product, and month.
- Each product has exactly one current price. Versions do not overlap and do not leave a gap.
- Every sale's price key is the version that covers that order date, and the product on the key matches the product on the sale.
- The product dimension's list price equals the current version. House Blend is $13.00. Grinder is $99.00.
- 2024 House Blend sales still point at $12.00. Sales on or after 1 March 2025 point at $13.00.
- The March 2025 Seattle plan for House Blend is the launch price, $327.89, not the new price.
- Kept bronze lines, after dropping blank quantities, non-positive quantities, and duplicate lines, sum to the same net amount as the fact, to the cent.
- The three rejected lines are in quarantine, with the reasons "quantity is blank or not positive" and "duplicate line".
- 2025 inventory units are less than the sum of the twelve snapshots. March inventory units equal the 31 March snapshot only.
- A Harbor Hotels filter changes March revenue and does not change March budget, March inventory, or March weeks of supply.
- Of 2025 revenue, $1,261.20 is the House Blend price change and $7,761.00 is the Grinder price change. 2024 has no price lift.

## Out of scope

This ticket does not include a finished dashboard, a Fabric tenant, or a live cash-register feed. The report page is blank so the first visual is part of learning filter context. Power BI Desktop and Spark were not run in the environment that built this folder. The Python checks are the proof the formulas match the files.
