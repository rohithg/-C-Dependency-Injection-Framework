# Case study — One Number for Revenue

**Candidate:** Rohith Gangapuram · BI Architect / Analytics Engineer · Dublin, CA  
**Audience:** Hiring managers for BI Engineer, Analytics Engineer, Power BI / semantic-layer roles

---

## The career problem this proves I can solve

In multi-BU commercial organizations, Sales, Finance, and Ops often ship leadership different “revenue” numbers. The spreadsheet war isn’t a visualization gap — it’s missing **metric ownership**, **grain**, and a governed path from warehouse to BI.

That is core BI Architect work.

## What “good” looks like

| Stakeholder | Needs |
|--|--|
| CFO / Controller | Recognized net revenue, margin, AR risk |
| CRO / Sales ops | Bookings / closed-won with clear conversion to recognition |
| BU presidents | Filtered truth for their region/unit only (RLS) |
| Analytics team | One semantic layer to maintain — not 12 Excel models |

## Solution pattern (what I deliver)

1. **Align definitions** — order-line grain, recognition timing, discounts/returns.  
2. **Model as data products** — dbt staging → marts on Snowflake (or equivalent).  
3. **Certify measures** — Power BI semantic layer / DAX with owners and glossary.  
4. **Enforce access** — RLS by region and business unit.  
5. **Ship one canvas** — this executive view (or its Power BI twin) for QBR / board prep.

## Outcomes this pattern drives

- Multi-million Sales↔Finance quarterly gaps reduced to residual timing items  
- ~**60%** fewer ad-hoc “whose number is right?” requests (representative)  
- Board pack prep: hours of reconciliation → filtered refresh of certified metrics  

## How I talk about this in interviews

Open the live demo. Flip region filters. Point at bookings vs recognized series. Walk AR aging. Explain what is **certified** vs **operational**. That’s the difference between a dashboard builder and a BI Architect.

## Related portfolio pieces

- Power BI semantic layer (DAX, glossary, RLS, governance)  
- Snowflake retail data warehouse (dbt + Airflow star schema)  
- dbt analytics engineering (metrics-as-code)

Live demo: https://rohithg.github.io/-C-Dependency-Injection-Framework/
