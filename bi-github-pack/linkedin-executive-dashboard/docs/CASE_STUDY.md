# Case study — Sales vs Finance revenue alignment

## Context

At a multi-BU supply-chain / wholesale organization, Sales and Finance each produced executive revenue numbers from different extracts. Leadership spent QBR time reconciling slides instead of making decisions.

## What “good” looked like

| Stakeholder | Needed |
|-------------|--------|
| CFO / Controller | Recognized net revenue, margin, AR risk |
| CRO / Sales ops | Closed-won bookings and pipeline conversion |
| BU presidents | Filtered truth for their region / unit only |
| Analytics team | One semantic layer to maintain, not 12 Excel models |

## Solution pattern

1. **Align grain** — order line + recognition date (not invoice print date alone).
2. **Codify measures** — `Recognized Revenue`, `Closed-Won Bookings`, `Gross Margin %`, `AR Aging` in a shared model.
3. **Enforce access** — RLS by region and business unit.
4. **Deliver one canvas** — this command center (or Power BI twin) for exec readouts.

## Impact (representative)

- Sales↔Finance quarterly variance: **$4.2M → ~$0.3M** residual (timing items only)
- Ad-hoc reporting / reconciliation requests: **~60% reduction**
- Board pack prep: hours → a filtered refresh of one governed view

## How to talk about this in interviews

Use the demo live: flip region filters, point at the bookings vs recognized series, and walk AR aging. Recruiters remember the *story* more than the tool logos.
