# Harbor & Co. — Power BI semantic model and Fabric lakehouse

A four-store retailer, January 2024 through December 2025. The files under `data/` are the warehouse. The folder `fabric/` is the lakehouse, notebook, and pipeline. The folder `powerbi/` is the semantic model and a blank report bound to it.

Open `powerbi/Harbor.pbip` in Power BI Desktop. Before the first refresh, set the `DataRoot` parameter to the `data/gold` folder on your machine. In this repo that path is `/workspace/13-powerbi-fabric/data/gold`. Use forward slashes. The report page is blank on purpose: the first visual is how you see filter context work.

This machine cannot run Power BI Desktop or a Fabric workspace. The measure math is checked locally:

```bash
cd 13-powerbi-fabric
python3 scripts/build_data.py
python3 -m unittest tests.test_measures
```

## The three layers

A report does not hold the business rules. A lakehouse does not hold them either. They sit in the middle, in the semantic model.

| Layer | What it is here | What a number means there |
|---|---|---|
| Fabric lakehouse | `fabric/HarborLakehouse.Lakehouse` plus the notebook | Rows. Bronze is the export. Gold is a star schema of additive amounts. |
| Semantic model | `powerbi/Harbor.SemanticModel` | The names Revenue, Margin, and Revenue YTD, and the relationships that make a slicer work. |
| Report | `powerbi/Harbor.Report` | A filter. A card that shows Revenue is a filter context plus the Revenue measure. |

Fabric Git does not store lakehouse table data. The CSVs in `data/` are the data. After you sync `fabric/` to a workspace, copy `data/bronze/sales_export.csv` to `Files/bronze/`, `data/reference/` to `Files/reference/`, and `data/gold/fact_budget.csv` to `Files/gold/`, then run the notebook.

## What the rows are

9,216 lines landed in bronze. Three are rejected: a blank quantity, a negative quantity, and a duplicate line. Gold keeps 9,213 order lines. The date table has 736 days, 1 January 2024 through 5 January 2026, including days with no sales. Budget is 1,152 rows: 24 months × 4 stores × 12 products.

2025 revenue is **$319,637.60**. 2024 was **$266,163.60**. That is a **20.09%** increase. Margin in 2025 is **$195,377.30**, which is **61.12%** of revenue. The 2025 plan was **$261,736.50**, so the company beat it.

## Star schema

A star schema is a fact table of events surrounded by short dimension tables of things you filter by. Filters travel from the dimension into the fact, one direction, many-to-one.

```
DimDate ──── FactSales ──── DimProduct
               │     │
               │     └── DimCustomer
               └──────── DimStore
DimProduct ── FactBudget ── DimStore
```

`FactSales` is one row per order line. `Net Amount` and `Cost Amount` are already extended (quantity times price, minus discount). They are additive: the total of a group is the sum of the lines. That is why Revenue is `SUM`, not `SUMX` of price times quantity. The multiplication happened once, in the warehouse.

`FactBudget` is a different grain: one row per store, product, and month. It is related to store and product. It is not related to `DimDate`. That missing relationship is deliberate, and the Budget measure shows what you do instead.

Keys are integers and hidden. The report shows Store, Product, and Month, never StoreKey. `discourageImplicitMeasures` is on, so Desktop will not offer a raw sum of a column you drag out. If a number has a business name, it is a measure on `Metrics`.

## Filter context, on one store and one month

Put **2025-03** on `DimDate[Year Month]` and **Seattle Pike** on `DimStore[Store]`. Every measure below is evaluated in that filter context.

