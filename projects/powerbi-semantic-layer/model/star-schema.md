# Star Schema — Semantic Model Documentation

Enterprise tabular model supporting Sales, Finance (AR/AP/Margin), Operations, and Transportation.

## Design rules

1. **Single marked date table** (`DimDate`) — all time intelligence depends on it.
2. **One active date relationship per fact** — alternate dates are inactive + `USERELATIONSHIP`.
3. **Dimensions filter facts; facts never filter each other** (no fact-to-fact relationships).
4. **Degenerate attributes** (OrderId, InvoiceNumber) stay on facts when they are not reused as dimensions.
5. **Bridge tables** only for true M:M (e.g., sales rep ↔ account team) — none required in the minimal core below.

---

## Tables

### Dimensions

| Table | Grain | Key | Notable columns | SCD |
|---|---|---|---|---|
| `DimDate` | Day | `DateKey` (YYYYMMDD) | `Date`, `MonthStart`, `FiscalYear`, `FiscalMonth`, `IsHoliday` | N/A |
| `DimCustomer` | Customer | `CustomerKey` | `CustomerId`, `CustomerName`, `Channel`, `RegionKey`, `CreditTerms` | Type 2 on region/channel |
| `DimProduct` | Product | `ProductKey` | `SKU`, `ProductName`, `Category`, `BusinessUnitKey`, `StdCost` | Type 2 on BU/category |
| `DimRegion` | Region | `RegionKey` | `RegionCode`, `RegionName`, `Area`, `Country` | Type 1 |
| `DimBusinessUnit` | BU | `BusinessUnitKey` | `BUCode`, `BUName`, `Division` | Type 1 |
| `DimSalesRep` | Rep | `SalesRepKey` | `RepId`, `RepName`, `RegionKey`, `ManagerKey` | Type 2 |
| `DimVendor` | Vendor | `VendorKey` | `VendorId`, `VendorName`, `PaymentTerms` | Type 1 |
| `DimCarrier` | Carrier | `CarrierKey` | `CarrierCode`, `CarrierName`, `Mode` | Type 1 |
| `DimAccount` | GL account | `AccountKey` | `AccountCode`, `AccountClass`, `EBITDAAddBack` | Type 1 |
| `DimCurrency` | Currency | `CurrencyKey` | `CurrencyCode` | Type 1 |

### Facts

| Table | Grain | Additive $ / qty | Date key (active) | Inactive dates |
|---|---|---|---|---|
| `FactSales` | Invoice line | ExtendedPrice, Discount, Qty, COGS, Commission, FreightOut | `InvoiceDateKey` → DimDate | `ShipDateKey` → DimDate |
| `FactOrders` | Order line | BookedAmount, OpenAmount | `BookDateKey` → DimDate | `PromiseDateKey` |
| `FactOpportunity` | Opportunity | Amount | `CloseDateKey` → DimDate | `CreateDateKey` |
| `FactAR` | Open AR item | AmountOpen | `InvoiceDateKey` → DimDate (for filtering); aging uses DueDate | `DueDateKey`, `CloseDateKey` |
| `FactAP` | Open AP item | AmountOpen, InvoiceAmount | `InvoiceDateKey` → DimDate | `DueDateKey`, `CloseDateKey` |
| `FactOps` | Order line execution | QtyOrdered, QtyShipped | `ShipDateKey` → DimDate | `BookDateKey`, `PromiseDateKey` |
| `FactTransport` | Trip / shipment leg | Miles, costs, gallons | `TripDateKey` → DimDate | `DeliveryDateKey` |
| `FactInventory` | Item × day snapshot | InventoryValue, OnHandQty | `SnapshotDateKey` → DimDate | — |
| `FactGL` | Account × day (or period) | Amount | `PostingDateKey` → DimDate | — |
| `FactQuota` | Rep × month | QuotaAmount | `MonthDateKey` → DimDate | — |

---

## Relationship diagram (logical)

```
                         ┌──────────────┐
                         │   DimDate    │
                         └──────┬───────┘
           ┌─────────────┬──────┼──────┬─────────────┐
           │             │      │      │             │
           ▼             ▼      ▼      ▼             ▼
     FactSales     FactOrders  FactAR FactAP   FactOps / FactTransport
     FactQuota     FactOpp     FactGL          FactInventory
           │             │
           ▼             ▼
     DimCustomer    DimProduct ──► DimBusinessUnit
           │
           ▼
      DimRegion ◄── DimSalesRep

FactAR ──► DimCustomer
FactAP ──► DimVendor
FactTransport ──► DimCarrier
FactGL ──► DimAccount
```

---

## Relationships & cardinality

