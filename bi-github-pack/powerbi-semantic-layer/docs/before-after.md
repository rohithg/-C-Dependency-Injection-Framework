# Before / After — Sales vs Finance “Revenue” Conflict

## Before: two numbers, one meeting

Monday leadership review. Sales presents **$12.4M revenue** from a regional workbook. Finance presents **$11.1M revenue** from the close pack. Thirty minutes lost arguing whose file is right.

Root causes (typical, and what we found):

| Team | What they called “Revenue” | Actual logic |
|---|---|---|
| Sales | Bookings + invoices, ship-date aligned, pre-return | Mixed FactOrders + FactSales, no credit memos |
| Finance | Recognized sales per invoice date, net of returns | GL-aligned, but undocumented in self-serve models |
| Regional ops | Gross sales before discounts | Promo discounts left in |

There was no glossary owner, no certified measure, and five .pbix files each with a local `Revenue = SUM(...)` expression.

Symptoms:

- Ad-hoc Slack/email requests: *“Can you pull revenue for West Packaging YTD?”* — answered with one-off SQL or Excel.
- Every board deck regenerated metrics from scratch.
- RLS absent → analysts exported everything and filtered in spreadsheets (worse drift).

---

## Intervention: semantic layer contract

1. **Name the metric** — Enterprise term is **Net Sales**. “Revenue” is a banned alias in reviews.
2. **Write the glossary row** — owner = Sales Ops + FP&A jointly; grain = invoice line × day; formula = Gross − Discounts − Returns.
3. **Implement one DAX measure** in the shared dataset (`[Net Sales]`), plus `[Net Sales (Ship Date)]` via `USERELATIONSHIP` for ops.
4. **Retire local measures** — report migration checklist; old datasets marked Deprecated.
5. **Certify & endorse** — Power BI Certified badge; App points only at SL-Prod.
6. **Govern requests** — if the metric exists in the glossary, the answer is “use Net Sales on the Sales Performance app,” not a new extract.

---

## After: one number, shorter meetings

| Metric | Sales dashboard | Finance close pack | Delta |
|---|---|---|---|
| Net Sales (Invoice Date) YTD | $11.1M | $11.1M | $0 |
| Net Sales (Ship Date) YTD | $11.3M | n/a (ops view) | Explicit alternate — not a conflict |

Same certified measure, different date role — **documented**, not debated.

### Request volume (illustrative pattern matching the resume narrative)

| Request type | Before (per month) | After (per month) |
|---|---|---|
| “Pull revenue for my region” | High teens / dozens | Near zero (self-serve app + RLS) |
| “Why don’t Sales and Finance match?” | Recurring weekly | Rare; routed to glossary |
| New dashboard KPI copy-paste | Common | Blocked unless glossary PR |

The broader program scaled to ~**250 certified metrics** and ~**300 glossary terms**, covering Sales, AR/AP aging, margin, OTIF, and fleet cost — with **80+ stakeholders** on governed apps instead of personal files.

---

## What actually changed technically

```dax
// Before (report-local, three variants in the wild)
Revenue = SUM ( Sales[Amount] )
Revenue = SUM ( Sales[Amount] ) - SUM ( Sales[Discount] )
Revenue = CALCULATE ( SUM ( Sales[Amount] ), Sales[Type] = "Invoice" )

// After (certified)
Net Sales =
VAR _gross =
    CALCULATE ( [Gross Sales], FactSales[DocType] = "Invoice" )
VAR _discounts =
    CALCULATE ( [Discounts], FactSales[DocType] = "Invoice" )
VAR _returns = [Returns & Allowances]
RETURN
    _gross - _discounts - _returns
```

Plus:

- Star schema with inactive ship-date relationship  
- Region/BU RLS so exports match the app  
- Workspace promotion Dev → UAT → Prod with owner sign-off  

---

## Takeaway for hiring managers

Semantic layer work is not “building a dashboard.” It is **conflict resolution encoded in DAX and process**: one grain, one owner, one measure, enforced through certification and workspace governance.
