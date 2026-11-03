# Harbor, from the question to the number

Read this first. It walks the same project a senior BI analyst would be handed, in the order you would actually do the work. No Power BI background is assumed. The ticket is `REQUIREMENTS.md`. The formulas and file map are in `README.md`.

## 1. What the boss asked

Harbor & Co. has four coffee shops: Seattle Pike, Portland Pearl, Austin Congress, and Denver LoHi. Someone in finance Slacked you this:

> For 2025, which stores beat plan? What was margin after discounts? How many weeks of coffee and gear are sitting on the shelf? House Blend and the grinder both got a price increase. Did we grow because we sold more, or because we charged more? West-region managers should only see West stores. And please stop emailing me a different spreadsheet every Friday.

That is the whole job. Everything else in this folder exists so those answers stay the same no matter who asks.

## 2. Why the answer does not live in the chart

A beginner puts the formula in the chart: "sum this column, but only for Seattle, and divide by last year." Next week someone copies the chart, forgets the Seattle filter, and finance has two revenues.

The grown-up split is three layers:

1. **The files** hold rows. A row is one thing that happened, or one thing that exists.
2. **The semantic model** holds the names. Revenue means one formula. Budget means another. A slicer does not get to change the formula, only which rows it sees.
3. **The report** holds the question. "Seattle, March 2025" is a filter. The card asks for Revenue. The model applies the filter and runs the formula.

You can change the picture without changing the meaning. You cannot accidentally invent a second meaning of Revenue.

## 3. Words you need, once

- A **fact** is an event or a measurement: a sale, a plan, a shelf count.
- A **dimension** is a thing you filter by: the date, the product, the store, the customer.
- A **key** is the id that connects them. The sale stores `StoreKey = 1`. The store table says 1 means Seattle Pike. The sale does not store the words "Seattle Pike" again.
- A **measure** is a named formula. It has no row of its own. It runs when a visual asks.
- A **filter context** is the set of filters in force when the measure runs. The slicer, the row of a table, and the page filter all add to it.
- **Additive** means you can add the rows and get the right total. Dollars of sales are additive. "Units on the shelf in January" plus "units on the shelf in February" is not, because a lot of those units are the same bags, counted twice.

## 4. What landed from the register

The cash-register export is `data/bronze/sales_export.csv`. Bronze means "as it arrived," including the bad parts. 9,216 lines arrived for 1 January 2024 through 31 December 2025.

Three of them are not real sales, and they were planted so the cleaning step has something to catch:

- one line with a blank quantity
- one line with quantity −3
- one exact copy of a real line

Those three go to `data/quarantine/rejected_sales.csv` with a reason. Gold keeps 9,213 lines. Gold means "safe to report."

Each kept line already knows its own money: quantity times the price that day, minus any discount. That net amount is stored on the fact. Revenue is then just a sum. You do not multiply price times quantity again inside the chart, or a discount gets applied twice the first time someone "helps."

Check that this happened: add up the kept bronze lines yourself, and add up `Net Amount` on the fact. They match to the cent. If they ever don't, the batch is not published. That check is in `harbor/quality.py`.

## 5. Why the sale stores a key, not a name

The gold sales file has store 1, product 1, customer 7, and a date key like 20250315. The names live once:

- 4 stores
- 12 products
- 22 customers
- 736 dates, one per day, including days nobody bought anything

The date table runs through 5 January 2026 because a wholesale order placed on 31 December ships two days later. Time comparisons need those days to exist even when no order was placed on them. A gap in the date table makes "year to date" and "last year" skip or double days.

This shape is a star. The fact is the center. The dimensions are the points. A filter on a dimension walks inward to the fact. It does not walk sideways into a fact that has no path.

```
DimDate ──────── FactSales ──────── DimProduct
   │                 │    │              │
   │                 │    └── DimCustomer│
   │                 └───── DimStore     │
   │                       │             │
   └──── FactInventory ────┴─────────────┘
                DimProductPrice
                     ▲
                     └── FactSales also points here, for the price that day

DimProduct ── FactBudget ── DimStore
```

Budget has no line to the date table and no line to the customer table. That is a decision, not an omission. Inventory has no line to the customer table. The price-version table has no line to the product table.

## 6. A price change is a new row, not an overwrite

On 1 March 2025, House Blend went from $12 to $13. On 1 June 2025, the grinder went from $89 to $99.

If you overwrite the product's price, every old sale suddenly looks like it happened at the new price. Last year's revenue moves. That is a broken history.

So the warehouse keeps two different ideas:

- **Who the product is today.** `DimProduct` has one row per product. Its list price is the price a customer would pay today. House Blend says $13. The grinder says $99. The price-band column ("Value" under $20, "Premium" at $20 or more) uses that current price. House Blend is still Value.
- **What the price was on a given day.** `DimProductPrice` has 14 rows. House Blend has a row from 1 January 2024 through 28 February 2025 at $12, and a row from 1 March 2025 onward at $13. Each product has exactly one row marked current. The ranges touch and do not overlap.

