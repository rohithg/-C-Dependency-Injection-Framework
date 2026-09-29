# Row-Level Security Patterns

Role-based filtering for region managers and business-unit controllers. Filters are applied on **dimensions**; facts inherit via Many:1 relationships.

---

## Roles

| Role | Audience | Filter dimension | Sees |
|---|---|---|---|
| `Region Manager` | Field sales / regional ops | `DimRegion` | Customers, sales, ops, transport in assigned regions |
| `BU Controller` | FP&A / BU finance | `DimBusinessUnit` | Products, sales COGS/margin, GL for assigned BUs |
| `AR Analyst` | Controllership | `DimRegion` (via customer) | AR open items for region customers |
| `Executive (No RLS)` | ELT / certified viewers | — | Full model (workspace permission still required) |
| `Central Finance` | Controllership leads | — | Full finance facts; optional OU filter via BU |

---

## Security table (recommended)

Maintain assignments in a warehouse table imported as `DimUserSecurity`:

| UserEmail | RegionCode | BUCode | RoleType |
|---|---|---|---|
| alex.manager@contoso.com | West | * | Region |
| jordan.controller@contoso.com | * | BU-PACKAGING | BU |
| sam.lead@contoso.com | West | BU-PACKAGING | Region+BU |

`*` means all values for that axis.

---

## Pattern A — Region filter (static role + USERNAME)

**Role:** `Region Manager`  
**Table filter on:** `DimRegion`

```dax
// DimRegion filter
VAR _user = USERPRINCIPALNAME ()
VAR _regions =
    CALCULATETABLE (
        VALUES ( DimUserSecurity[RegionCode] ),
        DimUserSecurity[UserEmail] = _user,
        DimUserSecurity[RoleType] IN { "Region", "Region+BU" },
        DimUserSecurity[RegionCode] <> "*"
    )
VAR _seeAll =
    CONTAINS (
        CALCULATETABLE (
            DimUserSecurity,
            DimUserSecurity[UserEmail] = _user,
            DimUserSecurity[RoleType] IN { "Region", "Region+BU" }
        ),
        DimUserSecurity[RegionCode], "*"
    )
RETURN
    _seeAll || DimRegion[RegionCode] IN _regions
```

Because `DimCustomer[RegionKey] → DimRegion` and `FactSales → DimCustomer`, sales rows outside the region disappear. `FactTransport` is filtered via its direct `RegionKey` relationship.

---

## Pattern B — Business unit filter

**Role:** `BU Controller`  
**Table filter on:** `DimBusinessUnit`

```dax
// DimBusinessUnit filter
VAR _user = USERPRINCIPALNAME ()
VAR _bus =
    CALCULATETABLE (
        VALUES ( DimUserSecurity[BUCode] ),
        DimUserSecurity[UserEmail] = _user,
        DimUserSecurity[RoleType] IN { "BU", "Region+BU" },
        DimUserSecurity[BUCode] <> "*"
    )
VAR _seeAll =
    CONTAINS (
        CALCULATETABLE (
            DimUserSecurity,
            DimUserSecurity[UserEmail] = _user,
            DimUserSecurity[RoleType] IN { "BU", "Region+BU" }
        ),
        DimUserSecurity[BUCode], "*"
    )
RETURN
    _seeAll || DimBusinessUnit[BUCode] IN _bus
```

Flows: `DimBusinessUnit ← DimProduct ← FactSales / FactOps` and `DimBusinessUnit ← FactGL`.

---

## Pattern C — Combined Region + BU (intersection)

When a user has both axes, apply **both** role filters (Power BI ANDs filters from the same role across tables). For a single role that encodes both:

**Role:** `Region+BU Analyst`  
Filters on **both** `DimRegion` and `DimBusinessUnit` using Pattern A + B expressions (same role).

Effect: Sales in West **and** Packaging only — not the union.

---

## Pattern D — Simple static filter (demo / small org)

**Role:** `West Region`  
**Table:** `DimRegion`

```dax
DimRegion[RegionCode] = "West"
```

Use only for prototypes. Production should be map-driven (Pattern A).

---

## Pattern E — “My customers” via sales rep hierarchy

**Role:** `Sales Rep`  
**Table:** `DimSalesRep`

```dax
VAR _user = USERPRINCIPALNAME ()
RETURN
    DimSalesRep[RepEmail] = _user
        || PATHCONTAINS (
            DimSalesRep[ManagerPath],
            LOOKUPVALUE ( DimSalesRep[SalesRepKey], DimSalesRep[RepEmail], _user )
        )
```

Requires `ManagerPath` (PATH string) maintained in the dimension.

---

## Testing checklist

| Step | Action |
|---|---|
| 1 | Model → Manage roles → View as → pick user email |
| 2 | Validate Net Sales for West ≠ enterprise Net Sales |
| 3 | Confirm blank visuals for out-of-scope BU, not errors |
| 4 | Test `*` assignments see all regions/BUs |
| 5 | Publish; use **Test as role** in service |
| 6 | Confirm RLS still applies to Analyze in Excel / XMLA clients |

---

## Hard rules

1. **Never RLS-filter the Date table** — breaks time intelligence for everyone.
2. **Never put RLS on fact tables** if a dimension path exists — duplicated logic and leakage risk.
3. **OLS ≠ RLS** — Object-level security hides measures/tables; use for sensitive COGS if needed, separately.
4. **Service principals / gateway accounts** used for refresh must bypass or use a refresh identity that can read all source rows; RLS applies to **viewers**, not to the refresh identity’s source extraction.
5. **App audiences ≠ RLS** — workspace/app permissions gate access to the report; RLS gates rows inside the model.

---

## Mapping to glossary metrics

| Metric | RLS impact |
|---|---|
| Net Sales | Region via Customer; BU via Product |
| Gross Profit Margin % | Same paths; watch shared costs allocated only at enterprise |
| AR Aging * | Region via Customer; BU only if AR is enriched with product/BU (often not) |
| OTIF % | Region via Customer; BU via Product |
| Cost per Mile | Region via FactTransport[RegionKey] |
