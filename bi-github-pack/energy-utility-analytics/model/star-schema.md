# Energy utility star schema

```
DimDate ──< FactEnergyUsage >── DimUtility
                    \
                     >── DimProgram
```

**Grain:** one row per utility × program × day.  
**Resume story:** Nexant 12-state energy programs / $500M+ program spend → Power BI + dimensional model for usage, demand, compliance.
