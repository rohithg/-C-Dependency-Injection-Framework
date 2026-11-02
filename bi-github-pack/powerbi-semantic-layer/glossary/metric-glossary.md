# Metric Glossary — Curated High-Value Metrics

Governed definitions for the semantic layer. Each row is certification-ready: **owner**, **grain**, **formula notes**, and **common pitfalls**.

> Convention: `[Measure Name]` refers to the DAX measure in `dax/measures/`. Fact tables and keys match `model/star-schema.md`.

---

## Sales

| # | Metric | Definition | Owner | Grain | Formula notes | Pitfalls |
|---|---|---|---|---|---|---|
| 1 | **Gross Sales** | Sum of extended selling price before discounts, returns, and allowances. | Sales Ops | Invoice line × day | `SUM(FactSales[ExtendedPrice])` | Do not confuse with booked orders. |
| 2 | **Discounts** | Promotional + contractual discounts applied at invoice. | Sales Ops | Invoice line × day | `SUM(FactSales[DiscountAmount])` | Exclude early-pay cash discounts (Finance owns those). |
| 3 | **Returns & Allowances** | Credit memos and price adjustments reducing recognized sales. | Sales Ops | Invoice line × day | Filter `DocType IN {"Credit","Allowance"}` | Sign convention: store as positive amounts; subtract in Net Sales. |
| 4 | **Net Sales** | Gross Sales − Discounts − Returns & Allowances. **Certified enterprise revenue.** | Sales Ops + FP&A | Invoice line × day | `[Gross Sales] - [Discounts] - [Returns & Allowances]` | Invoice date is default; use Ship Date variant for ops. |
| 5 | **Net Sales (Ship Date)** | Net Sales re-sliced by ship date via inactive relationship. | Sales Ops | Invoice line × ship day | `CALCULATE([Net Sales], USERELATIONSHIP(...ShipDate...))` | Never dual-active date relationships. |
| 6 | **Units Sold** | Quantity shipped/invoiced in selling UOM. | Sales Ops | Invoice line × day | `SUM(FactSales[Quantity])` | Exclude free goods from ASP calc if policy says so. |
| 7 | **Average Selling Price (ASP)** | Net Sales ÷ Units Sold. | Sales Ops | Same as Net Sales | `DIVIDE([Net Sales], [Units Sold])` | Do not average unit prices across lines. |
| 8 | **Bookings** | Order value accepted in period (not yet necessarily invoiced). | Sales Ops | Order line × book date | `SUM(FactOrders[BookedAmount])` | Separate fact; do not mix with Net Sales. |
| 9 | **Backlog** | Open order value not yet invoiced as of as-of date. | Sales Ops | Open order line × as-of | Open status filter; as-of snapshot or open-items pattern | Requires as-of logic, not a simple SUM. |
| 10 | **Win Rate %** | Won opportunities ÷ closed opportunities by count or value. | Sales Ops | Opportunity × close date | `DIVIDE([Won Opp Value], [Closed Opp Value])` | Agree count vs value; document both if needed. |
| 11 | **Sales vs Quota %** | Net Sales ÷ Quota for aligned territory/period. | Sales Ops | Rep/territory × period | `DIVIDE([Net Sales], [Quota])` | Quota must match RLS territory grain. |

---

## Finance — Margin & P&L

| # | Metric | Definition | Owner | Grain | Formula notes | Pitfalls |
|---|---|---|---|---|---|---|
| 12 | **COGS** | Standard or actual cost of goods for invoiced lines. | FP&A / Cost Acct | Invoice line × day | `SUM(FactSales[COGSAmount])` | Align cost method (std vs actual) with close calendar. |
| 13 | **Gross Profit** | Net Sales − COGS. | FP&A | Same as Net Sales | `[Net Sales] - [COGS]` | Additive; safe to sum across dims. |
| 14 | **Gross Profit Margin %** | Gross Profit ÷ Net Sales. | FP&A | Same as Net Sales | `DIVIDE([Gross Profit], [Net Sales])` | Never average margin % of children. |
| 15 | **Contribution Margin** | Gross Profit − variable selling costs (freight out, commissions). | FP&A | Invoice line × day | `[Gross Profit] - [Variable Selling Cost]` | Document which costs are “variable.” |
| 16 | **Contribution Margin %** | Contribution Margin ÷ Net Sales. | FP&A | Same | `DIVIDE([Contribution Margin], [Net Sales])` | Same anti-pattern as GP%: no weighted-average shortcuts in visuals. |
| 17 | **OpEx** | Operating expenses booked in GL for period. | FP&A | GL account × period | From `FactGL` expense accounts | Map chart-of-accounts carefully. |
| 18 | **EBITDA (Mgmt)** | Management EBITDA per internal bridge (not statutory). | FP&A | BU × period | Document add-backs in glossary annex | Label as management, not GAAP. |

---

## Finance — AR / AP Aging