Each sale stores `ProductPriceKey`, the version that covered the order date. A 2024 House Blend sale points at $12. A sale on 1 March 2025 or later points at $13. The dollars on the sale were computed with that version, so the history is in the number and in the key.

The plan does not get the new price. Budget was written at the launch price. Seattle's March 2025 plan for House Blend is $327.89, which is the $12 price. It is not rewritten to $13. That is what lets you say "we beat the plan," including the part of the beat that came from charging more.

How much was the price, and how much was volume? Take each 2025 line, keep its discount rate, and ask what the net would have been at the launch price. The difference is the price lift.

- House Blend: **$1,261.20**
- Grinder: **$7,761.00**
- Together: **$9,022.20**

2025 revenue is $328,659.80. 2024 was $266,163.60. The company grew **$62,496.20**, which is **23.48%**. About $9,022.20 of that is the two price changes. The other **$53,474.00** is selling more, and a different mix of products. 2024 itself has no price lift. Both changes happen in 2025, so last year's revenue did not move when the new prices were added. That is the test that history is intact.

## 7. The shelf is not a pile of months

Someone counts the stockroom on the last evening of each month. That count is one snapshot. There are 1,152 of them: 24 months, 4 stores, 12 products.

If you sum every snapshot in 2025 you get **22,308** units. That number is nonsense. It counts January's bags, then counts many of the same bags again in February, and so on for twelve months.

The certified measure, Inventory units, keeps only the last snapshot inside the dates you filtered, then adds across stores and products.

- Filter to 2025: the last snapshot is 31 December, and the company had **1,890** units on hand.
- Filter to March 2025: the only snapshot is 31 March, and the company had **1,875**. Adding dates and taking the last date agree, because there is only one count in that month.
- Filter to Seattle in March 2025: **470** units.

Weeks of supply asks a different question: if we keep selling at the recent pace, how many weeks does the shelf last?

Pace is the units sold in the 28 days that end on the last date in the filter, divided by 4. For a March 2025 filter that window is 4 March through 31 March, not "all of March," and not "the whole year."

- Company, end of 2025: pace **356.25** units a week, shelf **1,890**, which is **5.31** weeks.
- Seattle, March 2025: pace **96.50** units a week, shelf **470**, which is **4.87** weeks.
- Company, March 2025: **5.17** weeks.

