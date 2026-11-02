# Power BI Semantic Layer — Governed Metrics & Enterprise Modeling

[![Power BI](https://img.shields.io/badge/Power%20BI-F2C811?logo=powerbi&logoColor=black)](https://powerbi.microsoft.com/)
[![DAX](https://img.shields.io/badge/DAX-advanced-1a9e9e)](dax/measures/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**Rohith Gangapuram** · BI Architect / Analytics Engineer

Portfolio artifact demonstrating how a single governed semantic layer replaces conflicting spreadsheet metrics with certified DAX measures, documented grain, and role-based security.

> Pair with the interactive **[One Number for Revenue](https://rohithg.github.io/-C-Dependency-Injection-Framework/)** career case study for the LinkedIn-facing demo of the same story.

---

## Why this exists

Sales and Finance disagreed on “revenue.” Ops tracked OTIF differently by region. Stakeholders rebuilt the same KPIs in Excel.

This repo shows the pattern used to fix that: a **star-schema model**, a **metric glossary** with owners and grain, **reusable DAX**, **RLS by region/BU**, and **workspace governance** for 80+ consumers.

Resume-aligned scope this pattern supports:

| Capability | Scale |
|---|---|
| Governed metrics | ~250 certified measures |
| Business glossary | ~300 defined terms |
| Stakeholder coverage | 80+ across Sales, Finance, Ops, Transportation |
| Domains | Sales, AR/AP, Margin, Operations, Fleet |

---

## Repo map

```
powerbi-semantic-layer/
├── README.md
├── glossary/
│   └── metric-glossary.md          # ~40 high-value metrics (definitions, owners, grain)
├── dax/measures/
│   ├── sales_measures.dax
│   ├── finance_measures.dax        # AR/AP aging, profit margin
│   ├── operations_measures.dax
│   └── time_intelligence.dax
├── model/
│   ├── star-schema.md              # tables, relationships, cardinality
│   └── relationships.csv
├── security/
│   └── rls-patterns.md             # region / BU role filters
├── governance/
│   └── workspace-governance.md     # capacity, refresh, access checklist
├── samples/
│   └── sample-model.tmdl           # minimal tabular model sketch
└── docs/
    └── before-after.md             # Sales-vs-Finance conflict → certified metric
```

---

## Design principles

1. **One definition per metric** — name, owner, grain, filter logic, and DAX live together.
2. **Facts stay additive; ratios stay measures** — never store margin % as a fact column.
3. **Inactive relationships for alternate date paths** — `USERELATIONSHIP` for ship date vs invoice date.
4. **`DIVIDE` for all ratios** — no bare `/` that blows up on blank denominators.
5. **RLS on dimensions, not facts** — filter `DimRegion` / `DimBusinessUnit`; facts inherit via relationships.
6. **Certification gate** — a measure is “certified” only when glossary row + DAX + owner sign-off exist.

---

## Sample certified metrics (excerpt)

| Metric | Domain | Grain | Owner |
|---|---|---|---|
| Net Sales | Sales | Invoice line × day | Sales Ops |
| Gross Profit Margin % | Finance | Same as Net Sales | FP&A |
| AR Aging 61–90 | Finance | Open AR item × as-of date | Controllership |
| OTIF % | Operations | Order line × ship date | Supply Chain |
| Cost per Mile | Transportation | Trip × day | Fleet Ops |

Full catalog: [`glossary/metric-glossary.md`](glossary/metric-glossary.md)

---

## DAX style (what “good” looks like here)

```dax
Gross Profit Margin % =
DIVIDE (
    [Gross Profit],
    [Net Sales],
    BLANK ()
)

Net Sales (Ship Date) =
CALCULATE (
    [Net Sales],
    USERELATIONSHIP ( FactSales[ShipDateKey], DimDate[DateKey] )
)

Sales YTD =
TOTALYTD ( [Net Sales], DimDate[Date] )
```

See [`dax/measures/`](dax/measures/) for production-style patterns: aging buckets, dynamic as-of, period-over-period, and inactive relationship switching.

---

## Model snapshot

```
DimDate ──< FactSales >── DimCustomer >── DimRegion
              │
              ├── DimProduct >── DimBusinessUnit
              └── DimSalesRep

DimDate ──< FactAR / FactAP / FactOps / FactTransport
```

Details: [`model/star-schema.md`](model/star-schema.md)

---

## Security & governance

- **RLS**: region managers see their territory; BU controllers see their P&L slice — [`security/rls-patterns.md`](security/rls-patterns.md)
- **Workspace**: certified dataset, refresh SLAs, access tiers — [`governance/workspace-governance.md`](governance/workspace-governance.md)

---

## Before → after

Unaligned Excel “revenue” numbers vs one certified `Net Sales` measure consumed by Sales dashboards and Finance close packs: [`docs/before-after.md`](docs/before-after.md)

---

## Audience

Built for recruiters and hiring managers evaluating **BI Engineer**, **Analytics Engineer**, or **Power BI Architect** candidates who need more than “built dashboards” — semantic modeling, DAX depth, and governance.

---

## License

Portfolio / interview sample. Not production data. All figures and entities are synthetic.


## Sample import data

CSV extracts under [`samples/data/`](samples/data/) (`FactSales`, `FactAR`, `DimRegion`, `DimBusinessUnit`) for spinning up a desktop model that matches the certified measures in `dax/measures/`.