| # | Metric | Definition | Owner | Grain | Formula notes | Pitfalls |
|---|---|---|---|---|---|---|
| 19 | **AR Open Balance** | Sum of open receivable amounts as of selected as-of date. | Controllership | Open AR item × as-of | Filter open items; amount in local/reporting currency | As-of date ≠ report refresh date unless documented. |
| 20 | **AR Current (0–30)** | Open AR with days past due ≤ 30 (or not yet due, per policy). | Controllership | Same | Bucket via `SWITCH` on days past due | Clarify “not due” vs “0–30 past due.” |
| 21 | **AR Aging 31–60** | Open AR with 31–60 days past due. | Controllership | Same | Aging bucket measure | Buckets must be mutually exclusive. |
| 22 | **AR Aging 61–90** | Open AR with 61–90 days past due. | Controllership | Same | Aging bucket measure | — |
| 23 | **AR Aging 90+** | Open AR with > 90 days past due. | Controllership | Same | Aging bucket measure | Often drives reserve discussion. |
| 24 | **DSO** | Days Sales Outstanding: (AR Open ÷ Credit Sales) × days in period. | Controllership | Customer/BU × period | `DIVIDE([AR Open], [Credit Sales]) * [Days in Period]` | Use trailing 90-day sales for stability when agreed. |
| 25 | **AP Open Balance** | Sum of open payable amounts as of as-of date. | Controllership | Open AP item × as-of | Mirror of AR pattern | Vendor currency conversion rules. |
| 26 | **AP Aging 0–30 / 31–60 / 61–90 / 90+** | Open AP bucketed by days past due. | Controllership | Same | Same bucket pattern as AR | Match AP policy (invoice date vs due date). |
| 27 | **DPO** | Days Payable Outstanding: (AP Open ÷ COGS or purchases) × days. | Controllership | BU × period | Agree denominator with Treasury | Purchases vs COGS must be documented. |

---

## Operations

| # | Metric | Definition | Owner | Grain | Formula notes | Pitfalls |
|---|---|---|---|---|---|---|
| 28 | **Orders Shipped** | Count of distinct orders with ship confirmation in period. | Supply Chain | Order × ship date | `DISTINCTCOUNT(FactOps[OrderId])` with shipped flag | Line vs order grain confusion. |
| 29 | **Lines Shipped On Time** | Order lines shipped on or before promised date. | Supply Chain | Order line × ship date | Count where `ShipDate <= PromiseDate` | Time zone / calendar day boundary. |
| 30 | **Lines Shipped In Full** | Order lines where shipped qty ≥ ordered qty. | Supply Chain | Order line × ship date | Qty completeness flag | Partials across multiple shipments. |
| 31 | **OTIF %** | On-Time In-Full: lines that are both on time and in full ÷ total lines due. | Supply Chain | Order line × ship/due date | `DIVIDE([OTIF Lines], [Lines Due])` | Single enterprise definition; kill regional variants. |
| 32 | **Fill Rate %** | Shipped qty ÷ ordered qty for due lines. | Supply Chain | Order line × period | `DIVIDE([Qty Shipped], [Qty Ordered])` | Different from OTIF; do not substitute. |
| 33 | **Cycle Time (Order to Ship)** | Average days from order book to first ship. | Supply Chain | Order × ship | Average of date diff; consider median in visuals | Outliers skew mean. |
| 34 | **Inventory Turns** | COGS ÷ Average Inventory for period. | Supply Chain / FP&A | Item/BU × period | `DIVIDE([COGS], [Avg Inventory])` | Avg inventory = (beg+end)/2 or daily avg. |
| 35 | **Backorder Rate %** | Backordered lines ÷ total order lines. | Supply Chain | Order line × book date | Status / reason-code filter | Exclude customer-requested future ships. |

---

## Transportation

| # | Metric | Definition | Owner | Grain | Formula notes | Pitfalls |
|---|---|---|---|---|---|---|
| 36 | **Miles Driven** | Total trip miles (loaded + empty per policy). | Fleet Ops | Trip × day | `SUM(FactTransport[Miles])` | Document empty-mile inclusion. |
| 37 | **Cost per Mile** | Total fleet operating cost ÷ Miles Driven. | Fleet Ops | Trip/fleet × period | `DIVIDE([Fleet Cost], [Miles Driven])` | Align cost pool (fuel, maint, driver). |
| 38 | **Loaded Mile %** | Loaded miles ÷ total miles. | Fleet Ops | Trip × period | `DIVIDE([Loaded Miles], [Miles Driven])` | — |
| 39 | **On-Time Delivery % (Carrier)** | Deliveries within appointment window ÷ total deliveries. | Fleet Ops | Shipment × delivery date | Window tolerance in minutes/hours | Appointment vs ETA definitions differ. |
| 40 | **Freight Cost per Shipment** | Outbound freight $ ÷ shipment count. | Fleet Ops / FP&A | Shipment × day | `DIVIDE([Freight Cost], [Shipment Count])` | Accessorials in or out — document. |

---

## Cross-cutting time intelligence (applied to base measures)

| Pattern | Example | Notes |
|---|---|---|
| MTD / QTD / YTD | `[Net Sales YTD]` | `TOTALYTD` / `DATESYTD` against `DimDate` |
| Prior period | `[Net Sales PY]` | `SAMEPERIODLASTYEAR` or `DATEADD` |
| Δ / Δ% | `[Net Sales YoY %]` | `DIVIDE([Net Sales] - [Net Sales PY], [Net Sales PY])` |
| Rolling 12 | `[Net Sales R12]` | `DATESINPERIOD(..., -12, MONTH)` |

Implementations: [`../dax/measures/time_intelligence.dax`](../dax/measures/time_intelligence.dax)

---

## Certification checklist (per metric)

- [ ] Definition agreed by owner + secondary stakeholder
- [ ] Grain and date role documented
- [ ] DAX in certified dataset measure table
- [ ] RLS impact reviewed
- [ ] Synonyms / banned aliases listed (e.g., “Revenue” → use **Net Sales**)
- [ ] Dashboard visuals point to certified measure only

---

## Banned aliases (enforce in reviews)

| Do not use | Use instead |
|---|---|
| Revenue / Sales $ (ambiguous) | **Net Sales** or **Gross Sales** (explicit) |
| Margin (ambiguous) | **Gross Profit Margin %** or **Contribution Margin %** |
| On-time % (ambiguous) | **OTIF %** or **On-Time Delivery % (Carrier)** |
| Aging (no bucket) | **AR Aging 61–90** (named bucket) |