| Measure | Value | Why |
|---|---|---|
| Revenue | $6,696.90 | Sum of `Net Amount` on lines whose order date is in March 2025 and whose store is Seattle Pike. |
| Revenue YTD | $20,186.55 | Same store, dates from 1 January 2025 through 31 March 2025. `DATESYTD` changes the date filter and leaves the store filter alone. |
| Revenue PY | $3,151.00 | Same store, March 2024. `SAMEPERIODLASTYEAR` shifts the dates. |
| Revenue YoY | $3,545.90 | Current minus prior. |
| Revenue YoY % | 112.53% | That difference divided by the prior. `DIVIDE` returns blank when the prior is zero, which is what 2024 does against 2023. |
| Budget | $6,024.95 | March's plan for Seattle, every product. |
| Budget variance | $671.95 | Revenue minus budget. Seattle's March beat the plan. |
| Revenue by ship date | $6,634.70 | Same slicers, but the date filter travels through ship date. |
| Margin % | 62.10% | Margin divided by revenue, inside the same filter. |
| Orders | 68 | Distinct order ids, not a count of lines. |
| Average order value | $98.48 | Revenue divided by orders. |

The company-wide March 2025 budget is **$20,432.42** and March revenue is **$28,821.50**. Filter the customer to Harbor Hotels and revenue falls to **$3,789.50**. Budget stays **$20,432.42**. A filter only moves across a relationship. Customers are not related to the budget fact, so a customer slicer cannot change Budget. Store is related, so a store slicer can.

## The measures

They live in `definition/tables/Metrics.tmdl`. A measure is a formula. It is not a column of stored answers. When a visual asks for it, the engine builds a filter context and runs the formula there.

```dax
Revenue = SUM(FactSales[Net Amount])

Margin = [Revenue] - [Cost]

Margin % = DIVIDE([Margin], [Revenue])
```

`DIVIDE` is the division you want in a model. A slash errors or returns infinity when the denominator is blank or zero. `DIVIDE` returns blank.

```dax
Orders = DISTINCTCOUNT(FactSales[OrderId])

Average order value = DIVIDE([Revenue], [Orders])
```

`COUNTROWS` would count lines. An order with three products would count three times. Distinct order ids count orders.

### CALCULATE

`CALCULATE` is the only function that changes filter context. Everything else reads the context it was given.

```dax
Revenue YTD = CALCULATE([Revenue], DATESYTD(DimDate[Date]))

Revenue PY = CALCULATE([Revenue], SAMEPERIODLASTYEAR(DimDate[Date]))

Revenue by ship date =
    CALCULATE(
        [Revenue],
        USERELATIONSHIP(FactSales[ShipDate], DimDate[Date])
    )
```

`DATESYTD` returns the dates from 1 January through the last date currently in context. `CALCULATE` replaces the date filter with that set. The store filter is not mentioned, so it survives.

`USERELATIONSHIP` turns on the inactive ship-date relationship for that measure only. Two relationships between the same two tables cannot both be active. Outside this measure, order date wins. Wholesale March 2025 is **$15,916.45** by order date and **$14,878.75** by ship date, because a wholesale order placed at the end of March ships two days later, in April.

### Budget and TREATAS

```dax
Budget =
    CALCULATE(
        SUM(FactBudget[Budget Amount]),
        REMOVEFILTERS(DimDate),
        TREATAS(VALUES(DimDate[Year Month]), FactBudget[Year Month])
    )
```

`VALUES` reads the year-months in the current date filter. `TREATAS` applies those values to `FactBudget[Year Month]` as if a relationship existed. `REMOVEFILTERS(DimDate)` matters because budget has no date relationship to begin with; it keeps a day-level filter from leaking in if you add one later.

This budget is monthly. A filter on a single day still returns that whole month's plan. Do not put Budget on a daily chart and read the gap as a daily miss.

### Share of category

```dax
Share of category =
    DIVIDE(
        [Revenue],
        CALCULATE([Revenue], ALLEXCEPT(DimProduct, DimProduct[Category]))
    )
```

`ALLEXCEPT` removes every filter on `DimProduct` except Category. On a visual with products as rows, the numerator keeps the product and the denominator is the category total. In 2025 coffee:

| Product | Revenue | Share of coffee |
|---|---|---|
| Espresso Beans | $28,188.00 | 41.98% |
| House Blend | $18,315.60 | 27.28% |
| Loose Tea | $12,702.40 | 18.92% |
| Cold Brew | $7,937.00 | 11.82% |

`ALL(DimProduct)` would have divided by all categories, not by coffee. `ALL(DimProduct[Product])` is the same idea as this `ALLEXCEPT` when Category is the only other filter, and it is the form you will see in older models.

