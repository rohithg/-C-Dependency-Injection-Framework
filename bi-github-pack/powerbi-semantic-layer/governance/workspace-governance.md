# Workspace Governance Checklist

Operating standard for the certified Power BI semantic layer consumed by 80+ stakeholders.

---

## 1. Workspace topology

| Workspace | Purpose | Who publishes | Who views |
|---|---|---|---|
| **SL-Dev** | Model iteration, experimental measures | BI Engineers | BI team only |
| **SL-UAT** | Business validation, certification candidates | BI Engineers | Metric owners |
| **SL-Prod** | Certified dataset + endorsed reports | BI Lead (gated) | App audiences |
| **Finance-Secure** (optional) | OLS-restricted COGS / comp | Finance BI | Controllership |

Rules:

- No direct stakeholder access to **SL-Dev**.
- Promotion path: Dev → UAT (owner sign-off) → Prod (BI Lead).
- One **certified dataset** in Prod; reports connect live (no local .pbix models for enterprise KPIs).

---

## 2. Capacity & performance

| Check | Target | Action if breached |
|---|---|---|
| Dataset size (shared capacity) | Under tenant soft limits; prefer Premium/Fabric capacity for 80+ users | Move to dedicated capacity |
| Peak refresh CPU / memory | No refresh collision with executive briefing window | Stagger schedules; incremental refresh |
| Interactive p95 query | < 5s for primary executive pages | Aggregations, composite models, reduce visuals |
| DirectQuery sources (if any) | Avoid for certified KPI dataset | Import + incremental preferred |

Capacity hygiene:

- [ ] Dedicated capacity assigned to SL-Prod (or Fabric equivalent)
- [ ] Refresh window documented (e.g., 01:00–04:00 local)
- [ ] Heavy self-serve / personal gateways inventoried quarterly
- [ ] Aggregation tables for high-cardinality customer×day sales if needed

---

## 3. Refresh health

| Dataset | Cadence | SLA (data as-of) | Alert |
|---|---|---|---|
| Certified Semantic Layer | Nightly + optional midday sales delta | 06:00 business day | Teams + email to BI on-call |
| AR/AP open items | Nightly (post-ERP close job) | 06:30 | Controllership DL |
| Inventory snapshots | Nightly | 06:00 | Supply Chain DL |

Checklist per release:

- [ ] Incremental policy: fact date column, 3-year archive, 7-day buffer lookback
- [ ] Source credentials in gateway: service account, secret rotation dated
- [ ] Refresh failure → automatic retry (1–2) then page on-call
- [ ] “Data last refreshed” visible on executive report header (measure or card)
- [ ] Month-end: freeze certification changes during close unless FP&A approves

Sample refresh status measure (report-side metadata where available):

```dax
Data Freshness Label =
VAR _refreshed = MAX ( MetaRefresh[LastRefreshDateTime] )
RETURN
    "Data as of " & FORMAT ( _refreshed, "YYYY-MM-DD hh:mm AM/PM" )
```

---

## 4. Access control

| Tier | Permission | Granted via |
|---|---|---|
| Viewer | App only (not workspace Member) | Power BI App audience |
| Contributor (UAT) | Build on UAT dataset | Security group `SG-BI-UAT` |
| Publisher | Contributor/Member on Dev | `SG-BI-Engineers` |
| Admin | Workspace Admin Prod | `SG-BI-Leads` (break-glass) |

Checklist:

- [ ] No individual users on Prod workspace — **security groups only**
- [ ] App audiences mapped to Region / BU / Executive groups
- [ ] RLS roles tested after each membership change
- [ ] Analyze in Excel / XMLA Build permission limited to `SG-BI-Analysts-Build`
- [ ] External guest accounts blocked on SL-Prod unless Legal-approved
- [ ] Quarterly access review with metric owners (export workspace access)

---

## 5. Certification & endorsement

| State | Meaning | Who sets |
|---|---|---|
| Certified | Glossary + DAX + owner sign-off complete | BI Lead |
| Promoted | Useful but not enterprise-certified | BI Engineer |
| Deprecated | Superseded; 30-day removal notice | BI Lead |

Checklist before Certified flag:

- [ ] Glossary row complete (definition, owner, grain, pitfalls)
- [ ] Measure in Prod dataset display folder
- [ ] No duplicate measure names in other datasets
- [ ] RLS impact reviewed
- [ ] Sample visual validated vs source system recon (Materiality threshold agreed)

---

## 6. Change management

| Change type | Path |
|---|---|
| Bugfix (wrong filter) | Hotfix Dev → UAT smoke → Prod same day |
| New measure | Dev → owner review → UAT → Prod weekly train |
| Breaking rename | Deprecation period; synonym in glossary |
| Schema / relationship | Impact analysis on all Prod reports; XMLA diff |

- [ ] Pull request (or .pbix/TMDL review) required for measure changes
- [ ] VERSION note in dataset description (`Semantic Layer 2026.09.1`)
- [ ] Changelog entry for stakeholder #bi-announcements channel

---

## 7. Monitoring scorecard (monthly)

| KPI | Healthy |
|---|---|
| Refresh success rate | ≥ 99% |
| Certified measure count drift | Glossary count = Prod measure count (±WIP) |
| Ad-hoc “what is revenue?” tickets | Declining MoM (see before-after) |
| Orphan reports on old datasets | Zero on SL-Prod |
| RLS test failures | Zero |

---

## 8. Month-end close addendum

- [ ] Agree as-of date with Controllership for AR/AP aging packs
- [ ] Lock measure logic 2 business days before close (exceptions logged)
- [ ] Finance-Secure workspace refresh after ERP post
- [ ] Archive PDF of certified P&L / aging to Finance SharePoint
