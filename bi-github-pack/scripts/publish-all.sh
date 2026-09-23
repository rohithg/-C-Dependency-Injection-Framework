#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
USER="rohithg"

publish() {
  local dir="$1" repo="$2" desc="$3"
  echo "==> Publishing $dir -> $USER/$repo"
  cd "$ROOT/$dir"
  rm -rf .git
  git init -b main
  git add -A
  git -c user.email="rohithgangapuram1999@gmail.com" -c user.name="Rohith Gangapuram" commit -m "Initial commit: $desc"
  if ! gh repo view "$USER/$repo" >/dev/null 2>&1; then
    gh repo create "$USER/$repo" --public --description "$desc" --source=. --remote=origin --push
  else
    git remote remove origin 2>/dev/null || true
    git remote add origin "https://github.com/$USER/$repo.git"
    git push -u origin main --force
  fi
}

publish "Snowflake-Retail-Data-Warehouse" "Snowflake-Retail-Data-Warehouse" \
  "ELT pipeline on Snowflake + dbt + Airflow — star schema dimensional models for retail/supply chain."
publish "powerbi-semantic-layer" "powerbi-semantic-layer" \
  "Governed Power BI semantic layer: DAX measures, metric glossary, RLS, and workspace governance."
publish "healthcare-dimensional-model" "healthcare-dimensional-model" \
  "Synthetic EHR/claims dimensional model with SCD2, data-quality tests, and entity resolution."
publish "dbt-analytics-engineering" "dbt-analytics-engineering" \
  "Analytics engineering for B2B SaaS — metrics-as-code (ARR, churn, NRR) with dbt CI."
publish "rohith-portfolio" "rohith-portfolio" \
  "Personal portfolio showcasing BI / Analytics Engineering expertise."
publish "linkedin-executive-dashboard" "linkedin-executive-dashboard" \
  "LinkedIn-ready executive BI dashboard — Sales vs Finance semantic layer story with interactive KPIs."

echo "Enable GitHub Pages for rohith-portfolio and linkedin-executive-dashboard (main / root)"
echo "Portfolio: https://rohithg.github.io/rohith-portfolio/"
echo "LinkedIn demo: https://rohithg.github.io/linkedin-executive-dashboard/"
