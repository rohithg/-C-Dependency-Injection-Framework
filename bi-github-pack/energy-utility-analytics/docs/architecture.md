# Architecture — energy utility analytics

## Resume mapping

| Resume signal | Project artifact |
|--|--|
| Nexant utility / energy SaaS, 12-state programs | Multi-utility seeds + compliance mart |
| Power BI + DAX for usage, demand, compliance | `dax/energy_measures.dax` + dashboard |
| Star schema / dimensional modeling | `sql/01_star_schema.sql` |
| Client reporting frameworks | glossary + certified measure names |

## Flow

```
Program / meter extracts (CSV seeds)
        → star schema (utility, program, date, usage fact)
        → monthly mart
        → Power BI semantic layer (DAX)
        → executive / compliance canvas
```