A customer slicer does not change this. Harbor Hotels in March is a real customer, and their revenue is much smaller than the company's. The shelf is still the company's shelf (or the store's shelf, if you filtered a store). Dividing the whole stockroom by one customer's purchases would say the shelf lasts a year, which is a bug. Weekly units drops customer filters on purpose. Revenue does not. Budget does not see customers either, for the same kind of reason: the plan was never written per customer, and there is no relationship to carry the filter.

## 8. The numbers finance asked for

Company, calendar 2025, by order date:

| Question | Answer |
|---|---|
| Revenue | $328,659.80 |
| Cost | $124,260.30 |
| Margin | $204,399.50 |
| Margin % | 62.19% |
| Units | 18,270 |
| Orders | 2,673 |
| Average order value | $122.96 |
| Last year | $266,163.60 |
| Growth | $62,496.20, or 23.48% |
| Plan | $261,736.50 |
| Beat the plan by | $66,923.30 |
| On the shelf, 31 Dec | 1,890 units, 5.31 weeks |

Every store beat its own 2025 plan:

| Store | Region | Revenue | Plan | Beat plan by |
|---|---|---|---|---|
| Seattle Pike | West | $84,920.35 | $77,178.77 | $7,741.58 |
| Portland Pearl | West | $85,656.80 | $60,400.76 | $25,256.04 |
| Austin Congress | South | $79,189.70 | $67,111.93 | $12,077.77 |
| Denver LoHi | Mountain | $78,892.95 | $57,045.04 | $21,847.91 |

West, which is Seattle plus Portland, did **$170,577.15** of revenue in 2025. That is the number a West manager sees. Austin and Denver disappear under the West role, because the role filters the store table and every fact hangs off that table.

Coffee in 2025, as a share of coffee rather than of the whole company:

| Product | Revenue | Share of coffee |
|---|---|---|
| Espresso Beans | $28,188.00 | 41.21% |
| House Blend | $19,576.80 | 28.62% |
| Loose Tea | $12,702.40 | 18.57% |
| Cold Brew | $7,937.00 | 11.60% |

The shares add to 100%. The formula removes the product filter and keeps the category filter. If it removed the category too, each coffee would be divided by gear and food as well, and the shares would not add to 100% of coffee.

## 9. One worked example: Seattle, March 2025

Put the year-month `2025-03` on the date table and the store Seattle Pike on the store table. Every measure below is that same question, with one formula each.

| Measure | Value | In one sentence |
|---|---|---|
| Revenue | $6,737.00 | Sum of net amount on Seattle lines ordered in March 2025. |
| Cost | $2,537.90 | Sum of cost on those same lines. |
| Margin | $4,199.10 | Revenue minus cost. |
| Margin % | 62.33% | Margin divided by revenue. |
| Units | 414 | Quantity on those lines. |
| Orders | 68 | Distinct orders, so a three-product order counts once. |
| Average order value | $99.07 | $6,737.00 divided by 68 orders. |
| Revenue YTD | $20,226.65 | Same store, 1 January through 31 March 2025. The store filter stays. |
| Revenue PY | $3,151.00 | Same store, March 2024. |
| Revenue YoY | $3,586.00 | This March minus last March. |
| Revenue YoY % | 113.81% | That gap divided by last March. |
| Budget | $6,024.95 | March's plan for Seattle, every product, still at launch prices. |
| Budget variance | $712.05 | $6,737.00 minus $6,024.95. Seattle's March beat the plan. |
| Revenue by ship date | $6,674.80 | Same slicers, but the date filter uses ship date. |
| Inventory units | 470 | The 31 March count at Seattle, every product. |
| Weekly units | 96.50 | Seattle units sold from 4 March through 31 March, divided by 4. |
| Weeks of supply | 4.87 | 470 divided by 96.50. |

Two traps that show up the moment you change the slicer:

- Company-wide March revenue is **$28,957.90** and the March plan is **$20,432.42**. Filter the customer to Harbor Hotels and revenue falls to **$3,818.20**. The plan stays **$20,432.42**. Inventory stays **1,875**. Weeks of supply stays **5.17**. There is no path from a customer to the plan or the shelf.
- Wholesale March revenue is **$15,998.15** by order date and **$14,950.45** by ship date. Orders placed at the end of March ship in April. Both numbers are right. They answer different questions. Only the ship-date measure uses the ship-date path. Every other measure stays on order date.

## 10. The tests that would fail the project

A senior does not call it done because a card looks plausible. The next refresh has to be able to fail loudly.

`harbor/quality.py` refuses the batch when any of these break:

- a key is duplicated, or a fact points at a store, product, customer, date, or price that does not exist
- the date table skips a day
- a product has two "current" prices, or a gap, or an overlap
- a sale's price version does not cover the order date
- today's product price does not match the current version
- the plan was silently rewritten at the new House Blend price
- the bronze file and the fact disagree by even one cent
- a year of inventory equals the sum of its months (that would mean the semi-additive measure got replaced with a plain sum)
- a customer filter changes weeks of supply

The batch id on every fact row is `2026-01-06`. Rebuilding that batch replaces it. It does not stack a second copy on top. Sixteen tests in `tests/test_measures.py` plus that quality gate are what got run. They passed.

Run them yourself from this folder:

```bash
python3 scripts/build_data.py
python3 -m unittest tests.test_measures
python3 -m harbor.quality
```

`build_data.py` rewrites the CSVs and `data/lesson.json`. The lesson file is the dump of the slices quoted above. If you change the generator, re-run it and update the quotes. Do not edit a CSV by hand.

## 11. What you click

This machine has no Power BI Desktop and no Fabric workspace. The model is still a real Power BI project (`powerbi/Harbor.pbip`), and the lakehouse notebook is the Spark shape of the same steps. Neither was executed here. The Python checks are the proof.

When you open it on a machine that has Desktop:

1. Open `powerbi/Harbor.pbip`.
2. Set the parameter `DataRoot` to the `data/gold` folder. Use forward slashes.
3. Refresh.
4. On the blank page, slice Year Month to `2025-03` and Store to Seattle Pike.
5. A Revenue card should read **$6,737.00**. Revenue YTD should read **$20,226.65**. Revenue PY should read **$3,151.00**. Inventory units should read **470**. Weeks of supply should read **4.87**.
6. Add Product, Revenue, and Share of category, with Category = Coffee. The shares should match the coffee table above.
7. Modeling, Security, View as, `West stores`. Clear the store slicer and set the year to 2025. Revenue should read **$170,577.15**.

In a real Fabric workspace you would copy the bronze, reference, source, and budget files into the lakehouse, run `Build star schema`, and point these same tables at the Delta tables. The measures do not change. Direct Lake reads the gold tables in place. This project imports CSV so it opens with no tenant.

## 12. The order, in one list

1. Write down the questions and the metric contract before you build. That is `REQUIREMENTS.md`.
2. Land the export. Keep the bad rows, and keep a reason for each rejection.
3. Build the star: facts at the right grain, dimensions for the things people filter, keys instead of repeated names.
4. Keep price history as versions. Do not overwrite yesterday.
5. Leave the plan at the price it was written at.
6. Store shelf counts as snapshots. Teach the measure to keep the last one.
7. Put every business name in the semantic model, with the filter behavior written into the formula.
8. Reconcile bronze to gold. Assert the traps: customer versus plan, customer versus shelf, year of inventory versus sum of months, old sales still at the old price.
9. Stamp a batch id. Only then let a report read the measures.