### Row context and calculated columns

A calculated column is computed once per row, at refresh, and stored. `DimProduct[Price band]` is one:

```dax
Price band = IF([List Price] >= 20, "Premium", "Value")
```

Inside that formula, `[List Price]` means this product's price. That is row context. Grinder and Kettle are Premium. House Blend at $12 is Value. The value does not change when someone slices to March.

Revenue is not a calculated column. A stored revenue on each line would still have to be summed, and a stored "revenue for the year" would be wrong the moment a slicer changed. Measures run at query time, in whatever filter the visual built.

`SUMX` is the bridge. It walks rows (row context) and, if the expression uses a measure, turns that row into a filter (context transition). This model does not need `SUMX`, because the fact already stores additive amounts. Use `SUMX` when the amount does not exist until you multiply columns that vary by row and you chose not to store the product.

### Time intelligence as a calculation group

`Time intelligence.tmdl` repeats YTD, prior year, and YoY % with `SELECTEDMEASURE()`. Drop the calculation group column on a visual next to any measure and the same date logic applies to Units or Margin, not only Revenue. The explicit measures on `Metrics` are the ones to read first. The calculation group is that pattern made reusable.

Time intelligence functions need a date table with no gaps. `DimDate` is marked `dataCategory: Time`. If Desktop asks, mark it as a date table on the `Date` column. Turn off Auto date/time in options so Desktop does not build a hidden date table beside this one.

## Row-level security

`West stores` filters `DimStore` to `Region = "West"`. Because sales and budget both relate to store, the filter reaches both facts. In 2025, West revenue is **$165,711.45** (Seattle Pike and Portland Pearl). Modeling, then View as, then this role. It is a static role so you can test it without a login. A dynamic role uses `USERPRINCIPALNAME()` against a column of email addresses. The shape is the same: a filter on a dimension, and relationships carry it to the facts.

## What you do in Desktop

1. Open `powerbi/Harbor.pbip`.
2. Set `DataRoot` to your `data/gold` folder and refresh.
3. On the blank page, add a slicer for `Year Month` and set it to `2025-03`.
4. Add a slicer for `Store` and set it to Seattle Pike.
5. Add a card for `Revenue`. It should read $6,696.90. Add cards for `Revenue YTD` ($20,186.55) and `Revenue PY` ($3,151.00).
6. Add a table of `Product`, `Revenue`, and `Share of category`, with Category filtered to Coffee. The shares should match the table above.
7. Modeling, Security, View as, `West stores`. Clear the store slicer, set the year to 2025, and Revenue should read $165,711.45.

## What changes in a real Fabric tenant

This model imports CSV so it opens with no workspace. In Fabric you would point the same tables at the lakehouse Delta tables and set the partition mode to Direct Lake. The DAX does not change. Direct Lake reads the gold tables in place. Import copies them into the model at refresh. DirectQuery sends each visual's query back to SQL. Direct Lake is the Fabric default when the star schema already lives in the lakehouse and the report needs to stay current without a full copy.

The pipeline `Refresh Harbor` has one notebook activity. Its workspace id is a placeholder. After Git sync, bind it to `Build star schema`. Add a semantic-model refresh activity after the notebook in the pipeline editor. That is the whole daily run: land the file, build gold, refresh the model, the report reads the measures.

## Where each idea lives

| Idea | File |
|---|---|
| Bronze, the bad rows, the star, the plan | `harbor/model.py` |
| The same transform in Spark | `fabric/BuildStarSchema.Notebook/notebook-content.py` |
| Relationships, including the inactive ship date | `definition/relationships.tmdl` |
| Measures | `definition/tables/Metrics.tmdl` |
| Price band calculated column | `definition/tables/DimProduct.tmdl` |
| Calculation group | `definition/tables/Time intelligence.tmdl` |
| West role | `definition/roles/West stores.tmdl` |
| The CSV path parameter | `definition/expressions.tmdl` |
| Checks that the numbers above are the sums of the CSVs | `tests/test_measures.py` |
