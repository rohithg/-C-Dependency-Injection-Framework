# Executive Revenue Command Center

**LinkedIn-ready BI showcase** by [Rohith Gangapuram](https://github.com/rohithg)

An interactive executive dashboard that demonstrates how a **governed semantic layer** ends the classic Sales-vs-Finance revenue conflict — the same pattern behind cutting ad-hoc reporting requests ~60% for stakeholders.

🌐 **Live demo (after Pages):** [rohithg.github.io/linkedin-executive-dashboard](https://rohithg.github.io/linkedin-executive-dashboard/)  
📦 Or open `index.html` locally / via any static server.

---

## Why this project (for recruiters & hiring managers)

| Signal | Proof in this repo |
|--------|--------------------|
| Executive storytelling | Banner narrates problem → fix → result |
| Metric governance | Recognized net revenue vs closed-won bookings on one canvas |
| Self-serve BI UX | Region + business-unit filters, account drill table |
| Finance literacy | Gross margin, AR aging buckets, variance KPI |
| Shareable artifact | Designed for LinkedIn screenshots + a ready-to-post copy |

---

## Case study (short)

**Problem.** Sales reported closed-won bookings; Finance reported recognized net revenue. Board packs disagreed by **~$4.2M** in a quarter.

**Approach.** Modeled one revenue definition in a dbt / Power BI semantic layer (grain, timing, discounts, returns), added RLS by region/BU, and replaced conflicting Excel extracts with a single command-center view.

**Outcome.** Sales↔Finance variance compressed; ad-hoc “whose number is right?” requests dropped ~**60%**; leadership used one dashboard for QBR / board prep.

> Demo numbers are synthetic and labeled as such — the *method* mirrors production work.

---

## Run locally

```bash
python3 -m http.server 8090
# open http://localhost:8090
```

---

## LinkedIn post

Copy/paste from [`docs/LINKEDIN_POST.md`](docs/LINKEDIN_POST.md). Pair with a screenshot of the KPI row + trend chart.

---

## Stack

Static HTML / CSS / JS · Chart.js · Google Fonts (Fraunces + Sora)

No backend. No secrets. Safe to pin on your profile and share publicly.

## Author

**Rohith Gangapuram** · BI / Analytics Engineer · Dublin, CA  
[linkedin.com/in/rohithgangapuram](https://linkedin.com/in/rohithgangapuram) · rohithgangapuram1999@gmail.com
