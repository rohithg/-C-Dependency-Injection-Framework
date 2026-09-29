# Unity Catalog / workspace notes

- Bronze: `main.bronze.*` — append-only landings from ADF
- Silver: `main.silver.*` — cleaned, typed, deduped
- Gold: `main.gold.usage_daily` — consumer mart for Synapse / Power BI
- Grants: `account users` SELECT on gold; engineers ALL PRIVILEGES on bronze/silver