| From (many) | To (one) | Key | Cardinality | Cross-filter | Active |
|---|---|---|---|---|---|
| FactSales | DimDate | InvoiceDateKey → DateKey | Many:1 | Single | Yes |
| FactSales | DimDate | ShipDateKey → DateKey | Many:1 | Single | **No** |
| FactSales | DimCustomer | CustomerKey | Many:1 | Single | Yes |
| FactSales | DimProduct | ProductKey | Many:1 | Single | Yes |
| FactSales | DimSalesRep | SalesRepKey | Many:1 | Single | Yes |
| FactOrders | DimDate | BookDateKey → DateKey | Many:1 | Single | Yes |
| FactOrders | DimCustomer | CustomerKey | Many:1 | Single | Yes |
| FactOrders | DimProduct | ProductKey | Many:1 | Single | Yes |
| FactOpportunity | DimDate | CloseDateKey → DateKey | Many:1 | Single | Yes |
| FactOpportunity | DimSalesRep | SalesRepKey | Many:1 | Single | Yes |
| FactAR | DimDate | InvoiceDateKey → DateKey | Many:1 | Single | Yes |
| FactAR | DimCustomer | CustomerKey | Many:1 | Single | Yes |
| FactAP | DimDate | InvoiceDateKey → DateKey | Many:1 | Single | Yes |
| FactAP | DimVendor | VendorKey | Many:1 | Single | Yes |
| FactOps | DimDate | ShipDateKey → DateKey | Many:1 | Single | Yes |
| FactOps | DimProduct | ProductKey | Many:1 | Single | Yes |
| FactOps | DimCustomer | CustomerKey | Many:1 | Single | Yes |
| FactTransport | DimDate | TripDateKey → DateKey | Many:1 | Single | Yes |
| FactTransport | DimCarrier | CarrierKey | Many:1 | Single | Yes |
| FactTransport | DimRegion | RegionKey | Many:1 | Single | Yes |
| FactInventory | DimDate | SnapshotDateKey → DateKey | Many:1 | Single | Yes |
| FactInventory | DimProduct | ProductKey | Many:1 | Single | Yes |
| FactGL | DimDate | PostingDateKey → DateKey | Many:1 | Single | Yes |
| FactGL | DimAccount | AccountKey | Many:1 | Single | Yes |
| FactGL | DimBusinessUnit | BusinessUnitKey | Many:1 | Single | Yes |
| FactQuota | DimDate | MonthDateKey → DateKey | Many:1 | Single | Yes |
| FactQuota | DimSalesRep | SalesRepKey | Many:1 | Single | Yes |
| DimCustomer | DimRegion | RegionKey | Many:1 | Single | Yes |
| DimProduct | DimBusinessUnit | BusinessUnitKey | Many:1 | Single | Yes |
| DimSalesRep | DimRegion | RegionKey | Many:1 | Single | Yes |

Machine-readable copy: [`relationships.csv`](relationships.csv)

---

## Filter-flow notes (RLS-relevant)

- **Region RLS** on `DimRegion` flows to `DimCustomer`, `DimSalesRep`, and facts related through those paths. `FactTransport` has a direct `RegionKey` for fleet reports.
- **BU RLS** on `DimBusinessUnit` flows through `DimProduct` → sales/ops facts and directly into `FactGL`.
- Do **not** enable bidirectional filtering “to make slicers work” — fix the model or use measures/`TREATAS`.

---

## Aging bucket column (recommended)

Nightly refresh computes as-of **today** for operational dashboards:

```dax
-- Calculated column on FactAR (refresh-time as-of = TODAY)
AgingBucket =
VAR _dpd = INT ( TODAY () - FactAR[DueDate] )
RETURN
    SWITCH (
        TRUE (),
        _dpd <= 30, "Current",
        _dpd <= 60, "31-60",
        _dpd <= 90, "61-90",
        "90+"
    )
```

Month-end / arbitrary as-of reports use the **dynamic bucket measures** in `finance_measures.dax` instead of this column.

---

## Measure display folders

| Folder | Content |
|---|---|
| `Measures\Sales` | Net Sales, ASP, Bookings, Quota |
| `Measures\Finance` | AR/AP aging, DSO/DPO, margin, EBITDA |
| `Measures\Operations` | OTIF, fill rate, cycle time, fleet |
| `Measures\Time Intelligence` | MTD/QTD/YTD, PY, R12, YoY |

---

## Refresh topology (logical)

| Entity | Mode | Source pattern |
|---|---|---|
| Dim* (small) | Import | Full refresh nightly |
| FactSales, FactOrders, FactOps | Import (incremental) | Incremental by date key, 3-year window |
| FactAR / FactAP | Import | Full open-items + limited closed history |
| FactGL | Import | Incremental by posting period |
| FactTransport | Import | Incremental by trip date |

---

## Anti-patterns avoided

| Anti-pattern | Instead |
|---|---|
| Snowflake everything | Flatten Region onto Customer only when RLS/simplicity demands; keep Region dim for RLS |
| Active ship + invoice dates | One active; `USERELATIONSHIP` for the other |
| Margin % on fact table | Measure with `DIVIDE` |
| Bidirectional fact filters | Shared dimensions + `TREATAS` when needed |
| Report-level DAX copies | Certified measures only |
